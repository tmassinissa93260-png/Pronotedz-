"""Le registre de modèles, les prompts versionnés, et l'agent d'écriture.

L'appel réseau à Claude est remplacé par une réponse factice : on teste la
chaîne complète (prompt → appel → validation → sortie) sans clé d'API.
"""


import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from pdz.agents import base as agents_base
from pdz.agents.base import (
    Agent,
    mots_par_replique,
    nb_beats_pour,
    nb_plans_pour,
    nb_repliques_pour,
    positions_relance_par_defaut,
    texte_empreinte,
)
from pdz.agents.ecriture.script import ScriptWriter, _normaliser_emotion
from pdz.ia.registre import registre
from pdz.moteur.erreurs import ErreurConfig, ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.prompts import charger
from pdz.prompts.registre import Prompt
from pdz.univers import (
    ChampInterprete,
    EmpreinteAudio,
    EmpreinteCreative,
    EmpreinteHook,
    EmpreinteNarrative,
    EmpreintePsychologie,
    EmpreinteVisuelle,
    Univers,
)

FRUITS = Path("univers/fruit-island.yaml")


# ── Registre de modèles ──────────────────────────────────────────────────

def test_un_alias_se_resout_en_modele():
    res = registre().resoudre("qualite")
    assert res.modele.id
    assert "ecriture" in res.modele.fait


def test_le_profil_change_le_modele_dimages():
    eco = registre().resoudre("images", profil="economique")
    premium = registre().resoudre("images", profil="premium")
    assert eco.modele.id != premium.modele.id
    assert eco.modele.prix.par_image < premium.modele.prix.par_image


def test_un_budget_bas_bascule_sur_le_modele_moins_cher():
    normal = registre().resoudre("qualite", budget_restant_pct=100)
    serre = registre().resoudre("qualite", budget_restant_pct=10)
    assert serre.modele.id != normal.modele.id
    assert "budget" in serre.raison


def test_alias_inconnu_donne_un_message_utile():
    with pytest.raises(ErreurConfig) as e:
        registre().resoudre("licorne")
    assert "Connus" in str(e.value)


# ── Repli quand une clé manque ───────────────────────────────────────────
# Mesuré en conditions réelles : `--profil equilibre` sans crédit Anthropic
# s'arrêtait net sur « clé d'API manquante », alors qu'une clé Groq
# fonctionnelle était configurée. Le repli évite de perdre une production
# entière pour une clé qu'on a décidé de ne pas payer.

def _config_avec(monkeypatch, **cles):
    """Rend une configuration où seules les clés nommées sont renseignées.

    Le module se patche par son objet et non par son chemin : `pdz.ia.registre`
    désigne aussi la fonction `registre()`, que pytest trouve en premier.
    """
    import sys
    from types import SimpleNamespace
    monkeypatch.setattr(
        sys.modules["pdz.ia.registre"], "config",
        lambda: SimpleNamespace(**{
            "anthropic_api_key": "", "fal_key": "", "groq_api_key": "",
            "elevenlabs_api_key": "", "audd_api_key": "", **cles,
        }),
    )


def _sans_anthropic(monkeypatch):
    _config_avec(monkeypatch, groq_api_key="gsk_test", fal_key="k")


def test_une_cle_absente_ne_bloque_pas_si_un_equivalent_existe(monkeypatch):
    _sans_anthropic(monkeypatch)
    res = registre().resoudre("qualite", profil="equilibre",
                              repli_si_cle_absente=True)
    assert res.modele.fournisseur == "groq"
    assert "absente" in res.raison


def test_le_repli_garde_la_meme_capacite(monkeypatch):
    """Le repli passe par `fait` : jamais une voix là où il faut du texte."""
    _sans_anthropic(monkeypatch)
    res = registre().resoudre("qualite", profil="equilibre",
                              repli_si_cle_absente=True)
    assert "ecriture" in res.modele.fait


def test_la_resolution_reste_pure_sans_le_drapeau(monkeypatch):
    """Interroger le registre pour savoir ce qu'un profil *désigne* ne doit
    pas dépendre des clés présentes — sinon `pdz modeles` mentirait sur la
    configuration réelle."""
    _sans_anthropic(monkeypatch)
    res = registre().resoudre("qualite", profil="equilibre")
    assert res.modele.fournisseur == "anthropic"


def test_sans_equivalent_disponible_la_cle_manquante_reste_une_erreur(monkeypatch):
    """Aucune alternative à ElevenLabs pour la voix : le repli ne doit pas
    inventer un remplaçant, l'erreur claire vaut mieux."""
    _config_avec(monkeypatch)
    res = registre().resoudre("voix", repli_si_cle_absente=True)
    assert res.modele.fournisseur == "elevenlabs"


def test_un_fournisseur_sans_cle_declaree_est_toujours_disponible():
    """Pollinations ne demande aucune clé : il ne doit jamais être écarté
    faute de configuration."""
    assert registre().cle_disponible("pollinations")


# ── Capacité exigée par l'appel (vision) ─────────────────────────────────

def test_une_capacite_manquante_fait_changer_de_modele(monkeypatch):
    """`charte` envoie des images sous l'alias « qualite », que le profil
    gratuit résout vers un modèle sans vision."""
    _sans_anthropic(monkeypatch)
    res = registre().resoudre("qualite", profil="gratuit",
                              repli_si_cle_absente=True,
                              capacite_requise="vision")
    assert "vision" in res.modele.fait
    assert res.modele.fournisseur == "groq"


def test_la_capacite_survit_au_repli_de_cle(monkeypatch):
    """Non-régression : le repli de clé choisit sur les capacités en commun,
    pas sur celle qu'on exige. Appliqué après le contrôle de capacité, il
    ramenait `equilibre` sans clé Anthropic vers un modèle sans vision."""
    _sans_anthropic(monkeypatch)
    res = registre().resoudre("qualite", profil="equilibre",
                              repli_si_cle_absente=True,
                              capacite_requise="vision")
    assert "vision" in res.modele.fait, f"{res.modele.id} ne fait pas de vision"


def test_avec_une_cle_anthropic_la_vision_reste_chez_claude(monkeypatch):
    """Le modèle gratuit de vision est un dépannage, pas une rétrogradation
    imposée à qui a payé."""
    _config_avec(monkeypatch, anthropic_api_key="sk-ant-x", groq_api_key="gsk_x")
    res = registre().resoudre("qualite", profil="equilibre",
                              repli_si_cle_absente=True,
                              capacite_requise="vision")
    assert res.modele.fournisseur == "anthropic"


def test_sans_aucun_modele_capable_le_message_est_explicite(monkeypatch):
    _config_avec(monkeypatch)
    with pytest.raises(ErreurConfig) as e:
        registre().resoudre("qualite", profil="gratuit",
                            repli_si_cle_absente=True,
                            capacite_requise="vision")
    assert "vision" in str(e.value) and "modeles.yaml" in str(e.value)


def test_une_capacite_deja_presente_ne_change_rien():
    """`claude-sonnet-5` fait déjà de la vision : aucune substitution."""
    sans = registre().resoudre("qualite", profil="equilibre")
    avec = registre().resoudre("qualite", profil="equilibre",
                               capacite_requise="vision")
    assert sans.modele.id == avec.modele.id


def test_le_cache_reduit_le_cout():
    m = registre().modeles["claude-sonnet-5"]
    sans = m.cout_texte(entree=4000, sortie=1500)
    avec = m.cout_texte(entree=4000, sortie=1500, cache_lu=2800)
    assert avec < sans


# ── Découpage : réplique ≠ plan ──────────────────────────────────────────

@pytest.mark.parametrize("duree", [30, 45, 90])
def test_il_y_a_environ_deux_plans_par_replique(duree):
    """Un plan toutes les ~1,75 s, une réplique toutes les ~3,5 s."""
    ratio = nb_plans_pour(duree) / nb_repliques_pour(duree)
    assert 1.7 <= ratio <= 2.3


def test_les_repliques_font_une_longueur_dicible():
    mots = mots_par_replique(45, nb_repliques_pour(45))
    assert all(7 <= m <= 12 for m in mots), mots


@pytest.mark.parametrize("duree,attendu_min,attendu_max", [(20, 4, 4), (45, 4, 8), (90, 8, 8)])
def test_le_nombre_de_beats_reste_dans_une_structure_lisible(duree, attendu_min, attendu_max):
    """Moins de 4, plus de hook/tension/payoff possible. Plus de 8, chaque
    temps fort dure moins de 5-6 s et n'est plus un beat narratif."""
    n = nb_beats_pour(duree)
    assert attendu_min <= n <= attendu_max


# ── Positions de relance par défaut, sans référence ──────────────────────

def test_les_positions_de_relance_par_defaut_ne_sont_jamais_vides():
    """Mesuré en conditions réelles avec Llama/Groq : une liste vide laisse
    le modèle deviner le timing, et il rend parfois un script sans aucune
    relance cochée. Sans référence, une liste calculée remplace la vide."""
    for duree in (30, 45, 90):
        assert positions_relance_par_defaut(duree, nb_repliques_pour(duree))


def test_les_positions_de_relance_respectent_lintervalle_de_15_a_20s():
    duree, repliques = 90, nb_repliques_pour(90)
    duree_par_replique = duree / repliques
    positions = positions_relance_par_defaut(duree, repliques)
    ecarts = [b - a for a, b in zip(positions, positions[1:])]
    for ecart in ecarts:
        assert 15 <= ecart * duree_par_replique <= 20


def test_les_positions_de_relance_restent_dans_les_repliques():
    for duree in (20, 30, 45, 90, 180):
        repliques = nb_repliques_pour(duree)
        for pos in positions_relance_par_defaut(duree, repliques):
            assert 1 <= pos < repliques


# ── Prompts versionnés ───────────────────────────────────────────────────

def test_le_prompt_se_charge_et_se_rend():
    p = charger("ecriture/script")
    # On n'attend pas un numéro de version précis : le figer ici obligerait à
    # modifier ce test à chaque amélioration de prompt, ce qui est exactement
    # ce que le versionnement doit éviter. On vérifie l'identité et le rendu.
    assert p.id == "ecriture/script"
    assert p.statut == "stable"
    stable, _, message = p.rendre(
        contexte_univers="UNIVERS : test",
        situation="une dispute",
        duree_s=45, nb_repliques=13,
        mots_par_replique=[9] * 13, nb_plans_vises=26,
        resume_precedent="",
    )
    assert "UNIVERS : test" in stable
    assert "une dispute" in message


def test_laction_doit_etre_ecrite_en_anglais():
    """Audit data-flow SCRIPT → PROMPT : `action` devient directement le
    prompt d'image (contrainte 12), mais c'était le seul maillon de toute
    la chaîne visuelle sans consigne de langue — `replique` (la voix) reste
    en français, `action` (l'image) doit être en anglais comme le style,
    les décors et tout ce que ShotPromptWriter écrit déjà."""
    p = charger("ecriture/script")
    assert "anglais" in p.systeme_stable.lower()
    proprietes = p.schema_sortie["properties"]["repliques"]["items"]["properties"]
    assert "anglais" in proprietes["action"]["description"].lower()
    # `replique` (la voix, jamais traduite) ne doit pas recevoir la même
    # consigne — sinon ElevenLabs recevrait du texte anglais à dire en
    # français.
    assert "anglais" not in proprietes["replique"]["description"].lower()


def test_les_entrees_optionnelles_sont_vraiment_optionnelles():
    """Ne rien passer d'optionnel doit rendre, pas lever.

    Avec StrictUndefined, un `{% if x %}` sur une variable absente échoue.
    C'est le piège de l'ajout d'une entrée optionnelle à un prompt existant :
    tous les appels qui marchaient se mettent à planter.
    """
    p = charger("ecriture/script")
    _, variable, message = p.rendre(
        contexte_univers="U", situation="s", duree_s=45, nb_repliques=13,
        mots_par_replique=[9] * 13, nb_plans_vises=26,
    )
    assert "FORME À ÉPOUSER" not in variable
    assert "SQUELETTE" not in message


def test_une_variable_oubliee_echoue_tout_de_suite():
    with pytest.raises(ErreurValidation) as e:
        charger("ecriture/script").rendre(situation="x")
    assert "manquantes" in str(e.value)


def test_le_squelette_narratif_est_presente_comme_un_guide_pas_une_quota():
    """Mesuré à l'écran une fois BriefWriter branché (toujours rempli, 4 à 8
    temps forts) : un script de 268 mots pour 45 s demandées (117 attendus)
    — le modèle développait chaque temps fort en sa propre réplique au lieu
    de les condenser dans le nombre déjà imposé."""
    p = charger("ecriture/script")
    assert "guide" in p.systeme_stable.lower()
    _, _, message = p.rendre(
        contexte_univers="U", situation="s", duree_s=45, nb_repliques=6,
        mots_par_replique=[9] * 6, nb_plans_vises=12,
        beats=[{"position_pct": 0, "role": "hook", "quoi": "il se passe X"}],
    )
    assert "condens" in message.lower()


# ── L'agent, avec un Claude factice ──────────────────────────────────────

def _reponse_factice(univers, nb=13, avec_relance=True, personnage=None):
    perso = univers.personnages[0].id if personnage is None else personnage
    return {
        "titre": "La trahison",
        "promesse": "Elle va tout avouer",
        "derniere_image": "retour sur le premier plan",
        "repliques": [
            {
                "numero": i + 1,
                "personnage": perso,
                "replique": "Tu savais depuis le début et tu n as rien dit",
                "action": "elle se retourne lentement",
                "emotion": "colere",
                "reaction_de": "",
                "relance": avec_relance and i == 5,
            }
            for i in range(nb)
        ],
    }


def _contexte():
    return Contexte(job_id="j", etape_cle="script", profil="equilibre",
                    budget_restant=0.60)


def test_lagent_valide_et_enrichit_la_sortie():
    u = Univers.charger(FRUITS)
    agent = ScriptWriter()
    sortie = agent.apres(_reponse_factice(u), {"univers": u}, _contexte())
    assert sortie["nb_repliques"] == 13
    assert sortie["mots_total"] > 0
    assert sortie["duree_parlee_estimee_s"] > 0


def test_lagent_refuse_un_personnage_inconnu():
    u = Univers.charger(FRUITS)
    mauvais = _reponse_factice(u, personnage="pasteque_inexistante")
    with pytest.raises(ErreurValidation) as e:
        ScriptWriter().apres(mauvais, {"univers": u}, _contexte())
    assert "inconnu de l'univers" in str(e.value)


def test_lagent_refuse_un_personnage_vide():
    """Mesuré en conditions réelles avec Llama/Groq : le champ peut être
    laissé complètement vide plutôt que mal orthographié."""
    u = Univers.charger(FRUITS)
    vide = _reponse_factice(u, personnage="")
    with pytest.raises(ErreurValidation) as e:
        ScriptWriter().apres(vide, {"univers": u}, _contexte())
    assert "inconnu de l'univers" in str(e.value)


def test_lagent_normalise_la_casse_du_personnage():
    """Mesuré en conditions réelles : Llama renvoie « Strawberina » (le nom
    affiché) plutôt que « strawberina » (l'identifiant). On rapproche par
    casse au lieu de faire échouer tout l'épisode pour ça."""
    u = Univers.charger(FRUITS)
    id_reel = u.personnages[0].id
    depareille = _reponse_factice(u, personnage=id_reel.upper())
    sortie = ScriptWriter().apres(depareille, {"univers": u}, _contexte())
    assert all(r["personnage"] == id_reel for r in sortie["repliques"])


def test_normaliser_emotion_une_valeur_vide_ou_absente_donne_calme():
    assert _normaliser_emotion("") == "calme"
    assert _normaliser_emotion(None) == "calme"


def test_une_emotion_hors_liste_retombe_sur_calme_sans_faire_echouer():
    """Mesuré en conditions réelles avec Llama/Groq : une seule valeur
    d'émotion hors liste (accentuée, traduite) fait rejeter TOUT le script
    par la validation côté serveur de Groq, pas seulement ce champ.
    `emotion` n'est donc plus un `enum` du schéma (voir script@1.4.0) —
    corrigé ici après coup, comme `decor`/`reaction_de`."""
    u = Univers.charger(FRUITS)
    sortie = _reponse_factice(u)
    sortie["repliques"][0]["emotion"] = "angry"
    corrige = ScriptWriter().apres(sortie, {"univers": u}, _contexte())
    assert corrige["repliques"][0]["emotion"] == "calme"


def test_une_emotion_accentuee_est_normalisee():
    u = Univers.charger(FRUITS)
    sortie = _reponse_factice(u)
    sortie["repliques"][0]["emotion"] = "Gêne"
    corrige = ScriptWriter().apres(sortie, {"univers": u}, _contexte())
    assert corrige["repliques"][0]["emotion"] == "gene"


def test_une_emotion_valide_traverse_intacte():
    u = Univers.charger(FRUITS)
    sortie = _reponse_factice(u)
    sortie["repliques"][0]["emotion"] = "tristesse"
    corrige = ScriptWriter().apres(sortie, {"univers": u}, _contexte())
    assert corrige["repliques"][0]["emotion"] == "tristesse"


def test_le_schema_actif_ne_contraint_plus_lemotion_par_enum():
    """Depuis script@1.4.0 : contraindre par `enum` un champ déjà rattrapable
    après coup ne protégeait rien et rendait tout le script fragile chez
    Groq. Toujours vrai sur la version active — figer le numéro ici
    obligerait à modifier ce test à chaque amélioration du prompt."""
    schema = charger("ecriture/script").schema_sortie
    proprietes = schema["properties"]["repliques"]["items"]["properties"]
    assert "enum" not in proprietes["emotion"]


def test_le_schema_impose_le_nombre_de_repliques_vise():
    """Mesuré à l'écran : rien n'empêchait un script de 2 répliques bien
    formées, alors qu'il en fallait 6 pour tenir la durée — le schéma
    validait chaque réplique présente, jamais leur nombre. `minItems`
    l'impose désormais, au même niveau que Groq valide déjà tout le reste."""
    u = Univers.charger(FRUITS)
    base = charger("ecriture/script").schema_sortie
    schema = ScriptWriter().schema(base, {"univers": u, "duree_s": 45}, _contexte())
    attendu = ScriptWriter()._forme({"univers": u, "duree_s": 45})["nb_repliques"]
    assert schema["properties"]["repliques"]["minItems"] == attendu
    assert attendu >= 3


def test_la_consigne_de_cadrage_est_dans_le_prompt_actif():
    """Comparé à un prompt écrit à la main avec cadrage, lumière et point de
    netteté précisés, une `action` qui ne dit que « ce qui se passe » donne
    une image quelconque même sur le bon sujet. Non-régression : cette
    consigne ne doit pas disparaître au prochain bump de version."""
    stable = charger("ecriture/script").systeme_stable.lower()
    assert "cadre chaque" in stable or "cadrage" in stable


def test_le_message_derreur_trop_court_redonne_la_cible_complete():
    """Un delta seul ('ajoute 44 mots') suppose que le modèle se souvient
    encore de la cible d'origine, loin plus haut dans le prompt. Un modèle
    plus faible (Llama) a besoin qu'on la lui redonne."""
    u = Univers.charger(FRUITS)
    court = _reponse_factice(u, nb=7)
    with pytest.raises(ErreurValidation) as e:
        ScriptWriter().apres(court, {"univers": u, "duree_s": 45}, _contexte())
    message = str(e.value)
    assert "au total" in message
    assert "répliques" in message
    assert "CHAQUE réplique" in message


def test_le_schema_ferme_le_personnage_a_lunivers():
    """Un `enum` guide bien mieux un modèle qu'une description en texte
    libre — surtout un modèle moins strict sur les instructions."""
    u = Univers.charger(FRUITS)
    base = charger("ecriture/script").schema_sortie
    schema = ScriptWriter().schema(base, {"univers": u}, _contexte())
    proprietes = schema["properties"]["repliques"]["items"]["properties"]

    ids_attendus = sorted(p.id for p in u.personnages)
    assert proprietes["personnage"]["enum"] == ids_attendus
    assert "" not in proprietes["personnage"]["enum"], (
        "le personnage n'est jamais optionnel, contrairement à decor/reaction_de"
    )


def test_decor_et_reaction_sont_decrits_mais_pas_contraints():
    """Groq valide le schéma côté serveur et REJETTE toute la réponse sur
    une seule valeur hors liste. On ne paie ce risque que pour ce qui ne se
    rattrape pas : une valeur de décor inconnue retombe sans dommage sur le
    premier décor de l'univers."""
    u = Univers.charger(FRUITS)
    base = charger("ecriture/script").schema_sortie
    schema = ScriptWriter().schema(base, {"univers": u}, _contexte())
    proprietes = schema["properties"]["repliques"]["items"]["properties"]

    assert "enum" not in proprietes["decor"]
    assert "enum" not in proprietes["reaction_de"]
    # Mais les valeurs attendues restent nommées, pour guider le modèle.
    for identifiant in (d.id for d in u.decors):
        assert identifiant in proprietes["decor"]["description"]


def test_avec_un_seul_locuteur_le_personnage_nest_pas_demande():
    """En narration, il n'y a rien à choisir : demander quand même ouvre une
    porte à l'erreur sans rien apporter."""
    u = Univers.charger(Path("univers/techno-holo.yaml"))
    base = charger("ecriture/script").schema_sortie
    schema = ScriptWriter().schema(base, {"univers": u}, _contexte())
    items = schema["properties"]["repliques"]["items"]

    assert "personnage" not in items["properties"]
    assert "personnage" not in items["required"]


def test_le_locuteur_unique_est_rempli_apres_coup():
    u = Univers.charger(Path("univers/techno-holo.yaml"))
    sortie = _reponse_factice(u, personnage="")
    sortie = ScriptWriter().apres(sortie, {"univers": u}, _contexte())
    assert all(r["personnage"] == "narrateur" for r in sortie["repliques"])


def test_le_schema_ne_modifie_pas_le_prompt_partage():
    """`charger()` met le Prompt en cache (lru_cache) : un `schema()` qui
    modifierait le dict en place corromprait tous les appels suivants,
    y compris pour un autre univers."""
    u = Univers.charger(FRUITS)
    base_avant = charger("ecriture/script").schema_sortie
    proprietes_avant = base_avant["properties"]["repliques"]["items"]["properties"]
    assert "enum" not in proprietes_avant["personnage"]

    ScriptWriter().schema(charger("ecriture/script").schema_sortie, {"univers": u}, _contexte())

    base_apres = charger("ecriture/script").schema_sortie
    proprietes_apres = base_apres["properties"]["repliques"]["items"]["properties"]
    assert "enum" not in proprietes_apres["personnage"]


def test_lagent_refuse_un_script_trop_court():
    """Mesuré à l'écran : 24 s rendues pour 45 s demandées. La durée était
    calculée puis rangée, jamais vérifiée."""
    u = Univers.charger(FRUITS)
    # 7 répliques : assez pour que la relance existe (le contrôle qui la
    # cherche passe avant), trop peu pour tenir 45 s.
    court = _reponse_factice(u, nb=7)
    with pytest.raises(ErreurValidation) as e:
        ScriptWriter().apres(court, {"univers": u, "duree_s": 45}, _contexte())
    assert "trop court" in str(e.value)
    # Le modèle doit savoir de combien il s'est trompé, pas seulement qu'il
    # s'est trompé : c'est ce qui rend la relance utile.
    assert "mots" in str(e.value)


def test_lagent_accepte_un_script_trop_long_avec_un_avertissement(caplog):
    """Trop long ne bloque plus le job, contrairement à trop court : rien ne
    se perd, l'épisode sort juste plus long que visé. Refuser ici gaspillait
    une tentative de correction (et de l'argent, sur un 429 Groq mesuré en
    conditions réelles) pour un défaut qui n'empêche pas l'épisode d'exister."""
    u = Univers.charger(FRUITS)
    long = _reponse_factice(u, nb=40)
    with caplog.at_level(logging.WARNING):
        sortie = ScriptWriter().apres(long, {"univers": u, "duree_s": 20}, _contexte())
    assert sortie["duree_parlee_estimee_s"] > 20 * 1.4
    assert any("plus long" in m for m in caplog.messages)


def test_une_duree_dans_la_cible_passe():
    """La borne est large à dessein : on rejette ce qui se voit, pas ce qui
    approche."""
    u = Univers.charger(FRUITS)
    sortie = ScriptWriter().apres(_reponse_factice(u, nb=13),
                                  {"univers": u, "duree_s": 45}, _contexte())
    assert 0.7 <= sortie["duree_parlee_estimee_s"] / 45 <= 1.4


def test_lagent_refuse_un_script_sans_relance():
    u = Univers.charger(FRUITS)
    plat = _reponse_factice(u, avec_relance=False)
    with pytest.raises(ErreurValidation) as e:
        ScriptWriter().apres(plat, {"univers": u}, _contexte())
    assert "relance" in str(e.value)


def test_la_signature_change_avec_la_version_du_prompt():
    """C'est ce qui invalide le cache automatiquement quand un prompt bouge."""
    sig = ScriptWriter().signature()
    assert sig["prompt"] == charger("ecriture/script").ref
    assert sig["agent"] == "script"
    # Le point du test : la version du prompt est DANS la signature, donc
    # publier un prompt invalide le cache sans purge manuelle.
    assert "@" in sig["prompt"]


def test_les_variables_du_prompt_sont_calculees_depuis_lunivers():
    u = Univers.charger(FRUITS)
    v = ScriptWriter().variables({"univers": u, "situation": "test"}, _contexte())
    assert v["duree_s"] == u.duree_cible_s
    assert len(v["mots_par_replique"]) == v["nb_repliques"]
    assert "Strawberina" in v["contexte_univers"]


# ── Empreinte créative : direction, jamais une contrainte chiffrée ───────

def _empreinte():
    champ = lambda v, c=0.8: ChampInterprete(valeur=v, confiance=c,
                                             observation="vu dans la référence")
    return EmpreinteCreative(
        hook=EmpreinteHook(type=champ("question impossible"),
                           mecanisme=champ("hypothèse personnelle"),
                           promesse=champ("une révélation")),
        narrative=EmpreinteNarrative(structure=champ("mise en place, escalade"),
                                     escalade=champ("chaque plan ajoute une info"),
                                     fin=champ("révélation ouverte")),
        psychologie=EmpreintePsychologie(curiosite=champ("question sans réponse"),
                                         arc_emotionnel=champ("curiosité, tension"),
                                         retention=champ("chaque plan retient une info")),
        visuel=EmpreinteVisuelle(style=champ("cinématique"),
                                 cadrage=champ("varie large puis serré")),
        audio=EmpreinteAudio(silence=champ("silences courts")),
        principes_reutilisables=["pose une question avant la 3e seconde"],
    )


def test_lempreinte_se_rend_en_texte_avec_les_confiances():
    texte = texte_empreinte(_empreinte())
    assert "question impossible" in texte
    assert "80%" in texte
    assert "pose une question avant la 3e seconde" in texte


def test_un_champ_inconnu_nest_pas_rendu():
    """« unknown » n'apporte rien au scénariste — l'inclure donnerait
    l'illusion d'une information là où il n'y en a pas."""
    e = _empreinte()
    e.hook.type = ChampInterprete()  # valeur="unknown", confiance=0.0 par défaut
    texte = texte_empreinte(e)
    assert "unknown" not in texte


def test_un_champ_a_faible_confiance_nest_pas_rendu():
    e = _empreinte()
    e.hook.type = ChampInterprete(valeur="mystère", confiance=0.1,
                                  justification="incertain")
    assert "mystère" not in texte_empreinte(e)


def test_les_variables_incluent_lempreinte_quand_lunivers_en_a_une():
    u = Univers.charger(FRUITS)
    u.empreinte_creative = _empreinte()
    v = ScriptWriter().variables({"univers": u, "situation": "test"}, _contexte())
    assert "question impossible" in v["empreinte_texte"]


def test_les_variables_sans_empreinte_donnent_un_texte_vide():
    """Non-régression : un univers sans vidéo de référence continue de
    fonctionner exactement comme avant l'ajout de l'empreinte créative."""
    u = Univers.charger(FRUITS)
    assert u.empreinte_creative is None
    v = ScriptWriter().variables({"univers": u, "situation": "test"}, _contexte())
    assert v["empreinte_texte"] == ""


# ── Stratégie créative de BriefWriter, exécutée ici ─────────────────────

def test_la_strategie_de_brief_passe_dans_les_variables():
    u = Univers.charger(FRUITS)
    strategie = {"mecanisme_hook": "question", "arc_narratif": "montée",
                "ce_qui_retient": "info gap", "a_eviter": "cliché"}
    v = ScriptWriter().variables(
        {"univers": u, "situation": "test", "strategie": strategie}, _contexte())
    assert v["strategie"] == strategie


def test_sans_strategie_les_variables_restent_valides():
    """Non-régression : un appel direct (sans passer par BriefWriter, comme
    `pdz avant-apres`) continue de fonctionner sans stratégie."""
    u = Univers.charger(FRUITS)
    v = ScriptWriter().variables({"univers": u, "situation": "test"}, _contexte())
    assert v["strategie"] == {}


# ── Relance après ErreurValidation : montrer l'erreur au modèle ─────────
#
# La docstring d'ErreurValidation promettait « on relance en montrant
# l'erreur au modèle » — mesuré en conditions réelles : ce n'était vrai
# nulle part dans le code, une relance rejouait le même essai avec les
# mêmes entrées. Un script trop court restait trop court trois fois de
# suite avec Llama (profil gratuit) jusqu'à l'échec du job entier. Le fil
# réel est en deux morceaux : pipeline.py injecte `_erreur_precedente`
# dans les entrées avant de relancer (testé dans test_moteur.py),
# Agent.executer() la lit ici et l'ajoute au message envoyé au modèle.

def _agent_de_test(monkeypatch):
    prompt_factice = Prompt(id="test/agent", version="1.0.0",
                            message="Écris un script.", schema_sortie={})
    monkeypatch.setattr(agents_base.prompts, "charger", lambda ref: prompt_factice)

    messages_recus = []

    async def faux_appeler(**kwargs):
        messages_recus.append(kwargs["message"])
        return SimpleNamespace(cout=0.0, donnees={"ok": True})

    monkeypatch.setattr(agents_base.texte, "appeler", faux_appeler)

    class AgentTest(Agent):
        nom = "agent_test"
        prompt_ref = "test/agent"

        def variables(self, entrees, ctx):
            return {}

    return AgentTest(), messages_recus


def test_lerreur_precedente_est_ajoutee_au_message_envoye(monkeypatch):
    agent, messages_recus = _agent_de_test(monkeypatch)
    asyncio.run(agent.executer(
        {"_erreur_precedente": "Script trop court : ajoute 18 mots."}, _contexte(),
    ))
    assert "Script trop court : ajoute 18 mots." in messages_recus[0]
    assert "essai précédent" in messages_recus[0]


def test_le_premier_essai_ne_porte_aucune_trace_de_correction(monkeypatch):
    """Premier essai, pas de relance : le message part inchangé."""
    agent, messages_recus = _agent_de_test(monkeypatch)
    asyncio.run(agent.executer({}, _contexte()))
    assert messages_recus[0] == "Écris un script."
