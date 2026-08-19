"""`fait:` annonce, `capacites:` mesure — et les deux ne se valent pas.

Ce que ces tests protègent : la distinction elle-même. Elle n'a de valeur
que si rien ne peut promouvoir une annonce en mesure, ni un inconnu en refus.

Le dépôt savait déjà ces choses — mais en commentaires :

    « MESURÉ (runs #57, #65, #66) : ce endpoint rend ~4,84 s qu'on lui
      demande 5 ou 10 »
    « ANNONCÉES par fal, pas encore mesurées ici »

Un commentaire ne peut pas empêcher une décision. Une donnée, si.
"""

from __future__ import annotations

from pdz.capabilities import capacites_du_modele, graphe, mesures_manquantes
from pdz.contracts import StatutCapacite

KLING = "fal-ai/kling-video/v2.1/standard/image-to-video"
LTX = "fal-ai/ltx-video-v097/image-to-video"


# ── `fait:` ne promet rien ───────────────────────────────────────────────

def test_tout_ce_qui_vient_de_fait_est_annonce():
    """`fait:` sert à ROUTER, jamais à garantir. Le dépôt s'en sert depuis
    toujours pour choisir un modèle — choisir n'est pas promettre."""
    animation = capacites_du_modele(KLING).capacite("animation")
    assert animation.statut is StatutCapacite.ANNONCE
    assert not animation.utilisable


def test_une_capacite_annoncee_n_engage_aucune_depense():
    assert not capacites_du_modele(KLING).sait_faire("animation")
    assert not capacites_du_modele(KLING).sait_faire("duree_10s")


# ── `capacites:` peut porter une mesure ─────────────────────────────────

def test_une_capacite_mesuree_engage():
    i2v = capacites_du_modele(KLING).capacite("image_to_video")
    assert i2v.statut is StatutCapacite.MESURE
    assert i2v.utilisable
    assert i2v.mesure_le, "une mesure sans date n'est pas reproductible"


def test_capacites_ecrase_toujours_fait():
    """`capacites:` est la seule source qui peut porter une mesure : la
    laisser écraser par une annonce serait l'inverse du but recherché."""
    assert capacites_du_modele(KLING).capacite("image_to_video").statut is StatutCapacite.MESURE


# ── MESURÉ-FAUX ≠ INCONNU ────────────────────────────────────────────────

def test_une_capacite_mesuree_fausse_dit_qu_on_a_verifie():
    """« ltx-video rend ~4,84 s qu'on lui demande 5 ou 10 » : la seule
    capacité du dépôt dont on ait mesuré qu'elle est FAUSSE."""
    d10 = capacites_du_modele(LTX).capacite("duree_10s")
    assert d10.statut is StatutCapacite.MESURE
    assert d10.valeur is False
    assert not d10.utilisable
    assert d10.methode, "sans méthode, une mesure n'est qu'une affirmation de plus"


def test_un_inconnu_ne_dit_pas_que_c_est_faux():
    """`valeur=None` et `valeur=False` sont deux informations opposées."""
    camera = capacites_du_modele(KLING).capacite("camera_control")
    assert camera.statut is StatutCapacite.INCONNU
    assert camera.valeur is None
    assert not camera.utilisable


def test_les_deux_modeles_ne_disent_pas_la_meme_chose_de_la_duree():
    """Kling ANNONCE 10 s, ltx a MESURÉ que non. Même capacité, deux
    statuts — c'est précisément ce que l'ancienne structure ne savait pas
    exprimer."""
    kling = capacites_du_modele(KLING).capacite("duree_10s")
    ltx = capacites_du_modele(LTX).capacite("duree_10s")
    assert kling.statut is StatutCapacite.ANNONCE and kling.valeur is True
    assert ltx.statut is StatutCapacite.MESURE and ltx.valeur is False


# ── Robustesse de la lecture ─────────────────────────────────────────────

def test_une_capacite_absente_du_fichier_est_inconnue():
    """Ne jamais lever sur une capacité qu'on n'a pas prévue : la question
    « sais-tu faire X ? » doit toujours avoir une réponse."""
    inconnue = capacites_du_modele(KLING).capacite("teleportation")
    assert inconnue.statut is StatutCapacite.INCONNU
    assert not inconnue.utilisable


def test_un_modele_absent_ne_casse_rien():
    assert capacites_du_modele("modele-inexistant").capacites == ()


def test_les_durees_reelles_remontent_dans_le_profil():
    assert capacites_du_modele(KLING).durees_s == (5, 10)
    assert capacites_du_modele(LTX).durees_s == (5,)


# ── Le graphe ────────────────────────────────────────────────────────────

def test_le_graphe_couvre_tous_les_modeles():
    from pdz.ia.registre import registre

    assert len(graphe().modeles) == len(registre().modeles)


def test_les_candidats_mettent_le_mesure_avant_l_annonce():
    """C'est ainsi qu'une capacité passe un jour d'ANNONCE à MESURE : les
    annoncés restent des candidats, jamais devant ce qui est prouvé."""
    candidats = [m.modele for m in graphe().candidats("image_to_video")]
    assert candidats, "aucun candidat i2v — la lecture des capacités est cassée"
    mesures = [m for m in graphe().candidats("image_to_video")
               if m.sait_faire("image_to_video")]
    assert candidats[:len(mesures)] == [m.modele for m in mesures]


def test_un_modele_sans_bloc_capacites_reste_utilisable_pour_le_routage():
    """La rétro-compatibilité : les modèles de texte n'ont aucun bloc
    `capacites:`, et le routage par `fait:` doit continuer de marcher."""
    sonnet = capacites_du_modele("claude-sonnet-5")
    assert sonnet.capacite("vision").statut is StatutCapacite.ANNONCE
    assert sonnet.capacite("vision").valeur is True


# ── La carte des angles morts ────────────────────────────────────────────

def test_le_systeme_sait_dire_ce_qu_il_n_a_pas_mesure():
    """La liste de travail. Une capacité ANNONCÉE sur laquelle on s'appuie
    souvent mérite d'être mesurée avant de le découvrir en production."""
    manquantes = mesures_manquantes()
    assert manquantes, "tout serait mesuré ? c'est faux, et le dire serait pire"
    assert (KLING, "camera_control") in manquantes
    assert (KLING, "image_to_video") not in manquantes, "celle-ci EST mesurée"


def test_l_essentiel_des_capacites_reste_non_mesure_et_c_est_dit():
    """Ce n'est pas un défaut du module : c'est l'état réel de la
    connaissance du dépôt. Le faire apparaître est ce qui permettra de le
    corriger."""
    total = sum(len(m.capacites) for m in graphe().modeles)
    assert len(mesures_manquantes()) > total / 2
