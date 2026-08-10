"""Le registre de modèles, les prompts versionnés, et l'agent d'écriture.

L'appel réseau à Claude est remplacé par une réponse factice : on teste la
chaîne complète (prompt → appel → validation → sortie) sans clé d'API.
"""


from pathlib import Path

import pytest

from pdz.agents.base import (
    mots_par_replique,
    nb_plans_pour,
    nb_repliques_pour,
    positions_relance_par_defaut,
)
from pdz.agents.ecriture.script import ScriptWriter
from pdz.ia.registre import registre
from pdz.moteur.erreurs import ErreurConfig, ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.prompts import charger
from pdz.univers import Univers

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


def test_le_schema_ferme_les_identifiants_a_lunivers():
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
    assert set(proprietes["reaction_de"]["enum"]) == {*ids_attendus, ""}


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
