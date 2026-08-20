"""L'état du monde, et la compilation d'un plan en tous ses contrats.

Ce que ces tests protègent :

  · **`observe = None` veut dire « pas regardé »**, jamais « conforme ». La
    confusion des deux est ce qui fait passer un clip statique ;
  · **le décor se porte d'un plan au suivant** — c'est ce que
    `continuite.porter_le_decor()` fait déjà, et pour la même raison : une
    réplique sans décor reste dans la scène en cours ;
  · **rien n'est inventé** — un plan qui ne dit rien de nouveau laisse le
    monde intact ; il n'y a pas d'« état par défaut » ;
  · **la nature du mouvement attendu décide de la stratégie** — c'est la
    réponse dont le graphe a besoin pour ne pas payer un modèle là où la
    parallaxe suffit.
"""

from __future__ import annotations

import pytest
import yaml

from pdz.contracts import ShotSpec
from pdz.production.storyboard import PlanScript
from pdz.scenes import compiler_plan, compiler_plans
from pdz.univers import Univers
from pdz.world import appliquer, delta, depuis_plans, etat_initial, observer

RACINE = __import__("pathlib").Path(__file__).resolve().parent.parent


@pytest.fixture
def univers() -> Univers:
    donnees = yaml.safe_load(
        (RACINE / "univers" / "fruit-island.yaml").read_text(encoding="utf-8"))
    return Univers.model_validate(donnees)


def _plan(**extra) -> PlanScript:
    base = dict(numero=0, replique_numero=1, personnage="strawberina",
                action="avance", emotion="calme", duree_s=2.0)
    return PlanScript(**{**base, **extra})


# ── L'état du monde ──────────────────────────────────────────────────────

def test_un_monde_initial_connait_qui_est_la_sans_inventer_ce_qu_ils_font():
    monde = etat_initial(decor="villa", entites=("strawberina", "bananito"))
    assert {e.id for e in monde.entites} == {"strawberina", "bananito"}
    assert all(e.attendu.description == "" for e in monde.entites)


def test_l_etat_apres_est_repris_tel_quel():
    monde = appliquer(etat_initial(),
                      ShotSpec(id="s1", sujet="avion", etat_apres="en vol"))
    assert monde.par_id("avion").attendu.description == "en vol"


def test_a_defaut_d_etat_final_l_evenement_fait_foi():
    monde = appliquer(etat_initial(), ShotSpec(id="s1", sujet="avion",
                                               evenement="décolle"))
    assert monde.par_id("avion").attendu.description == "décolle"


def test_un_plan_qui_ne_dit_rien_laisse_le_monde_intact():
    """Il n'y a pas d'« état par défaut » : ne rien savoir et savoir que rien
    ne change sont deux choses différentes."""
    apres = appliquer(etat_initial(),
                      ShotSpec(id="s1", sujet="avion", etat_apres="en vol"))
    encore = appliquer(apres, ShotSpec(id="s2", sujet="avion"))
    assert encore.par_id("avion").attendu.description == "en vol"


def test_le_decor_se_porte_d_un_plan_au_suivant():
    """Une réplique sans décor précisé reste dans la scène en cours —
    exactement ce que `continuite.porter_le_decor()` garantit déjà."""
    etats = depuis_plans([
        ShotSpec(id="s1", sujet="a", decor="villa"),
        ShotSpec(id="s2", sujet="a"),
        ShotSpec(id="s3", sujet="a", decor="plage"),
    ])
    assert [e.decor for e in etats] == ["villa", "villa", "plage"]


def test_la_position_reste_qualitative():
    """Donner des coordonnées à un modèle d'image ne les fait pas
    respecter, et en stocker ferait croire à une précision que rien ne tient."""
    class _PlanAvecGeometrie(ShotSpec):
        pass

    plan = ShotSpec(id="s1", sujet="avion")
    # `geometrie` vit sur le PlanScript, pas sur ShotSpec : sans elle, la
    # position reste vide plutôt que devinée.
    monde = appliquer(etat_initial(), plan)
    assert monde.par_id("avion").attendu.position.zone == ""


# ── Observé vs attendu ──────────────────────────────────────────────────

def test_une_entite_non_observee_n_est_pas_conforme():
    """`None` veut dire « pas encore regardé ». La confusion avec
    « conforme » est ce qui fait passer un clip statique."""
    monde = appliquer(etat_initial(), ShotSpec(id="s1", sujet="avion",
                                               etat_apres="en vol"))
    assert monde.par_id("avion").observe is None
    assert not monde.par_id("avion").ecart_connu
    assert delta(monde) == ()


def test_un_ecart_observe_remonte():
    monde = appliquer(etat_initial(), ShotSpec(id="s1", sujet="avion",
                                               etat_apres="en vol"))
    vu = observer(monde, {"avion": "immobile au sol"})
    assert delta(vu) == (("avion", "en vol", "immobile au sol"),)


def test_une_observation_conforme_ne_produit_aucun_delta():
    monde = appliquer(etat_initial(), ShotSpec(id="s1", sujet="avion",
                                               etat_apres="en vol"))
    assert delta(observer(monde, {"avion": "en vol"})) == ()


def test_les_entites_non_regardees_restent_distinctes_des_regardees():
    monde = appliquer(etat_initial(),
                      ShotSpec(id="s1", sujet="avion", entites_secondaires=("tour",)))
    vu = observer(monde, {"avion": "au sol"})
    assert vu.par_id("tour").observe is None
    assert vu.par_id("avion").observe is not None


def test_une_observation_ancienne_ne_survit_pas_au_plan_suivant():
    """L'observation d'un plan précédent ne dit rien de celui-ci : la
    conserver serait un mensonge."""
    monde = appliquer(etat_initial(), ShotSpec(id="s1", sujet="avion",
                                               etat_apres="au sol"))
    vu = observer(monde, {"avion": "au sol"})
    suivant = appliquer(vu, ShotSpec(id="s2", sujet="avion", etat_apres="en vol"))
    assert suivant.par_id("avion").observe is None


# ── La compilation d'un plan ────────────────────────────────────────────

def test_un_plan_produit_tous_ses_contrats(univers):
    compile = compiler_plan(_plan(mouvement_sujet="turns her head"), univers)
    assert compile.spec.id == "shot_000"
    assert compile.mouvement.shot_id == "0"
    assert compile.camera.shot_id == "0"
    assert compile.perception.shot_id == "shot_000"
    assert compile.monde.par_id("strawberina") is not None


@pytest.mark.parametrize("champs,attendu", [
    (dict(mouvement_sujet="turns her head sharply"), "sujet"),
    (dict(mouvement_environnement="dust drifting"), "ambiance"),
    (dict(mouvement_camera="pan_lent"), "camera"),
    (dict(), ""),
])
def test_la_nature_du_mouvement_attendu_est_deduite(univers, champs, attendu):
    """LA réponse dont le graphe de stratégies a besoin pour ne pas payer un
    modèle là où la parallaxe suffit."""
    assert compiler_plan(_plan(**champs), univers).mouvement_attendu == attendu


def test_un_mouvement_de_sujet_prime_sur_la_camera(univers):
    """Un plan qui demande les deux reste avant tout un plan de sujet :
    c'est ce que la parallaxe ne saura pas rendre, donc ce qui décide."""
    compile = compiler_plan(
        _plan(mouvement_sujet="turns her head", mouvement_camera="pan_lent"), univers)
    assert compile.mouvement_attendu == "sujet"


def test_la_camera_est_un_programme_separe(univers):
    """Tant que caméra et sujet vivent dans le même champ, aucun diagnostic
    ne peut dire « ça bouge, mais c'est la caméra »."""
    compile = compiler_plan(_plan(mouvement_camera="pan_lent"), univers)
    assert not compile.camera.verrouillee
    assert not hasattr(compile.mouvement, "camera")


def test_l_attendu_du_diagnostic_est_deduit_des_contrats(univers):
    compile = compiler_plan(_plan(mouvement_sujet="turns her head"), univers)
    attendu = compile.attendu
    assert attendu.sujet_doit_bouger
    assert not attendu.camera_doit_bouger
    assert "camera_only_motion" in attendu.confusions_interdites


def test_un_plan_sans_mouvement_n_attend_aucun_mouvement(univers):
    """L'erreur symétrique, et la plus facile à commettre."""
    assert not compiler_plan(_plan(), univers).attendu.sujet_doit_bouger


def test_le_premier_plan_pese_le_plus(univers):
    """Trois secondes décident de tout, et c'est le seul endroit où un
    mouvement réel se remarque à coup sûr."""
    premier = compiler_plan(_plan(numero=0), univers).importance
    suivant = compiler_plan(_plan(numero=4), univers).importance
    assert premier > suivant


def test_l_importance_monte_avec_ce_que_le_plan_porte(univers):
    nu = compiler_plan(_plan(numero=3), univers).importance
    charge = compiler_plan(_plan(numero=3, fonction="révèle le mécanisme",
                                 emotion="colere",
                                 elements_obligatoires=["lettre"]), univers).importance
    assert charge > nu
    assert 0.0 <= charge <= 1.0


def test_un_personnage_absent_de_l_univers_ne_bloque_pas(univers):
    """Le plan existe, il a un mouvement et une caméra. Seule la perception
    reste vide, et `est_verifiable` le dira."""
    compile = compiler_plan(_plan(personnage="inconnu"), univers)
    assert compile.mouvement is not None
    assert not compile.perception.est_verifiable


# ── La propagation ──────────────────────────────────────────────────────

def test_l_etat_du_monde_se_propage_d_un_plan_au_suivant(univers):
    """Sans propagation, chaque plan repartirait d'un monde vide et aucune
    dérive ne serait détectable."""
    plans = [_plan(numero=0, decor="villa"),
             _plan(numero=1, personnage="bananito"),
             _plan(numero=2)]
    compiles = compiler_plans(plans, univers, decor="villa")
    assert all(c.monde.decor == "villa" for c in compiles)
    # Le dernier monde connaît les deux personnages vus jusque-là.
    assert {"strawberina", "bananito"} <= {e.id for e in compiles[-1].monde.entites}


def test_compiler_une_liste_vide_ne_casse_rien(univers):
    assert compiler_plans([], univers) == ()
