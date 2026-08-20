"""Faisabilité et décomposition — ne pas dépenser sur un plan infabricable.

Ce que ces tests protègent :

  · **faisabilité ≠ esthétique.** « Difficile à fabriquer » et « sera moche »
    sont deux jugements sans rapport ; les mélanger dans un score unique est
    ce que ce système refuse ;
  · **les difficultés se CUMULENT.** Six entités ET une identité à tenir ET
    un mouvement de sujet est bien plus dur que chacun séparément — une
    moyenne le lisserait ;
  · **une décomposition ne perd JAMAIS la fonction narrative.** Sinon on
    obtient trois plans corrects qui ne racontent plus rien, et le récit ne
    s'en aperçoit qu'au montage.
"""

from __future__ import annotations

import pytest

from pdz.contracts import Faisabilite, ShotSpec
from pdz.renderability import (
    SEUIL_DECOMPOSITION,
    analyser,
    decomposer,
    doit_decomposer,
    valider_statiquement,
)
from pdz.renderability.decomposition import DUREE_MINIMALE_PAR_PLAN_S


def _plan(**extra) -> ShotSpec:
    base = dict(id="shot_001", numero=1, but="montrer le rotor",
                sujet="rotor", duree_s=4.0)
    return ShotSpec(**{**base, **extra})


# ── L'analyse ────────────────────────────────────────────────────────────

def test_un_plan_sans_contrainte_est_parfaitement_faisable():
    """Le cas nominal, et la majorité des plans du dépôt. Le score part de
    1,0 et RETIRE — dans l'autre sens, un plan simple n'aurait jamais 1."""
    complexite = analyser(_plan())
    assert complexite.score == 1.0
    assert complexite.faisabilite is Faisabilite.HAUTE
    assert complexite.raisons == ()


def test_les_difficultes_se_cumulent_au_lieu_de_se_moyenner():
    """Une moyenne dirait qu'un plan à trois difficultés moyennes est
    moyen. Il est très difficile."""
    une = analyser(_plan(ancres=("avion",)))
    trois = analyser(_plan(ancres=("avion",),
                           entites_secondaires=("piste", "tour", "pluie"),
                           elements_obligatoires=("fumee", "feux")),
                     mouvement_attendu="sujet")
    assert trois.score < une.score / 2


def test_le_facteur_dominant_dit_quoi_simplifier():
    """« Ce plan est LOW » ne dit pas quoi faire. « LOW à cause de sept
    éléments » si."""
    complexite = analyser(_plan(entites_secondaires=("a", "b", "c", "d"),
                                elements_obligatoires=("e", "f")))
    assert complexite.facteur_dominant == "entites"
    assert any("éléments" in r for r in complexite.raisons)


def test_une_identite_a_tenir_pese():
    """« C'est le problème n°1 des séries générées » — `images.py`."""
    assert analyser(_plan(ancres=("strawberina",))).score < 1.0


def test_un_mouvement_de_sujet_pese_plus_qu_une_ambiance():
    """La même limite que côté stratégies : aucun traitement local ne sait
    inventer un personnage qui tourne la tête."""
    sujet = analyser(_plan(), mouvement_attendu="sujet")
    ambiance = analyser(_plan(), mouvement_attendu="ambiance")
    assert sujet.score < ambiance.score


def test_une_duree_hors_capacite_du_backend_effondre_le_score():
    """Ce n'est pas une difficulté, c'est une IMPOSSIBILITÉ : la
    décomposition doit devenir la seule issue raisonnable."""
    complexite = analyser(_plan(duree_s=12.0), duree_max_backend_s=5.0)
    assert complexite.faisabilite is Faisabilite.BASSE
    assert complexite.facteur_dominant == "duree"


def test_le_score_reste_une_estimation_technique():
    """Aucun champ de `Complexite` ne parle de qualité, de beauté ou de
    style. Si un jour c'est le cas, la distinction sera perdue."""
    complexite = analyser(_plan(ancres=("x",)))
    assert set(complexite.facteurs) <= {
        "entites", "identite", "mouvement", "duree", "exclusions"}


# ── La validation statique ──────────────────────────────────────────────

def test_une_duree_nulle_est_refusee_sans_depenser():
    assert any("durée" in p for p in valider_statiquement(_plan(duree_s=0)))


def test_un_plan_sans_sujet_est_refuse():
    assert any("sujet" in p for p in valider_statiquement(_plan(sujet="")))


def test_exiger_et_interdire_la_meme_chose_est_refuse():
    """Une image qui doit montrer ET cacher la même chose échouera quoi
    qu'il arrive — autant ne pas la payer."""
    problemes = valider_statiquement(_plan(
        elements_obligatoires=("logo", "rotor"), elements_a_exclure=("logo",)))
    assert any("exigé et interdit" in p for p in problemes)


def test_le_filtre_de_prompt_existant_est_reutilise_tel_quel():
    """`risque_prompt` tourne sans appel IA et sait déjà repérer le texte
    lisible. Le réimplémenter serait le dégrader."""
    # Formulation tirée des motifs réels du filtre — pas inventée : un test
    # qui inventerait sa propre phrase vérifierait sa propre invention.
    problemes = valider_statiquement(
        _plan(), prompt="a control panel with visible text and a screen showing data")
    assert any("texte lisible" in p for p in problemes)


def test_un_visage_n_est_un_probleme_que_si_l_univers_l_interdit():
    """La contrainte vient de l'univers. Un univers qui autorise les visages
    ne doit jamais déclencher cette correction — elle n'existe pas."""
    prompt = "close-up on a human face, sharp detailed features"
    assert not valider_statiquement(_plan(), prompt=prompt, visage_interdit=False)
    assert valider_statiquement(_plan(), prompt=prompt, visage_interdit=True)


def test_un_plan_sain_ne_remonte_aucun_probleme():
    assert valider_statiquement(_plan()) == ()


# ── La décomposition ────────────────────────────────────────────────────

def _charge(**extra) -> ShotSpec:
    base = dict(duree_s=6.0, entites_secondaires=("piste", "tour", "pluie"),
                elements_obligatoires=("fumee", "feux", "trainee"),
                ancres=("avion",), evenement="décolle", etat_avant="au sol",
                etat_apres="en vol", porte="claim_003", fonction="révèle le mécanisme")
    return _plan(**{**base, **extra})


def test_un_plan_faisable_n_est_pas_decompose():
    assert decomposer(_plan()) == (_plan(),)


def test_un_plan_charge_est_decompose():
    plan = _charge()
    morceaux = decomposer(plan, mouvement_attendu="sujet")
    assert len(morceaux) > 1


def test_la_decomposition_conserve_toujours_la_fonction_narrative():
    """LA règle. Sans elle, on obtient des plans corrects qui ne racontent
    plus rien — et ça ne se voit qu'au montage."""
    plan = _charge()
    for morceau in decomposer(plan, mouvement_attendu="sujet"):
        assert morceau.but == plan.but
        assert morceau.porte == plan.porte
        assert morceau.fonction == plan.fonction
        assert morceau.ancres == plan.ancres
        assert morceau.emotion == plan.emotion


def test_la_somme_des_durees_est_conservee():
    """Le découpage ne rallonge ni ne raccourcit le plan : la voix reste la
    chronologie officielle."""
    plan = _charge()
    morceaux = decomposer(plan, mouvement_attendu="sujet")
    assert sum(m.duree_s for m in morceaux) == pytest.approx(plan.duree_s, abs=0.01)


def test_l_etat_de_depart_et_d_arrivee_bornent_la_serie():
    """La décomposition ne change pas d'où l'on part ni où l'on arrive."""
    plan = _charge()
    morceaux = decomposer(plan, mouvement_attendu="sujet")
    assert morceaux[0].etat_avant == plan.etat_avant
    assert morceaux[-1].etat_apres == plan.etat_apres
    assert morceaux[0].etat_apres == "", "un état final intermédiaire serait faux"


def test_un_plan_trop_court_n_est_jamais_decoupe():
    """Sous ~1,2 s, une coupe n'est plus lue comme un changement : découper
    ne fabriquerait pas des plans, mais du clignotement."""
    court = _charge(duree_s=1.8)
    assert not doit_decomposer(court, analyser(court, mouvement_attendu="sujet"))
    assert len(decomposer(court, mouvement_attendu="sujet")) == 1


def test_aucun_morceau_ne_descend_sous_la_duree_lisible():
    plan = _charge(duree_s=2.6)
    for morceau in decomposer(plan, mouvement_attendu="sujet"):
        assert morceau.duree_s >= DUREE_MINIMALE_PAR_PLAN_S


def test_le_decoupage_attaque_le_facteur_dominant():
    """Simplifier ce qui n'était pas le problème ne rend le plan ni plus
    faisable, ni plus lisible."""
    plan = _charge()
    morceaux = decomposer(plan, mouvement_attendu="sujet")
    # Dominant = entités : le premier morceau établit le sujet seul.
    assert morceaux[0].entites_secondaires == ()
    assert len(morceaux[0].elements_obligatoires) < len(plan.elements_obligatoires)


def test_les_elements_obligatoires_sont_repartis_sans_perte():
    """Aucun élément exigé ne doit disparaître du découpage."""
    plan = _charge()
    morceaux = decomposer(plan, mouvement_attendu="sujet")
    repartis = [e for m in morceaux for e in m.elements_obligatoires]
    assert set(repartis) == set(plan.elements_obligatoires)


def test_decomposer_rend_toujours_au_moins_un_plan():
    """Un appelant ne doit jamais avoir à distinguer « décomposé » de « pas
    décomposé » : il reçoit une liste de plans à fabriquer, c'est tout."""
    for plan in (_plan(), _charge(), _charge(duree_s=1.0)):
        assert len(decomposer(plan)) >= 1


def test_le_seuil_de_decomposition_est_le_seul_nombre_qui_decide():
    juste_au_dessus = SEUIL_DECOMPOSITION + 0.01
    juste_en_dessous = SEUIL_DECOMPOSITION - 0.01
    from pdz.renderability.analyse import Complexite

    assert not doit_decomposer(_charge(), Complexite(score=juste_au_dessus))
    assert doit_decomposer(_charge(), Complexite(score=juste_en_dessous))
