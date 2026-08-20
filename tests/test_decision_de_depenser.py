"""Le graphe de stratégies peut dire NON au modèle payant.

`noter()` classe les plans par ce que l'animation leur apporterait — une
question narrative, à laquelle il répond bien. Le graphe répond à une autre
question, technique : **ce que ce plan demande, le modèle payant est-il seul à
savoir le rendre ?**

Les deux sont nécessaires. Un plan peut porter l'épisode et n'attendre qu'un
mouvement d'ambiance — que la parallaxe rend gratuitement et à coup sûr, là où
le modèle rend 0,23 € d'espérance. Le run #66 a mesuré exactement ce cas : un
clip payé, valide, de la bonne durée, et parfaitement statique.
"""

from __future__ import annotations

import pytest
from PIL import Image

from pdz.production import animation
from pdz.production.animation import (
    _filtrer_par_strategie,
    _importance,
    _mouvement_attendu,
)


@pytest.fixture
def image(tmp_path):
    fichier = tmp_path / "plan.jpg"
    Image.new("RGB", (64, 64), (10, 60, 90)).save(fichier)
    return fichier


def _filtrer(plans, image, *, budget=100.0):
    return _filtrer_par_strategie(list(range(len(plans))), plans,
                                  [image] * len(plans),
                                  budget_restant=budget, profil="equilibre")


# ── Ce que le plan EXIGE ────────────────────────────────────────────────

@pytest.mark.parametrize("plan,attendu", [
    ({"mouvement_sujet": "turns her head"}, "sujet"),
    ({"mouvement_environnement": "dust drifting"}, "ambiance"),
    ({"mouvement_camera": "pan_lent"}, "camera"),
    ({"mouvement_camera": "fixe"}, ""),
    ({}, ""),
])
def test_la_nature_du_mouvement_est_lue_sur_le_plan(plan, attendu):
    assert _mouvement_attendu(plan) == attendu


def test_un_mouvement_de_sujet_prime_sur_la_camera():
    """Un plan qui demande les deux reste avant tout un plan de sujet : c'est
    ce que la parallaxe ne saura pas rendre, donc ce qui décide."""
    assert _mouvement_attendu({"mouvement_sujet": "turns",
                               "mouvement_camera": "pan_lent"}) == "sujet"


# ── Le filtre ───────────────────────────────────────────────────────────

def test_un_mouvement_de_sujet_important_justifie_le_modele(image):
    plans = [{"numero": 0, "duree_s": 4.0, "emotion": "colere", "relance": True,
              "mouvement_sujet": "the character shouts, shoulders heaving"}]
    retenus, ecartes = _filtrer(plans, image)
    assert retenus == {0} and ecartes == {}


def test_une_ambiance_ne_justifie_jamais_de_payer(image):
    """Payer un modèle pour ce que la parallaxe rend gratuitement ET à coup
    sûr, c'est acheter une espérance là où on avait une garantie."""
    plans = [{"numero": 0, "duree_s": 4.0, "emotion": "colere", "relance": True,
              "mouvement_environnement": "dust drifting in the light"}]
    retenus, ecartes = _filtrer(plans, image)
    assert retenus == set()
    assert "parallaxe" in ecartes[0] or "2.5" in ecartes[0].lower()


def test_un_plan_sans_mouvement_decide_ne_coute_rien(image):
    """Payer pour un mouvement que personne n'a demandé serait le pire des
    deux mondes : une dépense ET un résultat non spécifié."""
    plans = [{"numero": 0, "duree_s": 4.0, "emotion": "colere"}]
    retenus, _ = _filtrer(plans, image)
    assert retenus == set()


def test_un_mouvement_de_sujet_secondaire_ne_justifie_pas_la_depense(image):
    """Le plan bougera sans montrer exactement ce qui était demandé — un
    compromis assumé, et tracé."""
    plans = [{"numero": 7, "duree_s": 2.0,
              "mouvement_sujet": "slight nod"}]
    retenus, ecartes = _filtrer_par_strategie([0], plans, [image],
                                              budget_restant=100.0,
                                              profil="equilibre")
    assert retenus == set() and 0 in ecartes


def test_le_filtre_ne_peut_qu_ecarter_jamais_ajouter(image):
    """Un plan non élu reste non élu : le filtre affine l'élection, il ne la
    remplace pas."""
    plans = [{"numero": i, "duree_s": 4.0,
              "mouvement_sujet": "shouts"} for i in range(3)]
    retenus, _ = _filtrer_par_strategie([1], plans, [image] * 3,
                                        budget_restant=100.0, profil="equilibre")
    assert retenus <= {1}


def test_un_budget_epuise_ecarte_le_modele(image):
    plans = [{"numero": 0, "duree_s": 4.0, "relance": True, "emotion": "colere",
              "mouvement_sujet": "shouts"}]
    retenus, ecartes = _filtrer(plans, image, budget=0.0)
    assert retenus == set() and 0 in ecartes


def test_une_strategie_indecidable_retombe_sur_le_comportement_historique(
        image, monkeypatch):
    """Le graphe est un arbitre, pas un passage obligé : s'il échoue, on
    tente le modèle plutôt que de priver l'épisode d'animation."""
    import pdz.strategies

    def _casse(*a, **k):
        raise RuntimeError("graphe cassé")

    monkeypatch.setattr(pdz.strategies, "choisir", _casse)
    plans = [{"numero": 0, "duree_s": 4.0, "mouvement_sujet": "shouts"}]
    retenus, _ = _filtrer(plans, image)
    assert retenus == {0}


# ── L'importance ────────────────────────────────────────────────────────

def test_le_premier_plan_pese_le_plus():
    """Trois secondes décident de tout."""
    assert _importance({}, 0) > _importance({}, 5)


def test_l_importance_monte_avec_ce_que_le_plan_porte():
    nu = _importance({}, 3)
    charge = _importance({"relance": True, "fonction": "révèle", "emotion": "colere",
                          "intensite_mouvement": "fort"}, 3)
    assert charge > nu
    assert 0.0 <= charge <= 1.0


# ── Le diagnostic distingue les deux raisons de ne pas payer ────────────

def test_ecarte_par_la_strategie_n_est_pas_non_elu():
    """Deux raisons très différentes de ne pas avoir payé. Les confondre
    effacerait l'information la plus utile — et `strategie_locale` est un
    SUCCÈS d'arbitrage, pas un renoncement."""
    assert "strategie_locale" in animation._LECTURE_DIAGNOSTIC
    assert "non_elu" in animation._LECTURE_DIAGNOSTIC
    _, mode, verdict = animation._LECTURE_DIAGNOSTIC["strategie_locale"]
    assert mode is None, "un arbitrage réussi n'est pas un mode d'échec"
    assert verdict == "PASS"


def test_les_deux_sont_attribues_au_repli_local():
    """Ni l'un ni l'autre ne doit compter comme un échec de DIRECT_I2V : ce
    serait inventer des échecs à une stratégie qui n'a rien tenté."""
    for etiquette in ("strategie_locale", "non_elu"):
        cible, mode, _ = animation._LECTURE_DIAGNOSTIC[etiquette]
        assert cible == "repli" and mode is None
