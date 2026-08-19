"""Le pont ancien → contrat ne perd rien, et n'invente rien.

Deux propriétés à tenir, et la seconde compte autant que la première :

  · **ne rien perdre** — les timings, les listes, les décisions traversent ;
  · **ne rien inventer** — un champ que l'ancienne structure ne porte pas
    reste VIDE. Le remplir par défaut ferait répondre `est_specifie == True`
    à toute la production existante, rendant la mesure inutile le jour même
    de son introduction.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pdz.adaptateurs import (
    audio_timeline,
    camera_program,
    motion_program,
    perceptual_contract,
    shot_graph,
    shot_spec,
)
from pdz.contracts import ControleCamera, MouvementCamera
from pdz.production.contrat_visuel import ContratVisuel
from pdz.production.motion_program import ControleCamera as ControleLegacy
from pdz.production.motion_program import MotionProgram as MotionLegacy
from pdz.production.storyboard import PlanScript
from pdz.production.voix import BandeVoix, RepliqueDite
from pdz.video.soustitres import Mot as MotLegacy


def _plan(**extra) -> PlanScript:
    base = dict(numero=3, replique_numero=2, personnage="strawberina",
                action="se retourne", emotion="colere", decor="villa",
                duree_s=2.4)
    return PlanScript(**{**base, **extra})


# ── ShotSpec : ce qui traverse ───────────────────────────────────────────

def test_le_plan_traverse_sans_perte():
    plan = _plan(cadrage="gros_plan", registre_visuel="wireframe",
                 fonction="fait monter la tension", disposition="centre",
                 elements_obligatoires=["rotor", "aimant"],
                 elements_a_exclure=["texte lisible"],
                 elements_secondaires=["fond flou"])
    spec = shot_spec(plan)

    assert spec.numero == 3
    assert spec.duree_s == 2.4
    assert spec.sujet == "strawberina"
    assert spec.decor == "villa"
    assert spec.cadrage == "gros_plan"
    assert spec.registre_visuel == "wireframe"
    assert spec.fonction == "fait monter la tension"
    assert spec.disposition == "centre"
    assert spec.elements_obligatoires == ("rotor", "aimant")
    assert spec.elements_a_exclure == ("texte lisible",)
    assert spec.entites_secondaires == ("fond flou",)
    assert spec.emotion == "colere"


def test_l_identifiant_est_stable_et_lisible():
    assert shot_spec(_plan(numero=7)).id == "shot_007"


# ── ShotSpec : ce qui n'est PAS inventé ──────────────────────────────────

def test_un_plan_ordinaire_n_est_pas_declare_specifie():
    """LA propriété qui rend la mesure utile.

    Aucun `PlanScript` du dépôt ne porte de `but` ni d'`etat_apres`. Si
    l'adaptateur les fabriquait, `est_specifie` répondrait `True` partout et
    ne mesurerait plus rien.
    """
    spec = shot_spec(_plan(elements_obligatoires=["rotor"]))
    assert spec.but == ""
    assert spec.etat_avant == "" and spec.etat_apres == ""
    assert not spec.est_specifie


def test_un_plan_sans_mouvement_ne_recoit_aucun_critere_de_mouvement():
    """La vérification de mouvement ne s'applique qu'aux plans animés :
    lui en donner un le ferait échouer à tort."""
    sondes = {c.sonde for c in shot_spec(_plan()).criteres_reussite}
    assert "verification_mouvement" not in sondes


def test_un_plan_avec_mouvement_recoit_son_critere():
    spec = shot_spec(_plan(mouvement_sujet="tourne la tête"))
    mouvement = [c for c in spec.criteres_reussite if c.sonde == "verification_mouvement"]
    assert len(mouvement) == 1 and mouvement[0].obligatoire


def test_le_critere_d_exclusion_n_est_pas_bloquant():
    """`qa_image` ne tourne que sur les plans à risque et rend souvent
    `UNCERTAIN` : en faire une condition obligatoire bloquerait des plans
    que personne n'a regardés."""
    spec = shot_spec(_plan(elements_a_exclure=["logo"]))
    exclusion = [c for c in spec.criteres_reussite if c.sonde == "qa_image"]
    assert len(exclusion) == 1 and not exclusion[0].obligatoire


def test_un_plan_vide_ne_recoit_aucun_critere():
    assert shot_spec(_plan()).criteres_reussite == ()


# ── ShotGraph : les arêtes viennent de faits, pas de suppositions ────────

def test_un_plan_de_reaction_est_relie_au_plan_parlant():
    plans = [_plan(numero=1), _plan(numero=2, reaction=True)]
    assert shot_graph(plans).aretes == (("shot_001", "shot_002", "reaction"),)


def test_deux_plans_du_meme_decor_sont_relies_en_continuite():
    plans = [_plan(numero=1, decor="villa"), _plan(numero=2, decor="villa")]
    assert shot_graph(plans).aretes == (("shot_001", "shot_002", "continuite"),)


def test_un_changement_de_decor_ne_cree_aucune_arete():
    plans = [_plan(numero=1, decor="villa"), _plan(numero=2, decor="plage")]
    assert shot_graph(plans).aretes == ()


def test_un_decor_vide_ne_cree_pas_de_fausse_continuite():
    """Deux plans sans décor précisé ne sont pas « dans le même décor » —
    c'est l'absence d'information, pas une identité."""
    plans = [_plan(numero=1, decor=""), _plan(numero=2, decor="")]
    assert shot_graph(plans).aretes == ()


def test_le_graphe_conserve_la_duree_totale():
    plans = [_plan(numero=1, duree_s=2.0), _plan(numero=2, duree_s=1.5)]
    assert shot_graph(plans).duree_totale_s == pytest.approx(3.5)


def test_un_graphe_vide_ne_casse_pas():
    graphe = shot_graph([])
    assert graphe.plans == () and graphe.aretes == ()


# ── Mouvement et caméra : la séparation ──────────────────────────────────

def _legacy(**extra) -> MotionLegacy:
    base = dict(shot_id="4", duree_s=3.0, action="se retourne",
                camera="camera pans slowly across the scene",
                camera_controle=ControleLegacy.TEXTE_SEULEMENT,
                environnement="poussière en suspension", intensite="fort",
                cible_perceptuelle="viewer_must_perceive_camera_movement",
                doit_preserver=("subject identity",), peut_changer=("subject motion",),
                interdit=("new objects",), registre="wireframe")
    return MotionLegacy(**{**base, **extra})


def test_le_mouvement_traverse_sans_la_camera():
    """La séparation EST la fonctionnalité : tant que caméra et sujet
    vivent dans le même champ, aucun diagnostic ne peut dire « ça bouge,
    mais c'est la caméra »."""
    m = motion_program(_legacy())
    assert m.action == "se retourne"
    assert m.environnement == "poussière en suspension"
    assert m.doit_preserver == ("subject identity",)
    assert m.interdit == ("new objects",)
    assert not hasattr(m, "camera")


def test_la_camera_devient_un_programme_a_part():
    c = camera_program(_legacy())
    assert c.mouvement is MouvementCamera.PAN_LENT
    assert c.shot_id == "4"
    assert not c.verrouillee


def test_le_controle_reste_textuel_et_donc_non_garanti():
    """L'adaptateur fal.ai n'envoie aucun paramètre de caméra. Le contrat
    doit le dire plutôt que de laisser croire à une garantie."""
    c = camera_program(_legacy())
    assert c.controle is ControleCamera.TEXTE_SEULEMENT
    assert not c.est_garantie


def test_une_camera_absente_retombe_sur_fixe():
    """Comportement existant de `camera_verrouillee`, préservé tel quel."""
    assert camera_program(_legacy(camera="")).mouvement is MouvementCamera.FIXE
    assert camera_program(_legacy(camera="")).verrouillee


def test_une_phrase_de_camera_inconnue_ne_casse_pas():
    assert camera_program(_legacy(camera="dolly zoom vertigineux")).verrouillee


def test_les_trajectoires_restent_vides():
    """Aucun producteur ne les décide, aucun backend ne les honore. Les
    remplir donnerait l'illusion d'un contrôle absent."""
    m = motion_program(_legacy())
    assert m.trajectoires == () and m.regions_statiques == () and m.priorite == ()


# ── Perception ───────────────────────────────────────────────────────────

def test_l_ordre_d_attention_suit_la_hierarchie_existante():
    """Obligatoire d'abord, secondaire ensuite — la hiérarchie que
    ShotPromptWriter décide déjà, enfin nommée comme telle."""
    visuel = ContratVisuel(qui="strawberina", qui_apparence="fraise",
                           quoi="révèle la trahison",
                           avec_quoi=["lettre"], avec_quoi_secondaire=["fond flou"])
    p = perceptual_contract(visuel, shot_id="shot_003")
    assert p.attention == ("strawberina", "lettre", "fond flou")
    assert p.objectif_principal == "révèle la trahison"
    assert p.est_verifiable


def test_la_cible_de_mouvement_rejoint_le_contrat_perceptuel():
    visuel = ContratVisuel(qui="a", qui_apparence="", quoi="montre", avec_quoi=["x"])
    p = perceptual_contract(visuel, _legacy(), shot_id="s")
    assert "viewer_must_perceive_camera_movement" in p.doit_percevoir


def test_une_camera_verrouillee_declare_la_confusion_a_eviter():
    """C'est ce qui transforme « mouvement faible » en `CAMERA_DOMINANT`."""
    visuel = ContratVisuel(qui="a", qui_apparence="", quoi="montre")
    p = perceptual_contract(visuel, _legacy(camera=""), shot_id="s")
    assert p.ne_doit_pas_etre_confondu_avec == ("camera_only_motion",)


def test_une_camera_mobile_ne_declare_pas_cette_confusion():
    visuel = ContratVisuel(qui="a", qui_apparence="", quoi="montre")
    p = perceptual_contract(visuel, _legacy(), shot_id="s")
    assert p.ne_doit_pas_etre_confondu_avec == ()


def test_un_contrat_visuel_sans_objectif_n_est_pas_verifiable():
    """Il serait satisfait par n'importe quelle image — donc inutile."""
    assert not perceptual_contract(ContratVisuel(qui="a", qui_apparence="", quoi="")).est_verifiable


# ── Chronologie : la propriété la plus importante du dépôt ───────────────

def _bande(**extra) -> BandeVoix:
    base = dict(
        fichier=Path("/tmp/voix.mp3"), duree_ms=4200, caracteres_factures=120,
        repliques=[
            RepliqueDite(numero=1, personnage="strawberina", texte="tu m'as trahi",
                         fichier=Path("/tmp/1.mp3"), debut_ms=0, duree_ms=1500,
                         mots=[MotLegacy(texte="tu", debut_ms=0, fin_ms=300),
                               MotLegacy(texte="m'as", debut_ms=300, fin_ms=820)]),
            RepliqueDite(numero=2, personnage="bananito", texte="jamais",
                         fichier=Path("/tmp/2.mp3"), debut_ms=1900, duree_ms=700,
                         mots=[MotLegacy(texte="jamais", debut_ms=1900, fin_ms=2600)]),
        ],
    )
    return BandeVoix(**{**base, **extra})


def test_les_timings_traversent_a_la_milliseconde_pres():
    """La chronologie officielle. Le moindre arrondi décalerait les
    sous-titres, et tout le découpage repose sur ces valeurs exactes."""
    t = audio_timeline(_bande())
    assert t.duree_ms == 4200
    assert [m.debut_ms for m in t.mots] == [0, 300, 1900]
    assert [m.fin_ms for m in t.mots] == [300, 820, 2600]
    assert t.repliques[1].debut_ms == 1900
    assert t.repliques[1].fin_ms == 2600


def test_les_durees_de_replique_alimentent_le_decoupage():
    assert audio_timeline(_bande()).durees_repliques_s == (1.5, 0.7)


def test_les_frontieres_de_replique_sont_preservees():
    """Une carte de sous-titres à cheval mêle deux personnages sur la même
    ligne — c'est ce que ces frontières empêchent."""
    assert sorted(audio_timeline(_bande()).debuts_de_replique_ms) == [0, 1900]


def test_le_script_fournit_l_emotion_et_la_relance():
    repliques = [{"numero": 1, "emotion": "colere", "relance": True},
                 {"numero": 2, "emotion": "surprise"}]
    t = audio_timeline(_bande(), repliques)
    assert t.repliques[0].emotion == "colere" and t.repliques[0].relance
    assert t.repliques[1].emotion == "surprise" and not t.repliques[1].relance


def test_sans_script_ces_champs_restent_neutres_plutot_que_devines():
    t = audio_timeline(_bande())
    assert all(r.emotion == "" and not r.relance for r in t.repliques)


def test_le_mode_muet_est_reconnu_et_ne_passe_pas_pour_une_vraie_voix():
    """`voix.py` produit déjà une piste silencieuse de la bonne durée quand
    la synthèse échoue. Sans ce drapeau, l'aval la prendrait pour une voix."""
    assert audio_timeline(_bande(caracteres_factures=0)).muet
    assert not audio_timeline(_bande()).muet


def test_une_bande_vide_n_est_pas_declaree_muette():
    """Aucune réplique = rien n'a été demandé, pas « la synthèse a échoué »."""
    assert not audio_timeline(_bande(repliques=[], caracteres_factures=0)).muet


def test_la_timeline_fait_l_aller_retour_json():
    from pdz.contracts import AudioTimeline

    origine = audio_timeline(_bande())
    assert AudioTimeline.depuis_json(origine.en_json()) == origine
