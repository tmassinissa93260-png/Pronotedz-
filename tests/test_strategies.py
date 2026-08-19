"""Le graphe de stratégies choisit COMMENT fabriquer, pas AVEC QUOI.

Ce que ces tests protègent, et qui n'existait nulle part avant :

  · **une garantie n'est pas une espérance.** Le run #66 a mesuré un clip
    payé, valide, de la bonne durée, et parfaitement statique. La parallaxe
    locale, elle, est du calcul : le mouvement est là à coup sûr.
  · **une stratégie gratuite ne sait pas tout faire.** La 2.5D ne peut pas
    inventer un personnage qui tourne la tête — elle fait bouger ce qui est
    déjà dans l'image. Ignorer cette limite ferait choisir le gratuit
    partout, ce que la première version du score faisait effectivement.
  · **le choix est tracé.** Un choix dont on a perdu la raison ne peut être
    ni contesté, ni appris.
"""

from __future__ import annotations

import pytest

from pdz.contracts import Strategie
from pdz.strategies import (
    ContexteRendu,
    StrategieDirectI2V,
    StrategieImageFixe,
    StrategieProcedurale,
    StrategieTwoPointFiveD,
    candidates,
    choisir,
)
from pdz.strategies.base import Candidate
from pdz.strategies.graphe import VALEUR_PLAN_MAXIMALE_EUR, valeur_du_plan_eur


@pytest.fixture
def image(tmp_path):
    fichier = tmp_path / "plan.png"
    fichier.write_bytes(b"\x89PNG-faux")
    return fichier


def _contexte(image, **extra) -> ContexteRendu:
    base = dict(shot_id="shot_001", image=image,
                destination=image.parent / "clip.mp4", duree_s=5.0,
                prompt="animate this still image", budget_restant_eur=1.0)
    return ContexteRendu(**{**base, **extra})


# ── Ce que chaque stratégie sait rendre ─────────────────────────────────

def test_la_parallaxe_ne_sait_pas_inventer_un_mouvement_de_sujet(image):
    """Elle fait bouger ce qui EST dans l'image ; un personnage qui tourne
    la tête demande des pixels qui n'y sont pas."""
    sujet = StrategieTwoPointFiveD().evaluer(_contexte(image, mouvement_attendu="sujet"))
    ambiance = StrategieTwoPointFiveD().evaluer(_contexte(image, mouvement_attendu="ambiance"))
    assert not sujet.garanti and sujet.confiance < 0.5
    assert ambiance.garanti and ambiance.confiance > 0.9


def test_le_procedural_ne_rend_qu_un_mouvement_de_camera(image):
    camera = StrategieProcedurale().evaluer(_contexte(image, mouvement_attendu="camera"))
    sujet = StrategieProcedurale().evaluer(_contexte(image, mouvement_attendu="sujet"))
    assert camera.garanti
    assert not sujet.garanti


def test_le_generatif_n_est_jamais_garanti(image):
    """La propriété la plus importante de cette stratégie, et celle que la
    cascade en dur ne disait nulle part."""
    candidate = StrategieDirectI2V().evaluer(_contexte(image, mouvement_attendu="sujet"))
    assert candidate is not None
    assert not candidate.garanti
    assert candidate.cout_eur > 0


def test_l_image_fixe_accepte_tout_et_ne_promet_rien(image):
    """Une décision légitime, pas un échec — et il faut pouvoir la
    distinguer d'une animation qui a raté."""
    candidate = StrategieImageFixe().evaluer(_contexte(image, mouvement_attendu="sujet"))
    assert candidate.confiance == 0.0
    assert candidate.garanti and candidate.cout_eur == 0.0


def test_une_image_absente_fait_renoncer_la_parallaxe(tmp_path):
    """`None` n'est pas un échec : une stratégie hors de son domaine fait
    exactement son travail en refusant."""
    fantome = tmp_path / "jamais.png"
    assert StrategieTwoPointFiveD().evaluer(
        _contexte(fantome, mouvement_attendu="ambiance")) is None


# ── Le refus avant dépense ──────────────────────────────────────────────

def test_un_budget_epuise_ecarte_le_generatif(image):
    candidate = StrategieDirectI2V().evaluer(
        _contexte(image, budget_restant_eur=0.0, mouvement_attendu="sujet"))
    assert candidate.confiance == 0.0
    assert "budget" in candidate.raison


def test_une_duree_impossible_ecarte_le_generatif_sans_payer(image):
    """Refusé par `valider()`, donc avant le moindre appel réseau."""
    candidate = StrategieDirectI2V().evaluer(
        _contexte(image, duree_s=60, mouvement_attendu="sujet"))
    assert candidate.confiance == 0.0


# ── L'arbitrage ─────────────────────────────────────────────────────────

def test_un_mouvement_de_sujet_critique_justifie_le_generatif(image):
    """Seul le modèle sait rendre ce que ce plan exige, et le plan le vaut."""
    retenue, _ = choisir(_contexte(image, mouvement_attendu="sujet", importance=0.9))
    assert retenue.strategie is Strategie.DIRECT_I2V


def test_un_mouvement_de_sujet_secondaire_ne_le_justifie_pas(image):
    """Le plan bougera sans montrer exactement ce qui était demandé — un
    compromis assumé, et tracé dans la raison du choix."""
    retenue, raison = choisir(_contexte(image, mouvement_attendu="sujet", importance=0.1))
    assert retenue.strategie is Strategie.DEUX_ET_DEMI_D
    assert "ne sait pas inventer" in raison


def test_une_ambiance_ne_justifie_jamais_de_payer(image):
    """Payer un modèle pour ce que la parallaxe rend gratuitement ET à coup
    sûr, c'est acheter une espérance là où on avait une garantie — l'erreur
    exacte du run #66."""
    for importance in (0.1, 0.5, 0.9, 1.0):
        retenue, _ = choisir(_contexte(image, mouvement_attendu="ambiance",
                                       importance=importance))
        assert retenue.strategie is Strategie.DEUX_ET_DEMI_D


def test_un_budget_epuise_retombe_sur_le_gratuit_en_le_disant(image):
    retenue, raison = choisir(_contexte(image, mouvement_attendu="sujet",
                                        importance=0.9, budget_restant_eur=0.0))
    assert retenue.cout_eur == 0.0
    assert raison


def test_le_choix_porte_toujours_sa_raison(image):
    _, raison = choisir(_contexte(image, mouvement_attendu="ambiance", importance=0.5))
    for attendu in ("coût", "confiance", "importance"):
        assert attendu in raison


# ── L'utilité : pourquoi ce n'est PAS un ratio ──────────────────────────

def test_un_ratio_confiance_par_euro_ferait_toujours_gagner_le_gratuit():
    """Le défaut de la première version de ce module, gardé comme test.

    « confiance / coût » rend toute stratégie gratuite mille fois meilleure
    que n'importe quelle stratégie payante, quelle que soit sa confiance —
    y compris sur un plan que seule la payante sait rendre.
    """
    gratuit = Candidate(Strategie.DEUX_ET_DEMI_D, 0.0, 0, confiance=0.25, garanti=False)
    payant = Candidate(Strategie.DIRECT_I2V, 0.23, 0, confiance=0.70, garanti=False)

    ratio = lambda c: c.confiance / max(c.cout_eur, 0.001)  # noqa: E731
    assert ratio(gratuit) > ratio(payant), "le ratio se trompe — c'est le point"

    valeur = valeur_du_plan_eur(0.9)
    assert payant.utilite(valeur) > gratuit.utilite(valeur), "l'utilité tranche juste"


def test_l_utilite_est_un_gain_en_euros():
    candidate = Candidate(Strategie.DIRECT_I2V, cout_eur=0.23, latence_ms=0,
                          confiance=0.5, garanti=False)
    assert candidate.utilite(1.0) == pytest.approx(0.5 - 0.23)


def test_la_valeur_d_un_plan_suit_son_importance():
    assert valeur_du_plan_eur(1.0) == VALEUR_PLAN_MAXIMALE_EUR
    assert valeur_du_plan_eur(0.0) == 0.0
    assert valeur_du_plan_eur(0.5) == pytest.approx(VALEUR_PLAN_MAXIMALE_EUR / 2)


def test_une_importance_hors_bornes_est_ramenee_dans_le_domaine():
    assert valeur_du_plan_eur(5.0) == VALEUR_PLAN_MAXIMALE_EUR
    assert valeur_du_plan_eur(-1.0) == 0.0


# ── Le graphe ───────────────────────────────────────────────────────────

def test_toutes_les_strategies_se_prononcent(image):
    proposees = candidates(_contexte(image, mouvement_attendu="ambiance"))
    assert {c.strategie for c in proposees} == {
        Strategie.DIRECT_I2V, Strategie.DEUX_ET_DEMI_D,
        Strategie.PROCEDURAL, Strategie.IMAGE_FIXE,
    }


def test_choisir_sans_aucune_strategie_dit_pourquoi(image):
    with pytest.raises(ValueError, match="StrategieImageFixe"):
        choisir(_contexte(image), strategies=())


def test_l_evaluation_ne_produit_aucun_fichier(image):
    """`evaluer()` doit être gratuit et sans effet de bord : c'est ce qui
    permet de comparer dix stratégies avant d'en exécuter une."""
    destination = image.parent / "clip.mp4"
    candidates(_contexte(image, mouvement_attendu="sujet", importance=0.9))
    assert not destination.exists()


# ── L'exécution ─────────────────────────────────────────────────────────

def test_le_procedural_ne_produit_aucun_clip(image):
    """C'est FFmpeg qui appliquera le recadrage au montage — il n'y a rien à
    produire ici, seulement une décision à porter."""
    resultat = StrategieProcedurale().executer(_contexte(image))
    assert not resultat.clip_produit
    assert resultat.fichier == image
    assert resultat.cout_eur == 0.0


def test_l_image_fixe_rend_l_image_telle_quelle(image):
    resultat = StrategieImageFixe().executer(_contexte(image))
    assert resultat.fichier == image and not resultat.clip_produit
