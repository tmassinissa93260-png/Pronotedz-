"""Observation → diagnostic → réparation : la boucle qui rend le système auto-correcteur.

Avant cette boucle, un échec produisait un repli silencieux : le plan
retombait en image fixe, et rien ne disait POURQUOI. Le run #66 a coûté
0,900 € pour des clips dont 78 % de la dépense était invisible.

Ce que ces tests protègent :

  · **un axe non mesuré vaut `INCERTAIN`** — un système qui lit « pas
    regardé » comme « bon » livre un clip statique en le déclarant conforme ;
  · **un diagnostic est une hypothèse**, avec sa confiance — pas un verdict ;
  · **la cause décide de la réparation** — `CAMERA_DOMINANT` et
    `STATIC_RENDER` voient le même symptôme et appellent l'inverse ;
  · **une relance sans changement de cause n'est pas une réparation.**
"""

from __future__ import annotations

import pytest

from pdz.contracts import (
    Axe,
    FailureDiagnosis,
    Mesure,
    ModeEchec,
    ObservationReport,
    Severite,
    TypeReparation,
    Verdict,
)
from pdz.contracts.communs import utilite_esperee
from pdz.diagnostics import Attendu, diagnostiquer, ecarts
from pdz.repair import CATALOGUE, branches_pour, compiler


def _rapport(*mesures) -> ObservationReport:
    return ObservationReport(shot_id="shot_001", mesures=tuple(mesures))


FICHIER_OK = Mesure(axe=Axe.TECHNIQUE, nom="fichier_valide",
                    verdict=Verdict.REUSSI, sonde="verification_mouvement",
                    valeur="4.84 s à 25.0 fps")
STATIQUE = Mesure(axe=Axe.MOUVEMENT, nom="mouvement_percu",
                  verdict=Verdict.ECHOUE, sonde="verification_mouvement",
                  valeur="0.509/255", seuil="1.0/255")
BOUGE = Mesure(axe=Axe.MOUVEMENT, nom="mouvement_percu",
               verdict=Verdict.REUSSI, sonde="verification_mouvement",
               valeur="1.723/255", seuil="1.0/255")


# ── L'observation ────────────────────────────────────────────────────────

def test_un_axe_non_mesure_ne_vaut_jamais_reussi():
    """La règle centrale. Le run #66 : un clip payé, valide, de la bonne
    durée, et parfaitement statique — déclaré conforme."""
    rapport = _rapport(FICHIER_OK, BOUGE)
    assert rapport.verdict_axe(Axe.MOUVEMENT) is Verdict.REUSSI
    assert rapport.verdict_axe(Axe.SEMANTIQUE) is Verdict.INCERTAIN
    assert rapport.verdict is Verdict.INCERTAIN, "cinq axes ne sont pas mesurés"


def test_le_rapport_dit_ses_propres_angles_morts():
    non_mesures = _rapport(FICHIER_OK, BOUGE).axes_non_mesures
    assert Axe.MOUVEMENT not in non_mesures
    assert Axe.SEMANTIQUE in non_mesures and Axe.AUDIO in non_mesures


def test_le_seuil_est_reporte_pour_rester_relisible_apres_recalibrage():
    """Sans le seuil, un ancien rapport devient ininterprétable dès qu'on
    change la calibration."""
    assert STATIQUE.seuil == "1.0/255"


# ── Le diagnostic ────────────────────────────────────────────────────────

def test_un_plan_qui_ne_devait_pas_bouger_n_echoue_pas_en_ne_bougeant_pas():
    """L'erreur symétrique, et la plus facile à commettre."""
    assert diagnostiquer(Attendu(shot_id="s", sujet_doit_bouger=False),
                         _rapport(FICHIER_OK, STATIQUE)) is None


def test_aucun_diagnostic_quand_l_observation_ne_contredit_rien():
    """`None` est un RÉSULTAT — « l'observation ne contredit pas
    l'intention » — distinct d'un `INCONNU` qui dirait « on n'a pas pu
    savoir »."""
    assert diagnostiquer(Attendu(shot_id="s", sujet_doit_bouger=True),
                         _rapport(FICHIER_OK, BOUGE)) is None


def test_un_rendu_statique_est_nomme_comme_tel():
    d = diagnostiquer(Attendu(shot_id="s", sujet_doit_bouger=True, importance=0.9),
                      _rapport(FICHIER_OK, STATIQUE))
    assert d.mode is ModeEchec.RENDU_STATIQUE
    assert d.severite is Severite.CRITIQUE
    assert d.confiance > 0.8


def test_camera_dominante_exige_que_la_camera_ait_pu_bouger():
    """C'est ce qui transforme « mouvement faible » — qui ne dit rien — en
    un diagnostic qui dit quoi corriger.

    Mais il faut que la caméra ait eu le DROIT de bouger. Une première
    version se contentait de la confusion déclarée, et c'était faux : sur un
    plan à caméra verrouillée, ce diagnostic menait à « verrouiller la
    caméra », c'est-à-dire à ne rien changer — une réparation sans effet est
    une relance déguisée.
    """
    d = diagnostiquer(
        Attendu(shot_id="s", sujet_doit_bouger=True, camera_doit_bouger=True,
                importance=0.9, confusions_interdites=("camera_only_motion",)),
        _rapport(FICHIER_OK, STATIQUE))
    assert d.mode is ModeEchec.CAMERA_DOMINANTE


def test_une_camera_verrouillee_donne_un_rendu_statique():
    """Si la caméra avait bougé, la sonde aurait MESURÉ du mouvement. Un clip
    statique dont la caméra était verrouillée n'a pas « une caméra
    dominante » — il n'a rien du tout."""
    d = diagnostiquer(
        Attendu(shot_id="s", sujet_doit_bouger=True, camera_doit_bouger=False,
                importance=0.9, confusions_interdites=("camera_only_motion",)),
        _rapport(FICHIER_OK, STATIQUE))
    assert d.mode is ModeEchec.RENDU_STATIQUE


def test_camera_dominante_porte_une_confiance_plus_basse():
    """Sans sonde qui SÉPARE le mouvement de caméra de celui du sujet, c'est
    une hypothèse fondée sur l'intention, pas une mesure. Le dire est plus
    utile que d'affirmer."""
    statique = diagnostiquer(Attendu(shot_id="s", sujet_doit_bouger=True),
                             _rapport(FICHIER_OK, STATIQUE))
    camera = diagnostiquer(
        Attendu(shot_id="s", sujet_doit_bouger=True, camera_doit_bouger=True,
                confusions_interdites=("camera_only_motion",)),
        _rapport(FICHIER_OK, STATIQUE))
    assert camera.confiance < statique.confiance


def test_un_mouvement_non_mesurable_ne_devient_pas_un_echec():
    """Ni confirmé, ni infirmé : c'est un échec de la MESURE, pas du plan.
    Le traiter comme un échec du plan ferait dépenser pour réparer quelque
    chose qui va peut-être très bien."""
    incertain = Mesure(axe=Axe.MOUVEMENT, nom="mouvement_percu",
                       verdict=Verdict.INCERTAIN, sonde="verification_mouvement")
    d = diagnostiquer(Attendu(shot_id="s", sujet_doit_bouger=True),
                      _rapport(FICHIER_OK, incertain))
    assert d.mode is ModeEchec.INCONNU
    assert d.confiance < 0.5
    assert d.severite is Severite.INFO


def test_un_fichier_illisible_est_diagnostique_avant_le_mouvement():
    """L'ordre compte : accuser le modèle de ne pas avoir bougé quand le
    fichier est cassé ferait chercher au mauvais endroit."""
    casse = Mesure(axe=Axe.TECHNIQUE, nom="fichier_valide",
                   verdict=Verdict.ECHOUE, sonde="verification_mouvement")
    d = diagnostiquer(Attendu(shot_id="s", sujet_doit_bouger=True), _rapport(casse))
    assert d.mode is ModeEchec.DUREE_INCORRECTE
    assert "exploitable" in d.explication


@pytest.mark.parametrize("importance,attendue", [
    (0.9, Severite.CRITIQUE), (0.5, Severite.MAJEURE), (0.1, Severite.MINEURE),
])
def test_la_severite_suit_l_importance_narrative(importance, attendue):
    """Rater le plan qui porte l'épisode n'a pas la même conséquence que
    rater un plan de transition."""
    d = diagnostiquer(
        Attendu(shot_id="s", sujet_doit_bouger=True, importance=importance),
        _rapport(FICHIER_OK, STATIQUE))
    assert d.severite is attendue


def test_les_ecarts_sont_des_preuves_pas_des_conclusions():
    """Les séparer permet de relire un diagnostic contesté sans refaire la
    mesure."""
    preuves = ecarts(Attendu(shot_id="s", sujet_doit_bouger=True),
                     _rapport(FICHIER_OK, STATIQUE))
    assert len(preuves) == 1
    assert preuves[0].dimension == "mouvement_sujet"
    assert preuves[0].observe == "0.509/255"


# ── La réparation ────────────────────────────────────────────────────────

def _diag(mode: ModeEchec, **extra) -> FailureDiagnosis:
    base = dict(shot_id="s1", mode=mode, severite=Severite.CRITIQUE,
                confiance=0.8, reparations_possibles=("x",))
    return FailureDiagnosis(**{**base, **extra})


@pytest.mark.parametrize("mode,attendue", [
    (ModeEchec.CAMERA_DOMINANTE, TypeReparation.AJUSTER_CAMERA),
    (ModeEchec.RENDU_STATIQUE, TypeReparation.AJUSTER_MOUVEMENT),
    (ModeEchec.MOUVEMENT_SUJET_ABSENT, TypeReparation.AJUSTER_MOUVEMENT),
    (ModeEchec.DERIVE_IDENTITE, TypeReparation.REPARATION_LOCALE),
    (ModeEchec.INCONNU, TypeReparation.DEMANDER_HUMAIN),
])
def test_la_cause_decide_de_la_reparation(mode, attendue):
    """Toute la différence avec une relance : `CAMERA_DOMINANT` et
    `STATIC_RENDER` voient le même symptôme et appellent l'inverse."""
    assert compiler(_diag(mode), budget_restant_eur=1.0).choisie is attendue


def test_une_derive_d_identite_repare_localement_plutot_que_tout_refaire():
    """On ne régénère jamais un plan entier quand une réparation locale est
    techniquement possible."""
    assert compiler(_diag(ModeEchec.DERIVE_IDENTITE),
                    budget_restant_eur=1.0).choisie is TypeReparation.REPARATION_LOCALE


def test_l_arbre_progresse_au_lieu_de_repeter():
    """Sans exclusion des branches tentées, l'arbre choisirait éternellement
    la même — ce qui serait exactement `retry 1 / retry 2 / retry 3`."""
    diagnostic, tentees, choix = _diag(ModeEchec.RENDU_STATIQUE), (), []
    for n in (1, 2, 3):
        plan = compiler(diagnostic, tentative=n, tentatives_max=5,
                        deja_tentees=tentees, budget_restant_eur=1.0)
        choix.append(plan.choisie)
        tentees += (plan.choisie,)
    assert len(set(choix)) == len(choix), f"branche répétée : {choix}"


def test_les_tentatives_epuisees_terminent_le_plan():
    """Un plan doit pouvoir se terminer : sans issue, la production
    s'arrêterait sur un plan secondaire."""
    plan = compiler(_diag(ModeEchec.RENDU_STATIQUE), tentative=3, tentatives_max=3,
                    budget_restant_eur=1.0)
    assert plan.choisie is TypeReparation.ACCEPTER
    assert "épuisés" in plan.raison


def test_un_diagnostic_peu_sur_ne_declenche_aucune_depense():
    """Réparer sur une hypothèse à pile ou face coûte plus cher que le
    défaut qu'on cherche à corriger."""
    plan = compiler(_diag(ModeEchec.RENDU_STATIQUE, confiance=0.2),
                    budget_restant_eur=1.0)
    assert plan.choisie is TypeReparation.ACCEPTER
    assert "non actionnable" in plan.raison


def test_une_branche_hors_budget_n_est_pas_proposee():
    """Proposer l'impossible fait perdre un tour."""
    branches = branches_pour(_diag(ModeEchec.DERIVE_IDENTITE), budget_restant_eur=0.0)
    assert TypeReparation.CHANGER_BACKEND not in {b.type for b in branches}


def test_accepter_est_toujours_disponible():
    branches = branches_pour(_diag(ModeEchec.RENDU_STATIQUE), budget_restant_eur=0.0)
    assert TypeReparation.ACCEPTER in {b.type for b in branches}


def test_le_choix_porte_toujours_sa_raison():
    """Un choix dont on a perdu la raison ne peut être ni contesté, ni
    appris — et `ExperienceMemory` n'en tirerait rien."""
    raison = compiler(_diag(ModeEchec.CAMERA_DOMINANTE), budget_restant_eur=1.0).raison
    for attendu in ("CAMERA_DOMINANT", "succès attendu", "coût", "risque", "tentative"):
        assert attendu in raison


# ── L'utilité : l'erreur commise deux fois, gardée en test ──────────────

def test_accepter_ne_repare_rien():
    """Lui donner un succès de 1,0 — première version de la table — la
    faisait gagner contre toutes les réparations, y compris gratuites : le
    défaut n'était jamais corrigé, et le journal affichait pourtant
    « réparation choisie : accepter »."""
    assert CATALOGUE[TypeReparation.ACCEPTER]["succes_attendu"] == 0.0


def test_changer_de_strategie_ne_promet_pas_le_mouvement_demande():
    """Retomber sur la parallaxe garantit UN mouvement, pas CELUI qui était
    demandé — la même limite que côté stratégies."""
    strategie = CATALOGUE[TypeReparation.CHANGER_STRATEGIE]["succes_attendu"]
    camera = CATALOGUE[TypeReparation.AJUSTER_CAMERA]["succes_attendu"]
    assert strategie < 0.8, "surestimé, la correction ciblée perdrait toujours"
    assert compiler(_diag(ModeEchec.CAMERA_DOMINANTE),
                    budget_restant_eur=1.0).choisie is TypeReparation.AJUSTER_CAMERA
    assert camera <= strategie, "le test suivant vérifie que le risque tranche"


def test_un_ratio_ferait_gagner_le_gratuit_qui_ne_repare_rien():
    """L'erreur a été commise DEUX FOIS — choix de stratégie, puis choix de
    réparation. D'où une formule unique, partagée, et ce test qui garde le
    défaut."""
    ratio = lambda succes, cout: succes / max(cout, 0.001)  # noqa: E731
    assert ratio(0.0, 0.0) == 0.0

    # Le vrai piège : une branche à succès non nul et coût nul écrase tout.
    assert ratio(0.60, 0.0) > ratio(0.60, 0.23)
    # L'utilité, elle, compare des euros à des euros.
    assert utilite_esperee(0.60, 0.0, 1.0, 0.25) == pytest.approx(0.45)
    assert utilite_esperee(0.60, 0.23, 1.0, 0.30) == pytest.approx(0.19)


def test_le_risque_reduit_le_gain_jamais_le_cout():
    """Le coût est payé que la réparation réussisse ou non."""
    sans = utilite_esperee(0.8, 0.10, 1.0, risque=0.0)
    avec = utilite_esperee(0.8, 0.10, 1.0, risque=0.5)
    assert avec < sans
    assert avec == pytest.approx(0.8 * 0.5 - 0.10)


# ── La boucle complète ───────────────────────────────────────────────────

def test_de_l_observation_a_la_reparation_sans_intervention():
    """Le trajet complet : un clip statique devient une correction ciblée."""
    attendu = Attendu(shot_id="shot_001", sujet_doit_bouger=True, importance=0.9,
                      camera_doit_bouger=True,
                      confusions_interdites=("camera_only_motion",))
    rapport = _rapport(FICHIER_OK, STATIQUE)

    diagnostic = diagnostiquer(attendu, rapport)
    assert diagnostic is not None and diagnostic.actionnable

    plan = compiler(diagnostic, budget_restant_eur=1.0)
    assert plan.choisie is TypeReparation.AJUSTER_CAMERA
    assert plan.shot_id == "shot_001"
    assert plan.diagnostic == diagnostic.id


def test_un_clip_conforme_ne_declenche_aucune_reparation():
    assert diagnostiquer(Attendu(shot_id="s", sujet_doit_bouger=True, importance=0.9),
                         _rapport(FICHIER_OK, BOUGE)) is None
