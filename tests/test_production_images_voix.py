"""Ce qui décide de la dépense et de la ressemblance.

Rien ici n'appelle un fournisseur : on teste les décisions prises AVANT
l'appel — combien de plans on peut payer, quel prompt part, quelle voix est
retenue. Ce sont ces décisions qui coûtent de l'argent, pas le transport HTTP.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from pdz.agents.analyse.charte import (
    CharteVisuelle,
    _graine,
    _identifiant,
    _nettoyer_rendu,
    vers_univers,
)
from pdz.analyse.visuel import AnalyseVisuelle, Couleur
from pdz.analyse.voix import ProfilVoix
from pdz.moteur.erreurs import ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.production import animation, contrat_visuel, images
from pdz.production.appariement_voix import POIDS_HAUTEUR_SEULE, Candidat, profil_suppose
from pdz.production.storyboard import PlanScript
from pdz.univers import Univers

FRUITS = Path(__file__).resolve().parent.parent / "univers" / "fruit-island.yaml"


def _contexte():
    return Contexte(job_id="job_test", etape_cle="test", profil="equilibre",
                    budget_restant=1.0)


def _visuel(palette=("#FF4D6D", "#118AB2", "#FFD166")):
    return AnalyseVisuelle(
        images_cles=[], palette=[Couleur(h, 0.3, 10.0, 0.8, 0.7) for h in palette],
        luminosite=0.5, contraste=0.25, saturation=0.6, temperature=0.15,
        nettete=0.6, grain=0.05, cadrage_x=0.5, cadrage_y=0.5,
        echelle_sujet=0.4, densite_mouvement=0.3, confiance=0.85,
    )


def _charte(nb=2):
    return {
        "rendu": "flat 2D vector animation, thick black outlines, no gradients",
        "eclairage": "even front lighting",
        "ambiance": "comédie de bureau",
        "personnages": [
            {
                "id": f"perso{i}", "nom": f"Perso {i}", "espece": "agrafeuse",
                "apparence": ("a chunky red desktop stapler with two round googly "
                              "eyes glued on its hinge, chipped chrome jaw, small "
                              "paper clip arms, wobbling on a wooden desk"),
                "caractere": "autoritaire", "images": [1, 2],
                "voix_percue": {"registre": "grave", "ton": "posé et las"},
            }
            for i in range(nb)
        ],
        "decors": [{"id": "bureau", "nom": "Le bureau",
                    "description": "grey open space office, fluorescent ceiling lights"}],
        "regles_du_monde": ["Les objets de bureau parlent", "Personne ne sort jamais"],
        "transposition": [{"personnage": "Perso 0", "garde": "l'archétype",
                           "change": "l'espèce"}],
        "incertitudes": [],
    }


# ── De la charte à l'univers ─────────────────────────────────────────────

def test_la_palette_de_lunivers_vient_des_mesures_pas_du_modele():
    """Le modèle nomme mal les couleurs ; l'histogramme non.

    C'est la règle de partage du module : mesuré d'un côté, interprété de
    l'autre, jamais mélangés.
    """
    visuel = _visuel()
    u = vers_univers(_charte(), visuel, identifiant="test", nom="Test")
    assert u.style.palette == visuel.palette_hex[:5]


def test_la_graine_est_stable_dune_execution_a_lautre():
    """`hash()` est salé à chaque lancement : deux runs, deux styles."""
    assert _graine("fruit-island") == _graine("fruit-island")
    assert _graine("fruit-island") != _graine("garage-42")


def test_une_reference_a_une_oeuvre_est_retiree_du_rendu():
    nettoye = _nettoyer_rendu("cel-shaded anime, in the style of Studio Ghibli")
    assert "ghibli" not in nettoye.lower()
    assert "cel-shaded" in nettoye


def test_lunivers_produit_passe_le_validateur_de_style():
    """Le validateur refuserait un nom d'œuvre : la charte ne doit pas en produire."""
    u = vers_univers(_charte(), _visuel(), identifiant="test", nom="Test")
    assert u.style.rendu


def test_les_identifiants_sont_utilisables_comme_noms_de_fichiers():
    assert _identifiant("Éric l'Agrafeuse !") == "eric_l_agrafeuse"
    assert _identifiant("  ") == "sans_nom"


def test_les_personnages_arrivent_sans_voix_mais_avec_des_reglages():
    """La voix se choisit en mesurant, pas en devinant — mais le ton perçu
    donne déjà les réglages de jeu."""
    u = vers_univers(_charte(), _visuel(), identifiant="t", nom="T")
    perso = u.personnages[0]
    assert perso.voix.voice_id == ""
    assert perso.voix.stabilite > 0.6      # « posé et las »


# ── Les vérifications de la charte ───────────────────────────────────────

def test_une_charte_sans_personnage_est_refusee():
    charte = _charte()
    charte["personnages"] = []
    with pytest.raises(ErreurValidation) as e:
        CharteVisuelle().apres(charte, {"visuel": _visuel()}, _contexte())
    assert "personnage" in str(e.value).lower()


def test_deux_personnages_ne_peuvent_pas_partager_un_identifiant():
    """Sinon ils partagent silencieusement voix et fiche image."""
    charte = _charte(2)
    charte["personnages"][1]["id"] = charte["personnages"][0]["id"]
    with pytest.raises(ErreurValidation) as e:
        CharteVisuelle().apres(charte, {"visuel": _visuel()}, _contexte())
    assert "deux fois" in str(e.value)


def test_une_apparence_trop_vague_est_refusee():
    """« a red stapler » ne permet pas de redessiner le personnage."""
    charte = _charte(1)
    charte["personnages"][0]["apparence"] = "a red stapler"
    with pytest.raises(ErreurValidation) as e:
        CharteVisuelle().apres(charte, {"visuel": _visuel()}, _contexte())
    assert "vague" in str(e.value)


def test_le_mode_transposition_exige_de_dire_ce_qui_change():
    charte = _charte(1)
    charte["transposition"] = []
    with pytest.raises(ErreurValidation):
        CharteVisuelle().apres(charte, {"visuel": _visuel(), "transposer": True},
                               _contexte())


# ── L'empreinte créative ─────────────────────────────────────────────────
# Le mécanisme d'attention d'une vidéo de référence, pas son contenu — voir
# `EmpreinteCreative` dans pdz/univers/modele.py.

def _champ(valeur="question impossible", confiance=0.8, justification="vu à l'image 1"):
    return {"valeur": valeur, "confiance": confiance, "justification": justification}


def _empreinte_brute():
    return {
        "hook": {"type": _champ("question impossible"),
                 "mecanisme": _champ("hypothèse personnelle"),
                 "promesse": _champ("une révélation avant la fin")},
        "narrative": {"structure": _champ("mise en place, escalade, révélation"),
                     "escalade": _champ("chaque plan ajoute une information"),
                     "fin": _champ("révélation ouverte")},
        "curiosite": _champ("question sans réponse évidente"),
        "arc_emotionnel": _champ("curiosité, inquiétude, tension"),
        "retention": _champ("chaque plan retient une information"),
        "visuel": {"style": _champ("cinématique, sombre"),
                  "cadrage": _champ("varie large puis serré"),
                  "son": _champ("voix posée, silences courts")},
        "principes_reutilisables": ["pose une question sans réponse avant la 3e seconde"],
        "fonctions_plans": [{"image": 1, "fonction": "établit l'échelle",
                             "raison": "plan large sur le décor"}],
    }


def test_une_charte_sans_empreinte_creative_est_refusee():
    """`creative_fingerprint` est la deuxième moitié de ce qu'une charte doit
    produire depuis la 1.1.0 — le style visuel ne suffit plus."""
    charte = _charte(1)
    charte["creative_fingerprint"] = {}
    with pytest.raises(ErreurValidation) as e:
        CharteVisuelle().apres(charte, {"visuel": _visuel()}, _contexte())
    assert "creative_fingerprint" in str(e.value)


def test_une_charte_avec_empreinte_creative_passe():
    charte = _charte(1)
    charte["creative_fingerprint"] = _empreinte_brute()
    sortie = CharteVisuelle().apres(charte, {"visuel": _visuel()}, _contexte())
    assert sortie["creative_fingerprint"]


def test_lempreinte_creative_arrive_sur_lunivers():
    charte = _charte(1)
    charte["creative_fingerprint"] = _empreinte_brute()
    u = vers_univers(charte, _visuel(), identifiant="t", nom="T")
    assert u.empreinte_creative is not None
    assert u.empreinte_creative.hook.type.valeur == "question impossible"
    assert u.empreinte_creative.hook.type.confiance == 0.8
    assert u.empreinte_creative.principes_reutilisables == [
        "pose une question sans réponse avant la 3e seconde"
    ]


def test_sans_creative_fingerprint_lunivers_na_pas_dempreinte():
    """Non-régression : une charte produite avec le prompt 1.0.0 (avant
    l'empreinte créative) continue de donner un univers utilisable."""
    u = vers_univers(_charte(1), _visuel(), identifiant="t", nom="T")
    assert u.empreinte_creative is None


def test_le_pacing_vient_de_ladn_jamais_du_modele():
    """La règle de partage s'applique aussi ici : un plan dure ce qu'il dure,
    indépendamment de ce qu'un modèle de vision en perçoit."""
    from pdz.analyse.adn import Adn

    adn = Adn(
        duree_s=45, duree_plan_s=1.8, coupes_par_minute=33.3,
        duree_premier_plan_s=1.5, plans_par_replique=2.0,
        debit_wpm=170, ratio_parole=0.9, relances_pct=[0.3, 0.6],
        courbe_energie=[0.5] * 12, palette=[], consignes_image=[],
    )
    charte = _charte(1)
    charte["creative_fingerprint"] = _empreinte_brute()
    u = vers_univers(charte, _visuel(), identifiant="t", nom="T", adn=adn)
    assert u.empreinte_creative.pacing["debit_wpm"] == 170


def test_un_champ_mal_forme_retombe_sur_unknown():
    """Défensif plutôt que strict : un champ manquant ne fait pas échouer
    tout l'univers pour une charte par ailleurs exploitable."""
    charte = _charte(1)
    brut = _empreinte_brute()
    brut["hook"]["type"] = {}
    charte["creative_fingerprint"] = brut
    u = vers_univers(charte, _visuel(), identifiant="t", nom="T")
    assert u.empreinte_creative.hook.type.valeur == "unknown"
    assert u.empreinte_creative.hook.type.confiance == 0.0


def test_lancien_nom_de_champ_justification_est_toujours_lu():
    """Le prompt charte 1.1.0 rendait `justification` ; le 1.2.0 rend
    `observation`. Une charte produite avant le renommage doit se relire
    sans perdre l'information."""
    charte = _charte(1)
    brut = _empreinte_brute()
    brut["hook"]["type"] = {"valeur": "question impossible", "confiance": 0.7,
                            "justification": "vu à l'image 1"}
    charte["creative_fingerprint"] = brut
    u = vers_univers(charte, _visuel(), identifiant="t", nom="T")
    assert u.empreinte_creative.hook.type.observation == "vu à l'image 1"


def test_une_charte_1_1_0_a_plat_se_relit_dans_les_nouveaux_groupes():
    """Non-régression : le prompt 1.1.0 rendait curiosite/arc_emotionnel/
    retention à la racine et `son` sous `visuel`. Le 1.2.0 les regroupe sous
    `psychologie` et `audio`. Une charte produite avant le regroupement doit
    continuer à alimenter l'univers, pas juste ne pas planter."""
    charte = _charte(1)
    charte["creative_fingerprint"] = {
        "hook": {"type": _champ("question impossible")},
        "narrative": {},
        # Forme À PLAT du prompt 1.1.0 — pas de clé « psychologie ».
        "curiosite": _champ("question sans réponse"),
        "arc_emotionnel": _champ("curiosité, tension"),
        "retention": _champ("chaque plan retient une info"),
        # « son » sous `visuel`, pas de clé « audio » — forme du 1.1.0.
        "visuel": {"son": _champ("voix posée")},
        "principes_reutilisables": [],
        "fonctions_plans": [],
    }
    u = vers_univers(charte, _visuel(), identifiant="t", nom="T")
    e = u.empreinte_creative
    assert e.psychologie.curiosite.valeur == "question sans réponse"
    assert e.psychologie.arc_emotionnel.valeur == "curiosité, tension"
    assert e.audio.voix.valeur == "voix posée"


# ── Prompts d'images ─────────────────────────────────────────────────────

def test_le_personnage_passe_avant_le_style_dans_le_prompt():
    """Les modèles d'image pondèrent le début du prompt. Inversé, on obtient
    de très belles images du mauvais personnage."""
    u = Univers.charger(FRUITS)
    perso = u.personnages[0]
    prompt = images.prompt_plan(perso, u, action="elle claque la porte",
                                emotion="colere")
    assert prompt.index(perso.apparence.split()[0]) < prompt.index(u.style.rendu[:12])


def test_les_interdits_de_lunivers_passent_avant_le_decor_et_le_style():
    """Mesuré à l'écran sur techno-holo : présents dans le prompt (voir
    test_les_consignes_de_lunivers_partent_dans_chaque_image) mais relégués
    en fin d'un prompt à 28 segments, « wireframe and transparent surfaces
    only, never solid rendered characters » ne pesait pas assez face à une
    action décrivant un humain — le personnage rendu était plein, pas
    filaire. Les interdits doivent passer immédiatement après l'action,
    avant le décor et le rendu général."""
    u = Univers.charger(HOLO)
    prompt = images.prompt_plan(u.personnages[0], u,
                                action="il marche dans la ville",
                                decor="silhouette")
    premiere_consigne = u.style.consignes_image[0]
    assert prompt.index(premiere_consigne) < prompt.index(u.decor("silhouette").description[:12])
    assert prompt.index(premiere_consigne) < prompt.index(u.style.rendu[:12])


def test_lemotion_devient_une_description_de_visage():
    """« angry » donne un visage contrarié ; les sourcils donnent la colère."""
    u = Univers.charger(FRUITS)
    prompt = images.prompt_plan(u.personnages[0], u, action="x", emotion="colere")
    assert "eyebrow" in prompt
    assert "colere" not in prompt          # rien de français ne part au modèle


def test_le_decor_demande_est_celui_utilise():
    u = Univers.charger(FRUITS)
    prompt = images.prompt_plan(u.personnages[0], u, action="x", decor="ceremonie")
    assert "torches" in prompt


def test_en_serie_animee_un_decor_absent_retombe_sur_le_premier():
    """Non-régression : sur une série à personnages, l'histoire se déroule
    forcément dans un des lieux définis — retomber sur le premier reste
    pertinent."""
    u = Univers.charger(FRUITS)
    prompt = images.prompt_plan(u.personnages[0], u, action="x", decor="")
    assert u.decors[0].description.strip() in prompt


def test_en_narration_un_decor_absent_ne_force_pas_le_premier():
    """Mesuré à l'écran : `techno-holo` n'a que 4 décors génériques (ville,
    réseau, objet, silhouette), qui ne couvrent pas un sujet libre. Un plan
    sur « un homme allongé regarde son téléphone » recevait quand même la
    description de la ville filaire, en plus de l'action — et l'image
    rendue montrait une ville, pas un téléphone. En narration, l'action est
    déjà la description de la scène ; imposer un décor générique en plus
    la pollue plutôt que de l'aider."""
    u = Univers.charger(HOLO)
    prompt = images.prompt_plan(
        u.personnages[0], u,
        action="un homme allonge sur son lit regarde lecran de son telephone",
        decor="",
    )
    assert u.decors[0].description.strip() not in prompt
    assert "telephone" in prompt


def test_le_shot_function_influence_le_prompt_dimage():
    """SHOT_FUNCTION (fonction_plan) était calculé par le scénariste puis
    jeté : présent dans le storyboard, jamais lu par la génération d'image.
    Sans ce fil, l'empreinte créative ne pèse sur rien de visible à l'écran —
    exactement ce que le test avant/après doit pouvoir vérifier."""
    u = Univers.charger(FRUITS)
    perso = u.personnages[0]
    sans = images.prompt_plan(perso, u, action="elle observe la pièce")
    avec = images.prompt_plan(perso, u, action="elle observe la pièce",
                              fonction="révèle un détail caché")
    assert sans != avec
    assert "révèle un détail caché" in avec


def test_deux_fonctions_differentes_donnent_des_prompts_differents():
    u = Univers.charger(FRUITS)
    perso = u.personnages[0]
    a = images.prompt_plan(perso, u, action="elle observe la pièce",
                           fonction="établit l'échelle du monde")
    b = images.prompt_plan(perso, u, action="elle observe la pièce",
                           fonction="fait monter la tension")
    assert a != b


def test_le_cadrage_ajoute_sa_formule_au_prompt():
    """ShotPromptWriter décrit déjà le cadrage en prose dans `action`, mais
    rien ne garantissait qu'un mot-clé de cadrage fiable atteigne vraiment
    le modèle d'image — voir pdz.production.cadrage.phrase()."""
    u = Univers.charger(FRUITS)
    perso = u.personnages[0]
    sans = images.prompt_plan(perso, u, action="elle observe la pièce")
    avec = images.prompt_plan(perso, u, action="elle observe la pièce",
                              cadrage="gros_plan")
    assert sans != avec
    assert "close-up shot" in avec


def test_un_cadrage_inconnu_najoute_rien():
    """Non-régression : un job en cache d'avant plans@1.2.0 n'a pas de
    cadrage — ne doit pas planter ni ajouter de texte parasite."""
    u = Univers.charger(FRUITS)
    perso = u.personnages[0]
    sans = images.prompt_plan(perso, u, action="elle observe la pièce")
    avec = images.prompt_plan(perso, u, action="elle observe la pièce", cadrage="")
    assert sans == avec


def test_le_cadrage_passe_avant_le_decor_et_le_style():
    u = Univers.charger(FRUITS)
    perso = u.personnages[0]
    prompt = images.prompt_plan(perso, u, action="elle observe la pièce",
                                cadrage="plan_large", decor="ceremonie")
    assert prompt.index("wide shot") < prompt.index(u.decor("ceremonie").description[:12])
    assert prompt.index("wide shot") < prompt.index(u.style.rendu[:12])


# ── registre_visuel : présence d'un objet ≠ bon registre visuel ──────────

def test_le_registre_visuel_sajoute_au_prompt():
    """Bug réel : un plan contenait bien « océans » et le générateur a
    quand même produit une carte géographique réaliste — le registre visuel
    doit être imposé explicitement, pas seulement les objets."""
    u = Univers.charger(FRUITS)
    perso = u.personnages[0]
    sans = images.prompt_plan(perso, u, action="un câble sous-marin")
    avec = images.prompt_plan(
        perso, u, action="un câble sous-marin",
        registre_visuel="abstract wireframe visualization, not a realistic map",
    )
    assert sans != avec
    assert "not a realistic map" in avec


def test_un_registre_visuel_vide_najoute_rien():
    """Non-régression : un job en cache d'avant plans@1.7.0 n'a pas ce
    champ — ne doit pas planter ni ajouter de texte parasite."""
    u = Univers.charger(FRUITS)
    perso = u.personnages[0]
    sans = images.prompt_plan(perso, u, action="elle observe la pièce")
    avec = images.prompt_plan(perso, u, action="elle observe la pièce", registre_visuel="")
    assert sans == avec


def test_le_registre_visuel_passe_avant_le_decor_et_le_style():
    u = Univers.charger(FRUITS)
    perso = u.personnages[0]
    prompt = images.prompt_plan(
        perso, u, action="elle observe la pièce", decor="ceremonie",
        registre_visuel="cinematic hand-drawn illustration",
    )
    assert prompt.index("cinematic hand-drawn") < prompt.index(u.decor("ceremonie").description[:12])
    assert prompt.index("cinematic hand-drawn") < prompt.index(u.style.rendu[:12])


# ── prompt_plan_depuis_contrat() : compile un ContratVisuel, ne réassemble
# jamais elle-même — verrous de non-régression sur prompt_plan() lui-même ──

def test_prompt_plan_produit_exactement_le_meme_resultat_quavant():
    """Chaîne figée : verrou explicite sur l'ordre d'assemblage de
    `prompt_plan()`, que le Visual Contract ne doit jamais changer."""
    u = Univers.charger(FRUITS)
    perso = u.personnages[0]
    prompt = images.prompt_plan(
        perso, u, action="elle observe la pièce", emotion="colere",
        decor="ceremonie", fonction="révèle un détail", cadrage="plan_large",
        registre_visuel="cinematic hand-drawn illustration",
    )
    attendu = ", ".join([
        perso.apparence,
        images.EXPRESSIONS["colere"],
        "elle observe la pièce",
        "wide shot",
        "cinematic hand-drawn illustration",
        "shot chosen to: révèle un détail",
        *u.style.consignes_image,
        u.decor("ceremonie").description,
        u.style.rendu,
        u.style.eclairage,
        "vertical 9:16 composition",
    ])
    assert prompt == attendu


def test_prompt_plan_depuis_contrat_egale_lappel_direct():
    """Le contrat compile vers exactement le même prompt que l'appel direct
    à `prompt_plan()` avec les mêmes valeurs logiques — la compilation ne
    change jamais le résultat, seulement sa forme d'entrée."""
    u = Univers.charger(FRUITS)
    perso = u.personnages[0]
    plan = PlanScript(
        numero=0, replique_numero=0, personnage=perso.id,
        action="elle observe la pièce", emotion="colere", decor="ceremonie",
        fonction="révèle un détail", cadrage="plan_large",
        registre_visuel="cinematic hand-drawn illustration",
        elements_obligatoires=["torch"],
    )

    direct = images.prompt_plan(
        perso, u, action=plan.action, emotion=plan.emotion, decor=plan.decor,
        fonction=plan.fonction, cadrage=plan.cadrage,
        registre_visuel=plan.registre_visuel,
    )
    contrat = contrat_visuel.compiler(plan, perso, u)
    depuis_contrat = images.prompt_plan_depuis_contrat(contrat, u)

    assert depuis_contrat == direct


def test_prompt_plan_depuis_contrat_najamais_de_registre_en_double():
    """Bug qu'on a failli introduire : `ContratVisuel.registre` est le
    plancher non négociable (jamais vide, retombe sur `style.rendu`), mais
    `prompt_plan()` ajoute déjà `style.rendu` sans condition plus loin dans
    l'assemblage. Compiler devait passer la valeur BRUTE du plan
    (`registre_visuel_plan`), pas le plancher — sinon `style.rendu`
    apparaît deux fois dans le prompt final."""
    u = Univers.charger(FRUITS)
    perso = u.personnages[0]
    plan = PlanScript(
        numero=0, replique_numero=0, personnage=perso.id,
        action="elle observe la pièce", emotion="calme", registre_visuel="",
    )
    contrat = contrat_visuel.compiler(plan, perso, u)
    prompt = images.prompt_plan_depuis_contrat(contrat, u)
    assert prompt.count(u.style.rendu) == 1


def test_la_fiche_de_personnage_est_neutre():
    """Une fiche prise en scène transmettrait ce décor à tous les plans."""
    u = Univers.charger(FRUITS)
    fiche = images.prompt_fiche(u.personnages[0], u)
    assert "plain flat" in fiche and "neutral" in fiche
    assert "villa" not in fiche


def test_regenerer_une_fiche_invalide_les_plans_du_personnage(tmp_path):
    """Sinon deux versions du même personnage cohabitent dans un épisode."""
    fiche = tmp_path / "fiche.jpg"
    fiche.write_bytes(b"version-1")
    avant = images._empreinte("un prompt", 42, fiche)
    fiche.write_bytes(b"version-2")
    apres = images._empreinte("un prompt", 42, fiche)
    assert avant != apres


def test_deux_prompts_identiques_partagent_la_meme_empreinte(tmp_path):
    assert images._empreinte("p", 1, None) == images._empreinte("p", 1, None)
    assert images._empreinte("p", 1, None) != images._empreinte("p", 2, None)


# ── Budget d'animation ───────────────────────────────────────────────────

def test_le_budget_prime_sur_le_chiffre_annonce_par_le_profil():
    """Un profil qui promet 6 animations sans regarder la caisse produit une
    facture surprise. Ici le nombre réel est calculé."""
    combien, raison = animation.combien_animer(20, budget_restant=0.10,
                                               profil="equilibre")
    assert combien < 6
    assert "budget" in raison


def test_un_budget_confortable_laisse_le_profil_decider():
    combien, raison = animation.combien_animer(20, budget_restant=100.0,
                                               profil="equilibre")
    assert combien == 6
    assert "profil" in raison


def test_le_profil_economique_nanime_rien():
    combien, raison = animation.combien_animer(20, budget_restant=100.0,
                                               profil="economique")
    assert combien == 0
    assert "désactivée" in raison


def test_on_nanime_jamais_plus_de_plans_quil_nen_existe():
    combien, _ = animation.combien_animer(2, budget_restant=100.0, profil="premium")
    assert combien == 2


# ── Narration : personne à l'écran ───────────────────────────────────────

HOLO = Path(__file__).resolve().parent.parent / "univers" / "techno-holo.yaml"


def test_en_narration_le_prompt_part_de_la_scene_pas_du_narrateur():
    """Une voix off ne se voit pas. Mettre son apparence en tête du prompt
    donnerait vingt portraits du même sujet là où il faut vingt scènes."""
    u = Univers.charger(HOLO)
    assert not u.anime
    prompt = images.prompt_plan(u.personnages[0], u,
                                action="a glowing wireframe city at night",
                                emotion="colere", decor="ville")
    assert prompt.startswith("a glowing wireframe city at night")
    assert u.personnages[0].apparence.split(",")[0] not in prompt
    # Aucune émotion : un visage qu'on ne voit pas n'a rien à jouer.
    assert "expression" not in prompt


def test_en_serie_animee_le_personnage_reste_en_tete():
    """Non-régression : c'est ce qui garde le personnage reconnaissable."""
    u = Univers.charger(FRUITS)
    perso = u.personnages[0]
    prompt = images.prompt_plan(perso, u, action="se retourne", emotion="colere")
    assert prompt.startswith(perso.apparence.split(",")[0])
    assert "expression" in prompt


def _prompts_de_scenes(u):
    return [images.prompt_plan(u.personnages[0], u, action=a, decor=d)
            for a, d in [("a wireframe city", "ville"),
                         ("a network of nodes", "reseau"),
                         ("a rotating object", "objet")]]


def test_en_narration_la_graine_varie_dun_plan_a_lautre():
    """Mesuré à l'écran : une graine fixe appliquée à vingt scènes
    différentes rendait la même ville filaire pendant tout l'épisode."""
    u = Univers.charger(HOLO)
    graines = {images.graine_du_plan(u, p) for p in _prompts_de_scenes(u)}
    assert len(graines) == 3, "chaque scène doit avoir sa propre graine"


def test_en_serie_animee_la_graine_reste_fixe():
    """Non-régression : c'est l'un des mécanismes qui gardent la patte
    graphique constante d'un plan à l'autre."""
    u = Univers.charger(FRUITS)
    graines = {
        images.graine_du_plan(u, images.prompt_plan(u.personnages[0], u, action=a))
        for a in ("se retourne", "crie", "sourit")
    }
    assert graines == {u.style.seed}


def test_la_graine_dun_plan_est_reproductible():
    """Sinon le cache ne servirait plus à rien : chaque reprise repaierait
    toutes les images."""
    u = Univers.charger(HOLO)
    prompt = _prompts_de_scenes(u)[0]
    assert images.graine_du_plan(u, prompt) == images.graine_du_plan(u, prompt)


def test_sans_graine_declaree_rien_nest_invente():
    u = Univers.charger(HOLO)
    u.style.seed = None
    assert images.graine_du_plan(u, "peu importe") is None


def test_les_consignes_de_lunivers_partent_dans_chaque_image():
    """Mesuré à l'écran : un univers qui interdit les visages en a vu
    apparaître un. `regles_du_monde` et `interdits` ne vont qu'à l'agent
    d'écriture — le générateur d'images ne les connaissait pas."""
    u = Univers.charger(HOLO)
    assert u.style.consignes_image, "l'univers doit poser ses interdits visuels"
    prompt = images.prompt_plan(u.personnages[0], u,
                                action="a wireframe city", decor="ville")
    for consigne in u.style.consignes_image:
        assert consigne in prompt


def test_les_consignes_de_lunivers_et_de_la_reference_se_cumulent():
    """Celles de l'univers valent toujours ; celles mesurées sur une vidéo
    de référence s'y ajoutent, elles ne les remplacent pas."""
    u = Univers.charger(HOLO)
    prompt = images.prompt_plan(u.personnages[0], u, action="x",
                                consignes=["heavy film grain"])
    assert "heavy film grain" in prompt
    assert u.style.consignes_image[0] in prompt


def test_un_univers_sans_consignes_dimage_marche_toujours():
    """Le champ est facultatif : les univers existants n'en ont pas."""
    u = Univers.charger(FRUITS)
    assert u.style.consignes_image == []
    assert images.prompt_plan(u.personnages[0], u, action="se retourne")


def test_la_narration_ne_produit_aucune_fiche(tmp_path):
    """La fiche servirait d'image de départ à chaque plan et rendrait toutes
    les scènes identiques — l'inverse du but recherché."""
    u = Univers.charger(HOLO)
    assert images.fiches(u, tmp_path) == {}


def test_un_echec_total_danimation_est_crie_pas_chuchote(monkeypatch, caplog,
                                                         tmp_path):
    """Une animation ratée est rattrapée en image fixe pour ne pas perdre
    l'épisode — au prix d'un silence qui a laissé passer un identifiant de
    modèle périmé pendant plusieurs productions. Un échec TOTAL doit sortir
    en ERROR, visible sans lire les journaux ligne à ligne."""
    from pdz.moteur.erreurs import ErreurValidation

    def _toujours_en_echec(*a, **k):
        raise ErreurValidation("endpoint introuvable")

    monkeypatch.setattr(animation.fal, "animer_image", _toujours_en_echec)

    u = Univers.charger(FRUITS)
    images = []
    for i in range(3):
        p = tmp_path / f"p{i}.jpg"
        Image.new("RGB", (64, 64), (10 * i, 60, 90)).save(p)
        images.append(p)
    plans = [{"numero": i, "personnage": u.personnages[0].id, "action": "parle",
              "emotion": "calme", "duree_s": 2.0} for i in range(3)]

    with caplog.at_level(logging.ERROR):
        resultats = animation.animer(
            plans, images, u, tmp_path / "anim", budget_restant=100.0,
            profil="equilibre", vie_pour_le_reste=False,
        )

    assert not any(r.anime for r in resultats), "aucune animation ne devait réussir"
    assert any(e.levelno >= logging.ERROR for e in caplog.records), \
        "un échec total d'animation doit remonter en ERROR"
    assert "AUCUN plan animé" in caplog.text


def test_un_clip_plus_court_que_prevu_retombe_sur_une_image_fixe(monkeypatch, tmp_path):
    """Bug réel (audit de l'épisode #56) : un fournisseur peut rendre un
    clip plus court que la durée allouée au plan. Le montage ne peut pas
    RALLONGER un clip trop court (`trim=duration=...` ne fait que couper) —
    laisser passer ça tronque la vidéo finale, silencieusement. Ici : 4,8 s
    demandées (sous le plafond de clip, donc le modèle est bien tenté), 4 s
    rendues → repli sur image fixe, jamais le clip court."""
    import subprocess

    def _clip_trop_court(image, prompt, destination, *, duree_s, **k):
        subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-t", "4", "-i", "color=c=blue:s=320x240:r=25",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(destination),
        ], check=True, capture_output=True)
        return destination, 0.23

    monkeypatch.setattr(animation.fal, "animer_image", _clip_trop_court)

    u = Univers.charger(FRUITS)
    p = tmp_path / "p0.jpg"
    Image.new("RGB", (64, 64), (10, 60, 90)).save(p)
    plans = [{"numero": 0, "personnage": u.personnages[0].id, "action": "parle",
             "emotion": "colere", "duree_s": 4.8}]

    resultats = animation.animer(
        plans, [p], u, tmp_path / "anim", budget_restant=100.0,
        profil="equilibre", vie_pour_le_reste=False,
    )

    assert resultats[0].methode != "modele", (
        "un clip plus court que la durée allouée ne doit jamais être gardé "
        "tel quel — le montage le tronquerait"
    )


def test_un_clip_assez_long_avec_mouvement_est_garde(monkeypatch, tmp_path):
    """Non-régression : un clip qui couvre bien la durée demandée ET
    contient un vrai mouvement doit toujours être accepté normalement.
    `testsrc` (motif animé), pas `color` (image fixe) — un clip de bonne
    durée mais statique doit désormais être rejeté (voir le test dédié)."""
    import subprocess

    def _clip_ok(image, prompt, destination, *, duree_s, **k):
        subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-t", "5", "-i", "testsrc=size=320x240:rate=25",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(destination),
        ], check=True, capture_output=True)
        return destination, 0.23

    monkeypatch.setattr(animation.fal, "animer_image", _clip_ok)

    u = Univers.charger(FRUITS)
    p = tmp_path / "p0.jpg"
    Image.new("RGB", (64, 64), (10, 60, 90)).save(p)
    plans = [{"numero": 0, "personnage": u.personnages[0].id, "action": "parle",
             "emotion": "colere", "duree_s": 4.7}]

    resultats = animation.animer(
        plans, [p], u, tmp_path / "anim", budget_restant=100.0,
        profil="equilibre", vie_pour_le_reste=False,
    )

    assert resultats[0].methode == "modele"
    assert resultats[0].anime is True
    assert resultats[0].diagnostic == "mouvement_confirme"


def test_un_clip_de_bonne_duree_mais_statique_est_rejete(monkeypatch, tmp_path):
    """Cœur de l'enquête run #66 : un clip peut être un fichier vidéo
    valide, de la bonne durée, et pourtant visuellement statique — l'API a
    répondu 200, mais ce n'est pas une animation. `methode == "modele"` ne
    doit plus jamais être vrai pour un clip sans mouvement détecté."""
    import subprocess

    def _clip_statique(image, prompt, destination, *, duree_s, **k):
        subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-t", "5", "-i", "color=c=blue:s=320x240:r=25",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(destination),
        ], check=True, capture_output=True)
        return destination, 0.23

    monkeypatch.setattr(animation.fal, "animer_image", _clip_statique)

    u = Univers.charger(FRUITS)
    p = tmp_path / "p0.jpg"
    Image.new("RGB", (64, 64), (10, 60, 90)).save(p)
    plans = [{"numero": 0, "personnage": u.personnages[0].id, "action": "parle",
             "emotion": "colere", "duree_s": 4.7}]

    resultats = animation.animer(
        plans, [p], u, tmp_path / "anim", budget_restant=100.0,
        profil="equilibre", vie_pour_le_reste=False,
    )

    assert resultats[0].methode != "modele"
    assert resultats[0].diagnostic == "rejete_mouvement"


def test_un_clip_paye_puis_rejete_garde_son_cout(monkeypatch, tmp_path):
    """Fuite budgétaire mesurée sur le run #66 : 0,900 € réellement dépensés,
    0,200 € comptabilisés. `_repli()` renvoyait `PlanAnime(cout=0.0)`, donc
    `sum(a.cout for a in animes)` (episode.py) n'additionnait que les clips
    ACCEPTÉS — alors que le plafond budgétaire est vérifié contre ce total.
    Un clip payé puis écarté a coûté malgré tout."""
    import subprocess

    def _clip_statique(image, prompt, destination, *, duree_s, **k):
        subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-t", "5", "-i", "color=c=blue:s=320x240:r=25",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(destination),
        ], check=True, capture_output=True)
        return destination, 0.18

    monkeypatch.setattr(animation.fal, "animer_image", _clip_statique)

    u = Univers.charger(FRUITS)
    p = tmp_path / "p0.jpg"
    Image.new("RGB", (64, 64), (10, 60, 90)).save(p)
    plans = [{"numero": 0, "personnage": u.personnages[0].id, "action": "parle",
             "emotion": "colere", "duree_s": 4.7}]

    resultats = animation.animer(
        plans, [p], u, tmp_path / "anim", budget_restant=100.0,
        profil="equilibre", vie_pour_le_reste=True,
    )

    assert resultats[0].diagnostic == "rejete_mouvement"
    assert resultats[0].methode != "modele"
    # C'est CE total que `episode.py` additionne.
    assert sum(r.cout for r in resultats) == pytest.approx(0.18)


def test_un_enregistrement_danimation_davant_ce_lot_se_reprend_sans_planter():
    """`cout` et `diagnostic` viennent d'être ajoutés à ce que `_noter()`
    écrit. Un job mis en cache AVANT ne les a pas : la reprise doit repartir
    avec des valeurs neutres plutôt que lever un KeyError — c'est la
    régression que ce lot pourrait introduire."""
    ancien = {"index": 0, "fichier": "/tmp/anime_000.mp4",
              "anime": True, "methode": "modele"}

    repris = animation.PlanAnime(
        ancien["index"], Path(ancien["fichier"]), ancien["anime"],
        ancien["methode"], ancien.get("cout", 0.0),
        diagnostic=ancien.get("diagnostic", ""),
    )

    assert repris.cout == 0.0
    assert repris.diagnostic == ""
    assert repris.methode == "modele"


def test_un_plan_jamais_tente_ne_coute_rien(monkeypatch, tmp_path):
    """Symétrie du test précédent : le report de coût ne doit pas inventer
    de dépense là où aucun appel payant n'a eu lieu."""
    def _jamais_appele(*a, **k):
        raise AssertionError("aucun appel payant ne doit partir ici")

    monkeypatch.setattr(animation.fal, "animer_image", _jamais_appele)

    u = Univers.charger(FRUITS)
    p = tmp_path / "p0.jpg"
    Image.new("RGB", (64, 64), (10, 60, 90)).save(p)
    # Plus long que ce que le modèle rend réellement → repli avant tout appel.
    plans = [{"numero": 0, "personnage": u.personnages[0].id, "action": "parle",
             "emotion": "colere", "duree_s": animation.DUREE_REELLE_MAX_S + 2}]

    resultats = animation.animer(
        plans, [p], u, tmp_path / "anim", budget_restant=100.0,
        profil="equilibre", vie_pour_le_reste=True,
    )

    assert resultats[0].diagnostic == "hors_portee"
    assert resultats[0].cout == 0.0


def test_un_plan_plus_long_que_le_clip_saute_lappel_paye(monkeypatch, tmp_path):
    """Bug réel (production épisode #57, puis #65 à un plafond plus large) :
    un plan qui a besoin de plus que `DUREE_CLIP_S` était quand même envoyé
    au modèle, qui ne rend jamais plus que ce qui est demandé (mesuré :
    4,84 s pour 5 s demandés, cinq fois de suite sur cet épisode) —
    l'appel payant était donc voué à échouer à chaque fois. Le repli doit
    être pris directement, sans dépenser ni attendre pour un clip qui sera
    de toute façon rejeté."""
    appele = {"n": 0}

    def _jamais_appele(*a, **k):
        appele["n"] += 1
        raise AssertionError("le modèle ne doit pas être appelé pour ce plan")

    monkeypatch.setattr(animation.fal, "animer_image", _jamais_appele)

    u = Univers.charger(FRUITS)
    p = tmp_path / "p0.jpg"
    Image.new("RGB", (64, 64), (10, 60, 90)).save(p)
    plans = [{"numero": 0, "personnage": u.personnages[0].id, "action": "parle",
             "emotion": "colere", "duree_s": 12.99}]

    resultats = animation.animer(
        plans, [p], u, tmp_path / "anim", budget_restant=100.0,
        profil="equilibre", vie_pour_le_reste=True,
    )

    assert appele["n"] == 0
    assert resultats[0].methode == "vie"


def test_le_repli_local_couvre_toute_la_duree_du_plan(monkeypatch, tmp_path):
    """Bug réel (production épisode #57) : le repli local (`vie.animer()`,
    sans limite de durée technique) était plafonné à `DUREE_CLIP_S` par un
    `min(duree, duree_clip_s)` — sur cinq plans de 6-7 s dans un même
    épisode, l'écart cumulé (6,3 s) a produit une vidéo finale plus courte
    que la voix, bloquée par la vérification de durée."""
    from pdz.analyse.sonde import sonder

    u = Univers.charger(FRUITS)
    p = tmp_path / "p0.jpg"
    Image.new("RGB", (64, 64), (10, 60, 90)).save(p)
    plans = [{"numero": 0, "personnage": u.personnages[0].id, "action": "parle",
             "emotion": "colere", "duree_s": 6.99}]

    resultats = animation.animer(
        plans, [p], u, tmp_path / "anim", budget_restant=100.0,
        profil="economique", vie_pour_le_reste=True,
    )

    assert resultats[0].methode == "vie"
    assert sonder(resultats[0].fichier).duree_s == pytest.approx(6.99, abs=0.15)


def test_lepisode_annonce_combien_de_plans_sont_animes():
    """« aucune animation » dans le résumé est une information : son absence
    a longtemps caché que rien n'était animé."""
    from pdz.production.episode import Episode

    muet = Episode(job_id="j", titre="T", video=Path("v.mp4"), duree_s=20.0,
                   cout=0.1, plans_animes=0)
    assert "aucune animation" in muet.resume()

    anime = Episode(job_id="j", titre="T", video=Path("v.mp4"), duree_s=20.0,
                    cout=0.5, plans_animes=2)
    assert "2 plan(s) animé(s)" in anime.resume()


SEUIL_MOTS_PROMPT_MOUVEMENT = 45

# Un `action` réaliste : ce que `ShotPromptWriter.fusionner()` produit
# vraiment sur un plan riche, une fois `elements_obligatoires`, `relations`,
# `geometrie` et la clause de priorité compilés dedans. ~65 mots.
_ACTION_REALISTE = (
    "a futuristic passenger airliner climbing into the sky just after takeoff, "
    "featuring runway, airport, flight path originates at the aircraft, curves "
    "upward to the right, glowing blue holographic line, airliner, centered in "
    "the frame, in the foreground, runway, near the bottom of the frame, in the "
    "foreground, airport, centered in the frame, in the background, airliner as "
    "the visual focus, fog secondary in the frame"
)


def test_le_prompt_de_mouvement_reste_court_et_protege_le_personnage():
    """Un prompt long fait refabriquer la scène au lieu de l'animer."""
    u = Univers.charger(FRUITS)
    prompt = animation._prompt_mouvement(
        {"emotion": "colere", "action": "elle jette un verre"}, u
    )
    assert len(prompt.split()) < SEUIL_MOTS_PROMPT_MOUVEMENT
    assert "identical" in prompt


# Pire cas MESURÉ (les quatre champs de mouvement remplis au maximum, plus
# `geometrie`, registre et ambiance) : 71 mots. Historique du plafond, parce
# qu'il ne s'agit pas d'un glissement mais de deux décisions distinctes :
#
#   119 → 52 : retrait de `action`, le prompt d'IMAGE (~65 mots de DESCRIPTION
#              DE SCÈNE) qui était réinjecté ici et faisait refabriquer.
#    52 → 71 : ajout, par le compilateur de prompt (`motion_program`), de
#              l'ouverture « animate this still image » et des blocs de
#              PRÉSERVATION et d'INTERDICTION.
#
# Le second n'annule pas le premier : ces mots-là ne décrivent pas la scène,
# ils disent au modèle ce qu'il n'a pas le droit d'y changer — c'est-à-dire
# exactement le contraire de ce qui avait été retiré. Ce plafond continue de
# garder la vraie régression : que `action` revienne.
PLAFOND_MOTS_PIRE_CAS = 72


def test_un_plan_riche_reste_sous_le_seuil_et_ne_redecrit_pas_la_scene():
    """Le vrai cas de production, pas un plan minimal.

    Le test précédent n'exerçait qu'un plan à deux champs : il passait au
    vert pendant que la production réelle atteignait 119 mots (2,6× le
    seuil), parce que `action` — le prompt d'IMAGE, ~65 mots — était
    réinjecté ici. En image→vidéo, l'image d'entrée porte déjà la scène ;
    la redécrire fait refabriquer au lieu d'animer."""
    u = Univers.charger(FRUITS)
    prompt = animation._prompt_mouvement(
        {"emotion": "calme",
         "action": _ACTION_REALISTE,
         "mouvement_sujet": "the airliner climbs steadily, engines glow brighter, "
                            "condensation trails expand behind the wings",
         "mouvement_camera": "push_in_lent",
         "mouvement_environnement": "ground fog drifts laterally, holographic "
                                    "particles rise slowly",
         "intensite_mouvement": "fort",
         # Déclenche l'invariant « relative object placement » : sans lui, ce
         # test mesurait un pire cas qui n'en était pas un.
         "geometrie": [{"objet": "airliner", "ancre": "centre"}],
         "registre_visuel": "abstract wireframe hologram, not a photorealistic render"},
        u,
    )

    # Bien en deçà des 119 mots d'avant le correctif : c'est le retrait de
    # `action` qui fait la différence, et c'est ça que ce plafond garde.
    assert len(prompt.split()) <= PLAFOND_MOTS_PIRE_CAS
    # Aucun fragment de la description de scène ne doit se retrouver ici.
    assert "centered in the frame" not in prompt
    assert "visual focus" not in prompt
    assert _ACTION_REALISTE not in prompt
    # Mais les décisions de MOUVEMENT, elles, doivent toutes être présentes.
    assert "the airliner climbs steadily" in prompt
    assert "camera performs a slow forward push-in" in prompt
    assert "ground fog drifts laterally" in prompt
    assert "clearly visible, unmistakable motion throughout" in prompt


def test_le_prompt_de_mouvement_porte_le_registre_visuel_du_plan():
    """`registre_visuel` (où vit `disposition`, ex. « technical-cutaway »)
    n'atteignait jamais ce prompt-ci — un plan animé pouvait dériver de son
    registre en cours de clip, faute de ce signal (voir animation.py)."""
    u = Univers.charger(FRUITS)
    prompt = animation._prompt_mouvement(
        {"emotion": "calme", "action": "a wireframe mechanism exposed",
         "registre_visuel": "abstract wireframe, not a realistic map"},
        u,
    )
    assert "abstract wireframe, not a realistic map" in prompt


def test_le_prompt_de_mouvement_ne_double_pas_un_registre_deja_couvert():
    """Non-remplissage : si `mouvement_sujet` mentionne déjà le registre en
    toutes lettres, `registre_visuel` n'est pas rajouté une seconde fois."""
    u = Univers.charger(FRUITS)
    prompt = animation._prompt_mouvement(
        {"emotion": "calme",
         "mouvement_sujet": "the mechanism unfolds, abstract wireframe rendering",
         "registre_visuel": "abstract wireframe rendering"},
        u,
    )
    assert prompt.lower().count("abstract wireframe rendering") == 1


def test_le_prompt_de_mouvement_sans_registre_visuel_ne_change_rien():
    """Non-régression : un plan sans `registre_visuel` (job en cache
    d'avant plans@1.7.0, ou plan qui n'en précise simplement aucun) ne doit
    ni planter ni ajouter de clause vide."""
    u = Univers.charger(FRUITS)
    prompt = animation._prompt_mouvement(
        {"emotion": "calme", "action": "elle sourit"}, u
    )
    assert "maintain style" not in prompt


# ── mouvement_sujet/camera/environnement/intensite (plans@1.13.0) ────────

def test_mouvement_sujet_remplace_le_vocabulaire_par_emotion():
    """Cas pédale (dossier « Animation 2.0 ») : une vraie décision de
    mouvement écrite par ShotPromptWriter remplace le dictionnaire fixe par
    émotion, jamais l'inverse."""
    u = Univers.charger(FRUITS)
    prompt = animation._prompt_mouvement(
        {"emotion": "calme", "action": "an accelerator pedal glowing in the dark",
         "mouvement_sujet": "the pedal moves downward smoothly, mechanical "
                            "linkage follows, energy pulses travel along the cables"},
        u,
    )
    assert "the pedal moves downward smoothly" in prompt
    assert "subtle idle motion" not in prompt


def test_sans_mouvement_sujet_le_repli_par_emotion_sapplique_toujours():
    """Non-régression : un job en cache d'avant plans@1.13.0, ou un plan où
    le modèle n'a rien décidé de plus précis, retombe sur l'ancien
    vocabulaire — jamais un prompt vide."""
    u = Univers.charger(FRUITS)
    prompt = animation._prompt_mouvement({"emotion": "joie", "action": "elle danse"}, u)
    assert "the character laughs, body bouncing" in prompt


def test_mouvement_camera_remplace_camera_holds_steady():
    u = Univers.charger(FRUITS)
    prompt = animation._prompt_mouvement(
        {"emotion": "calme", "action": "a rocket on the launchpad",
         "mouvement_camera": "push_in_lent"},
        u,
    )
    assert "camera performs a slow forward push-in" in prompt
    assert "camera holds steady" not in prompt


def test_sans_mouvement_camera_aucune_phrase_de_camera_nest_ajoutee():
    """Le schéma demande au modèle de laisser `mouvement_camera` vide quand
    aucun mouvement de caméra n'apporte rien à ce plan. Traduire ce vide en
    « camera holds steady » revenait à instruire l'immobilité sur la
    majorité des plans — l'inverse de ce que le champ vide veut dire."""
    u = Univers.charger(FRUITS)
    prompt = animation._prompt_mouvement({"emotion": "calme", "action": "x"}, u)
    assert "camera" not in prompt


def test_mouvement_camera_fixe_explicite_fige_bien_la_camera():
    """« fixe » est un CHOIX, pas une absence de choix : là, la consigne
    d'immobilité est légitime et doit bien partir."""
    u = Univers.charger(FRUITS)
    prompt = animation._prompt_mouvement(
        {"emotion": "calme", "action": "x", "mouvement_camera": "fixe"}, u
    )
    assert "camera holds steady" in prompt


def test_mouvement_environnement_est_ajoute_au_prompt():
    u = Univers.charger(FRUITS)
    prompt = animation._prompt_mouvement(
        {"emotion": "calme", "action": "x",
         "mouvement_environnement": "holographic particles drift slowly"},
        u,
    )
    assert "holographic particles drift slowly" in prompt


def test_intensite_forte_ajoute_une_clause_de_visibilite():
    u = Univers.charger(FRUITS)
    prompt = animation._prompt_mouvement(
        {"emotion": "calme", "action": "x", "intensite_mouvement": "fort"}, u
    )
    assert "clearly visible, unmistakable motion throughout" in prompt


def test_intensite_faible_najoute_rien_de_plus():
    u = Univers.charger(FRUITS)
    prompt = animation._prompt_mouvement(
        {"emotion": "calme", "action": "x", "intensite_mouvement": "faible"}, u
    )
    assert "clearly visible" not in prompt


def test_le_prompt_de_mouvement_purge_le_vocabulaire_facial_interdit():
    """Univers avec `no human faces` : le repli par émotion « calme »
    (« slight breathing, eyes blinking ») déclenche une contrainte
    négative corrective — même sur le vocabulaire hérité, pas seulement
    sur les nouveaux champs (voir `risque_prompt.purger_mouvement_interdit`)."""
    techno = Univers.charger(Path("univers/techno-holo.yaml"))
    prompt = animation._prompt_mouvement({"emotion": "calme", "action": "x"}, techno)
    assert "no breathing motion" in prompt
    assert "no blinking eyes" in prompt


def test_le_prompt_de_mouvement_univers_sans_interdit_facial_reste_inchange():
    """Univers qui n'interdit pas les visages (fruit-island) : aucune
    contrainte n'est ajoutée, coût zéro."""
    u = Univers.charger(FRUITS)
    prompt = animation._prompt_mouvement({"emotion": "calme", "action": "x"}, u)
    assert "no breathing motion" not in prompt


# ── Appariement de voix ──────────────────────────────────────────────────

def _profil(hauteur, debit=5.0, etendue=6.0, timbre=1500.0):
    return ProfilVoix(
        hauteur_hz=hauteur, hauteur_p10=hauteur * 0.9, hauteur_p90=hauteur * 1.1,
        etendue_demi_tons=etendue, stabilite_hz=1.0, timbre_hz=timbre,
        debit_syllabes_s=debit, ratio_parole=0.8, dynamique_db=6.0,
        voisement=0.4, duree_s=10.0, confiance=1.0,
    )


class _VoixFactice:
    def __init__(self, id_, nom):
        self.id, self.nom, self.langue, self.genre, self.usage = id_, nom, "fr", "", ""


def test_la_vitesse_corrige_lecart_pas_la_cible():
    """Reprendre la vitesse de la cible corrigerait une erreur inexistante.

    Ce qu'il faut, c'est de combien la voix retenue parle trop vite ou trop
    lentement — donc un rapport entre les deux mesures.
    """
    candidat = Candidat(
        voix=_VoixFactice("v1", "Voix"),
        profil=_profil(140, debit=4.0),     # la candidate parle lentement
        cible=_profil(140, debit=6.0),      # la cible parle vite
        distance=0.1, fichier=Path("x.mp3"),
    )
    assert candidat.reglages()["vitesse"] > 1.0


def test_le_jeu_vient_de_la_cible_pas_de_la_candidate():
    expressive = Candidat(
        voix=_VoixFactice("v", "V"), profil=_profil(140, etendue=3.0),
        cible=_profil(140, etendue=14.0), distance=0.1, fichier=Path("x.mp3"),
    )
    assert expressive.reglages()["style"] > 0.6


def test_la_vitesse_reste_dans_ce_que_le_moteur_encaisse():
    extreme = Candidat(
        voix=_VoixFactice("v", "V"), profil=_profil(140, debit=1.0),
        cible=_profil(140, debit=9.0), distance=0.1, fichier=Path("x.mp3"),
    )
    assert extreme.reglages()["vitesse"] <= 1.25


def test_sans_audio_de_reference_seule_la_hauteur_compte():
    """Un profil supposé a une confiance nulle : ses autres axes sont du
    remplissage, les pondérer reviendrait à choisir sur une invention."""
    suppose = profil_suppose(120.0)
    assert suppose.confiance == 0.0

    proche = _profil(122.0, timbre=3000.0, etendue=15.0)
    loin = _profil(230.0, timbre=1500.0, etendue=6.0)

    def d(autre):
        ecart = np.abs(suppose.vecteur() - autre.vecteur())
        return float(np.sqrt(((ecart * POIDS_HAUTEUR_SEULE) ** 2).sum()))

    assert d(proche) < d(loin)


# ── Choisir une voix sans audio de référence ─────────────────────────────

def test_le_registre_inscrit_dans_lunivers_est_suivi():
    from pdz.production.appariement_voix import hauteur_attendue
    from pdz.univers import Personnage, Voix

    grave = Personnage(id="a", nom="A", espece="x", apparence="y",
                       voix=Voix(registre_percu="grave"))
    aigu = Personnage(id="b", nom="B", espece="x", apparence="y",
                      voix=Voix(registre_percu="aigu"))
    assert hauteur_attendue(grave, 0, 2) < hauteur_attendue(aigu, 1, 2)


def test_sans_registre_les_personnages_sont_etales():
    """Sinon tous visent la même hauteur, reçoivent des voix voisines, et le
    dialogue devient impossible à suivre."""
    from pdz.production.appariement_voix import hauteur_attendue
    from pdz.univers import Personnage

    persos = [Personnage(id=f"p{i}", nom=f"P{i}", espece="x", apparence="y")
              for i in range(4)]
    hauteurs = [hauteur_attendue(p, i, len(persos)) for i, p in enumerate(persos)]
    assert len(set(hauteurs)) == len(hauteurs)
    assert min(hauteurs) >= 110 and max(hauteurs) <= 255


# ── decision_visuelle : diagnostic seulement, jamais un coût de plus ─────

def test_fabriquer_journalise_les_faits_de_decision_visuelle_sans_rien_changer(
    monkeypatch, tmp_path, caplog,
):
    """Un plan dont la relation vise un objet non désigné doit produire une
    ligne de log « décision visuelle » — mais ni le prompt envoyé au
    fournisseur d'image, ni le coût, ne doivent en dépendre : c'est un
    diagnostic (voir `pdz.production.decision_visuelle`), jamais une
    correction ni un appel de plus."""
    import logging

    appels = []

    def fausse_image(prompt, destination, **kwargs):
        appels.append(prompt)
        Image.new("RGB", (64, 64), (10, 60, 90)).save(destination)
        return destination, 0.001

    monkeypatch.setattr(images.ia_images, "generer_image", fausse_image)

    u = Univers.charger(FRUITS)
    plan = PlanScript(
        numero=0, replique_numero=0, personnage=u.personnages[0].id,
        action="strawberina holds a golden trophy", emotion="joie",
        elements_obligatoires=["golden trophy"],
        relations=[{"cible": "spotlight beam", "etat": "sweeping across"}],
    )

    with caplog.at_level(logging.INFO):
        planche = images.fabriquer([plan], u, tmp_path / "images", cache=False)

    assert any("décision visuelle" in m and "orpheline" in m for m in caplog.messages)
    # Les fiches de personnages de l'univers sont aussi produites par
    # `fabriquer()` (un appel par personnage) — seul le DERNIER appel
    # correspond au plan lui-même.
    assert planche.plans[0].prompt == appels[-1]
    assert planche.cout == pytest.approx(0.001)


def test_fabriquer_sans_incoherence_ne_journalise_aucune_decision_visuelle(
    monkeypatch, tmp_path, caplog,
):
    import logging

    def fausse_image(prompt, destination, **kwargs):
        Image.new("RGB", (64, 64), (10, 60, 90)).save(destination)
        return destination, 0.001

    monkeypatch.setattr(images.ia_images, "generer_image", fausse_image)

    u = Univers.charger(FRUITS)
    plan = PlanScript(
        numero=0, replique_numero=0, personnage=u.personnages[0].id,
        action="strawberina holds a golden trophy", emotion="joie",
        elements_obligatoires=["golden trophy"],
    )

    with caplog.at_level(logging.INFO):
        images.fabriquer([plan], u, tmp_path / "images", cache=False)

    assert not any("décision visuelle" in m for m in caplog.messages)
