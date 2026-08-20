"""L'épisode compile ses plans en contrats — et ne bloque jamais pour autant.

Cette étape TRACE, elle ne décide pas. Ce qu'elle apporte : pour chaque plan,
la question « peut-il répondre aux cinq questions ? » reçoit une réponse
écrite, et les plans techniquement fragiles sont nommés AVANT la moindre
dépense.

Ce qu'elle n'apporte pas encore, et c'est dit : elle ne change pas ce qu'on
fabrique. Faire décider le rendu par ces contrats demanderait de toucher au
chemin qui dépense dans le même commit qu'un branchement.
"""

from __future__ import annotations

import pytest
import yaml

from pdz import db
from pdz.production.episode import _compiler_contrats
from pdz.production.storyboard import PlanScript
from pdz.univers import Univers

RACINE = __import__("pathlib").Path(__file__).resolve().parent.parent


@pytest.fixture
def base(tmp_path, monkeypatch):
    from pdz.config import Config, config

    config.cache_clear()
    monkeypatch.setattr("pdz.config.config", lambda: Config(donnees=tmp_path))
    monkeypatch.setattr("pdz.db.config", lambda: Config(donnees=tmp_path))
    db.init()
    with db.connexion() as conn:
        conn.execute(
            "INSERT INTO jobs (id, type, statut, entree, profil, budget_max,"
            " cout_total, cree_le, maj_le) VALUES (?,?,?,?,?,?,?,?,?)",
            ("job_1", "video", "en_cours", "{}", "equilibre", 1.0, 0.0,
             db.maintenant(), db.maintenant()),
        )
    yield tmp_path
    config.cache_clear()


@pytest.fixture
def univers() -> Univers:
    donnees = yaml.safe_load(
        (RACINE / "univers" / "fruit-island.yaml").read_text(encoding="utf-8"))
    return Univers.model_validate(donnees)


def _plans() -> list[PlanScript]:
    return [
        PlanScript(numero=0, replique_numero=1, personnage="strawberina",
                   action="avance", emotion="colere", decor="villa", duree_s=3.0,
                   fonction="pose le conflit", mouvement_sujet="turns her head"),
        PlanScript(numero=1, replique_numero=1, personnage="bananito",
                   action="recule", emotion="surprise", duree_s=2.0),
    ]


# ── Ce que l'étape produit ──────────────────────────────────────────────

def test_les_contrats_sont_compiles_pour_chaque_plan(base, univers):
    compiles = _compiler_contrats(_plans(), univers, "job_1")
    assert len(compiles) == 2
    assert [c.spec.id for c in compiles] == ["shot_000", "shot_001"]


def test_un_artefact_contrats_est_journalise(base, univers):
    """Requêtable et versionné, pas seulement écrit dans les journaux."""
    from pdz.moteur import journal

    _compiler_contrats(_plans(), univers, "job_1")
    trace = journal.etape_faite("job_1", "contrats")
    assert trace is not None
    assert len(trace["plans"]) == 2
    assert trace["plans"][0]["mouvement_attendu"] == "sujet"


def test_l_importance_et_le_decor_sont_traces(base, univers):
    from pdz.moteur import journal

    _compiler_contrats(_plans(), univers, "job_1")
    premier = journal.etape_faite("job_1", "contrats")["plans"][0]
    assert premier["importance"] > 0.5, "le premier plan pèse le plus"
    assert premier["decor"] == "villa"


def test_le_decor_se_porte_dans_la_trace(base, univers):
    """Le second plan ne précise aucun décor : il reste dans la scène."""
    from pdz.moteur import journal

    _compiler_contrats(_plans(), univers, "job_1")
    plans = journal.etape_faite("job_1", "contrats")["plans"]
    assert plans[1]["decor"] == "villa"


def test_les_plans_sous_specifies_sont_comptes_sans_etre_inventes(base, univers):
    """Aujourd'hui c'est la totalité d'entre eux, parce qu'aucun PlanScript
    ne porte de `but` explicite. Le dire est le premier pas pour le
    corriger ; l'inventer le rendrait invisible."""
    from pdz.moteur import journal

    _compiler_contrats(_plans(), univers, "job_1")
    plans = journal.etape_faite("job_1", "contrats")["plans"]
    assert all(not p["specifie"] for p in plans)


# ── Ce que l'étape ne fait JAMAIS ───────────────────────────────────────

def test_l_etape_ne_bloque_jamais_la_production(base, univers, monkeypatch):
    """Un instrument de lecture, pas une étape du rendu : perdre la trace
    coûte de la lisibilité, perdre l'épisode coûte la vidéo."""
    import pdz.scenes

    def _casse(*a, **k):
        raise RuntimeError("compilation impossible")

    monkeypatch.setattr(pdz.scenes, "compiler_plans", _casse)
    assert _compiler_contrats(_plans(), univers, "job_1") == ()


def test_un_plan_contradictoire_est_signale_sans_bloquer(base, univers, caplog):
    """Un plan qui exige et interdit la même chose échouera quoi qu'il
    arrive. Le système sait le nommer avant de payer ; il ne sait pas encore
    le réparer seul."""
    plans = _plans()
    plans[0].elements_obligatoires = ["logo", "lettre"]
    plans[0].elements_a_exclure = ["logo"]

    with caplog.at_level("WARNING"):
        compiles = _compiler_contrats(plans, univers, "job_1")
    assert len(compiles) == 2, "la production continue"
    assert any("contradictoires" in m for m in caplog.messages)


def test_une_liste_vide_ne_casse_rien(base, univers):
    assert _compiler_contrats([], univers, "job_1") == ()


def test_l_etape_ne_coute_rien(base, univers):
    """`scenes` n'appelle aucun modèle : tout vient de décisions déjà prises."""
    _compiler_contrats(_plans(), univers, "job_1")
    with db.connexion() as conn:
        cout = conn.execute("SELECT cout_total FROM jobs WHERE id = ?",
                            ("job_1",)).fetchone()
    assert cout["cout_total"] == 0.0
