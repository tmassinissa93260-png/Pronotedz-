"""LOT A — le programme de mouvement et son compilateur de prompt.

Ce que ces tests gardent, et qui n'existait nulle part avant : la
**séparation** entre l'intention temporelle d'un plan (une donnée typée,
complète, faite pour être diagnostiquée) et le texte qu'on envoie au
fournisseur (économe, contraint, fait pour être obéi). Les deux avaient
jusqu'ici la même et unique existence — une chaîne de caractères — ce qui
rendait impossible de répondre à « qu'est-ce que ce plan VOULAIT faire ? »
autrement qu'en relisant un prompt.
"""

from pathlib import Path

import pytest

from pdz.production import motion_program
from pdz.production.motion_program import ControleCamera, MotionProgram
from pdz.univers import Univers

FRUITS = Path("univers/fruit-island.yaml")
TECHNO = Path("univers/techno-holo.yaml")


@pytest.fixture
def fruits():
    return Univers.charger(FRUITS)


@pytest.fixture
def techno():
    return Univers.charger(TECHNO)


PLAN_COMPLET = {
    "numero": 3,
    "duree_s": 4.0,
    "emotion": "calme",
    "action": "an accelerator pedal glowing in the dark",
    "mouvement_sujet": "the pedal moves downward smoothly, mechanical linkage follows",
    "mouvement_camera": "push_in_lent",
    "mouvement_environnement": "energy pulses travel along the cables",
    "intensite_mouvement": "fort",
    "registre_visuel": "technical cutaway",
}


# ── Conversion PlanScript → MotionProgram ────────────────────────────────

def test_un_plan_complet_devient_un_programme_complet(fruits):
    p = motion_program.depuis_plan(PLAN_COMPLET, fruits)

    assert isinstance(p, MotionProgram)
    assert p.shot_id == "3"
    assert p.duree_s == 4.0
    assert p.action == "the pedal moves downward smoothly, mechanical linkage follows"
    assert p.camera == "camera performs a slow forward push-in"
    assert p.environnement == "energy pulses travel along the cables"
    assert p.intensite == "fort"
    assert p.registre == "technical cutaway"


def test_le_controle_camera_dit_la_verite_sur_le_fournisseur(fruits):
    """Le point le plus important de ce lot. L'adaptateur fal.ai n'envoie que
    `{prompt, image_url, duration, aspect_ratio}` : aucun paramètre de caméra,
    de graine ni de trajectoire. Le programme doit le DIRE, pas laisser croire
    qu'un `mouvement_camera` est imposé techniquement."""
    p = motion_program.depuis_plan(PLAN_COMPLET, fruits)
    assert p.camera_controle is ControleCamera.TEXTE_SEULEMENT

    # Et il n'existe aucune autre valeur : rien dans le code ne peut prétendre
    # à un contrôle que le fournisseur n'a pas.
    assert [c.value for c in ControleCamera] == ["text_only"]


def test_la_camera_est_verrouillee_par_choix_ou_par_absence_de_choix(fruits):
    """`camera_verrouillee` sert au diagnostic en aval : un mouvement de
    caméra dominant est un échec sur un plan verrouillé, un succès sur un
    plan en `pan_lent`. Les deux cas doivent donc se distinguer."""
    fixe = motion_program.depuis_plan({"mouvement_camera": "fixe"}, fruits)
    vide = motion_program.depuis_plan({}, fruits)
    pan = motion_program.depuis_plan({"mouvement_camera": "pan_lent"}, fruits)

    assert fixe.camera_verrouillee
    assert vide.camera_verrouillee
    assert not pan.camera_verrouillee


def test_la_cible_perceptuelle_distingue_camera_sujet_et_intensite(fruits):
    """La QA doit pouvoir demander « le mouvement ATTENDU est-il perceptible ? »
    plutôt que « les pixels changent-ils ? » — deux questions différentes."""
    camera = motion_program.depuis_plan(
        {"mouvement_sujet": "x bouge", "mouvement_camera": "pan_lent"}, fruits)
    fort = motion_program.depuis_plan(
        {"mouvement_sujet": "x bouge", "intensite_mouvement": "fort"}, fruits)
    normal = motion_program.depuis_plan({"mouvement_sujet": "x bouge"}, fruits)

    assert camera.cible_perceptuelle == "viewer_must_perceive_camera_movement"
    assert fort.cible_perceptuelle == "viewer_must_perceive_strong_subject_motion"
    assert normal.cible_perceptuelle == "viewer_must_perceive_subject_motion"


# ── Invariants : dérivés, jamais inventés ────────────────────────────────

def test_les_invariants_universels_viennent_du_mode_image_vers_video(fruits):
    """Ceux-là ne dépendent d'aucun univers ni d'aucun plan : ils découlent du
    fait que l'image de départ est la source de vérité."""
    p = motion_program.depuis_plan({}, fruits)
    assert "subject identity" in p.doit_preserver
    assert "scene geometry" in p.doit_preserver
    assert "composition" in p.doit_preserver
    assert "new objects" in p.interdit
    assert "scene redesign" in p.interdit


def test_un_univers_qui_interdit_les_visages_interdit_le_mouvement_facial(techno):
    p = motion_program.depuis_plan({}, techno)
    assert "facial motion" in p.interdit


def test_un_univers_sans_interdit_facial_ne_recoit_pas_cet_invariant(fruits):
    p = motion_program.depuis_plan({}, fruits)
    assert "facial motion" not in p.interdit


def test_seul_un_choix_explicite_de_camera_fixe_interdit_le_recadrage(fruits):
    """Un `mouvement_camera` VIDE veut dire « aucun mouvement de caméra
    n'apporte rien ici », pas « fige la caméra » : en faire un interdit
    reviendrait à instruire l'immobilité sur la majorité des plans, ce que
    l'enquête run #66 avait justement fait retirer."""
    assert "camera reframing" in motion_program.depuis_plan(
        {"mouvement_camera": "fixe"}, fruits).interdit
    assert "camera reframing" not in motion_program.depuis_plan({}, fruits).interdit


def test_ce_que_le_plan_a_decide_devient_ce_qui_peut_changer(fruits):
    p = motion_program.depuis_plan(PLAN_COMPLET, fruits)
    assert "subject motion" in p.peut_changer
    assert "environmental motion" in p.peut_changer


def test_un_plan_muet_ne_recoit_aucune_permission_de_changement(fruits):
    """L'inverse est la vraie garantie : rien n'est inventé. Un plan qui ne
    décide rien n'autorise rien."""
    p = motion_program.depuis_plan({"emotion": "calme"}, fruits)
    assert p.peut_changer == ()


def test_une_geometrie_decidee_devient_une_composition_a_tenir(fruits):
    """`geometrie` est une décision de PLACEMENT : elle appartient à ce qui
    doit être préservé, pas à ce qui peut bouger librement."""
    p = motion_program.depuis_plan(
        {"geometrie": [{"objet": "pedale", "ancre": "centre"}]}, fruits)
    assert "relative object placement" in p.doit_preserver
    assert "relative object placement" not in motion_program.depuis_plan(
        {}, fruits).doit_preserver


# ── Compatibilité ascendante ─────────────────────────────────────────────

def test_un_plan_davant_plans_1_13_0_reste_convertible(fruits):
    """Un job en cache d'avant les champs `mouvement_*` : le repli par émotion
    s'applique, comme avant, et rien ne plante."""
    p = motion_program.depuis_plan({"emotion": "joie", "action": "elle danse"}, fruits)
    assert p.action == "the character laughs, body bouncing"
    assert p.camera == ""
    assert p.environnement == ""
    assert p.intensite == ""


def test_un_plan_vide_produit_un_programme_valide(fruits):
    """Cas dégénéré : aucune clé du tout. Le programme doit exister avec des
    valeurs par défaut sûres plutôt que lever."""
    p = motion_program.depuis_plan({}, fruits)
    assert p.shot_id == ""
    assert p.duree_s == 0.0
    assert p.action == "subtle idle motion, slight breathing, eyes blinking"
    assert p.cible_perceptuelle == "viewer_must_perceive_subject_motion"


def test_une_emotion_inconnue_retombe_sur_un_mouvement_neutre(fruits):
    p = motion_program.depuis_plan({"emotion": "perplexite"}, fruits)
    assert p.action == "subtle idle motion"


def test_le_programme_est_immuable(fruits):
    """Un programme est un constat, pas un brouillon : le muter en aval
    ferait mentir le diagnostic sur ce qui avait été demandé."""
    p = motion_program.depuis_plan(PLAN_COMPLET, fruits)
    with pytest.raises(Exception):
        p.action = "autre chose"        # type: ignore[misc]


# ── Compilateur de prompt ────────────────────────────────────────────────

def test_le_prompt_compile_ouvre_sur_une_transformation_pas_une_generation(fruits):
    """Le modèle doit savoir qu'il TRANSFORME une image existante. Sans cette
    ouverture, un prompt d'animation ressemble à un prompt de génération."""
    prompt = motion_program.compiler_prompt(
        motion_program.depuis_plan(PLAN_COMPLET, fruits), fruits)
    assert prompt.startswith("animate this still image")


def test_le_prompt_compile_ne_redecrit_jamais_la_scene(fruits):
    """`action` porte le prompt d'IMAGE (~65 mots). L'image de départ contient
    déjà tout ça : le réinjecter fait refabriquer au lieu d'animer."""
    prompt = motion_program.compiler_prompt(
        motion_program.depuis_plan(PLAN_COMPLET, fruits), fruits)
    assert "an accelerator pedal glowing in the dark" not in prompt


def test_le_prompt_compile_porte_les_blocs_de_decision(fruits):
    prompt = motion_program.compiler_prompt(
        motion_program.depuis_plan(PLAN_COMPLET, fruits), fruits)
    assert "the pedal moves downward smoothly" in prompt        # action
    assert "camera performs a slow forward push-in" in prompt   # caméra
    assert "energy pulses travel along the cables" in prompt    # environnement
    assert "clearly visible, unmistakable motion throughout" in prompt  # intensité
    assert "maintain style: technical cutaway" in prompt        # registre


@pytest.mark.parametrize("intensite, attendu", [
    ("fort", "clearly visible, unmistakable motion throughout"),
    ("modere", "steady, clearly readable motion"),
    ("faible", None),
    ("", None),
])
def test_lintensite_amplifie_le_texte_sauf_quand_elle_est_faible(
        fruits, intensite, attendu):
    """`faible` n'ajoute rien VOLONTAIREMENT : demander explicitement « peu de
    mouvement » à un modèle qui en produit déjà trop peu (mesuré, run #66)
    serait contre-productif."""
    prompt = motion_program.compiler_prompt(
        motion_program.depuis_plan(
            {"mouvement_sujet": "x bouge", "intensite_mouvement": intensite}, fruits),
        fruits,
    )
    if attendu is None:
        assert "clearly visible" not in prompt
        assert "clearly readable" not in prompt
    else:
        assert attendu in prompt


def test_le_prompt_compile_porte_la_preservation_et_les_interdits(fruits):
    prompt = motion_program.compiler_prompt(
        motion_program.depuis_plan(PLAN_COMPLET, fruits), fruits)
    assert "character design stays identical" in prompt
    assert "preserve scene geometry, composition" in prompt
    assert "no new objects, no scene redesign" in prompt


def test_la_preservation_ne_repete_pas_ce_que_lidentite_dit_deja(fruits):
    """`subject identity` reste dans le PROGRAMME (le diagnostic en a besoin)
    mais pas dans le prompt, où « character design stays identical » le dit
    déjà. Le programme est complet ; seule la compilation économise."""
    programme = motion_program.depuis_plan(PLAN_COMPLET, fruits)
    prompt = motion_program.compiler_prompt(programme, fruits)
    assert "subject identity" in programme.doit_preserver
    assert "subject identity" not in prompt


def test_le_prompt_compile_reste_court(fruits):
    """Le pire cas mesuré (tous les champs remplis, plus registre, géométrie
    et ambiance) reste sous le plafond que ce projet documente."""
    plan = dict(PLAN_COMPLET, geometrie=[{"objet": "pedale", "ancre": "centre"}])
    prompt = motion_program.compiler_prompt(
        motion_program.depuis_plan(plan, fruits), fruits)
    assert len(prompt.split()) <= 72


def test_le_prompt_compile_purge_le_mouvement_humain_interdit(techno):
    """Le repli par émotion « calme » promet « slight breathing, eyes
    blinking » à un univers sans visage humain. La purge existante doit bien
    s'appliquer APRÈS compilation, sur le texte final."""
    prompt = motion_program.compiler_prompt(
        motion_program.depuis_plan({"emotion": "calme"}, techno), techno)
    assert "no breathing motion" in prompt
    assert "no blinking eyes" in prompt


def test_un_univers_sans_interdit_facial_ne_paie_aucune_purge(fruits):
    prompt = motion_program.compiler_prompt(
        motion_program.depuis_plan({"emotion": "calme"}, fruits), fruits)
    assert "no breathing motion" not in prompt


def test_le_registre_deja_present_nest_pas_repete(fruits):
    """Non-remplissage, même discipline que partout ailleurs dans ce projet."""
    prompt = motion_program.compiler_prompt(
        motion_program.depuis_plan(
            {"mouvement_sujet": "the mechanism unfolds, abstract wireframe rendering",
             "registre_visuel": "abstract wireframe rendering"}, fruits),
        fruits,
    )
    assert prompt.lower().count("abstract wireframe rendering") == 1


def test_un_champ_vide_ne_produit_aucune_clause_vide(fruits):
    """Le bug classique d'un compilateur de prompt : une virgule orpheline ou
    un « maintain style: » sans style."""
    prompt = motion_program.compiler_prompt(
        motion_program.depuis_plan({"emotion": "calme"}, fruits), fruits)
    assert "maintain style" not in prompt
    assert ", ," not in prompt
    assert not prompt.strip().endswith(",")
