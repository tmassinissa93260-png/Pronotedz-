"""La mémoire d'expérience collecte, et ne prétend rien de plus.

Ce que ces tests protègent :

  · **une ligne par TENTATIVE** — un plan réparé trois fois en produit
    trois. Agréger par plan effacerait ce qu'on cherche à mesurer ;
  · **l'idempotence** — reprendre un job ne duplique pas ses expériences,
    ce qui gonflerait les échantillons sans qu'aucune tentative de plus
    n'ait eu lieu ;
  · **`None` ≠ `0.0`** — « on n'a jamais essayé » et « ça échoue toujours »
    sont deux informations opposées ;
  · **le bruit n'entre pas** dans les moyennes.
"""

from __future__ import annotations

import pytest

from pdz import db
from pdz.contracts import Certitude, ExperienceRecord, ModeEchec, Strategie, TypeReparation
from pdz.memory import ExperienceMemory, performance_par_modele, performance_par_strategie
from pdz.memory.experience import ECHANTILLON_MINIMAL


@pytest.fixture
def memoire(tmp_path, monkeypatch):
    """Une base neuve par test — sinon les expériences d'un test faussent
    les statistiques du suivant, ce qui est précisément le bug que ce
    module doit rendre impossible en production."""
    from pdz.config import Config, config

    config.cache_clear()
    monkeypatch.setenv("DONNEES", str(tmp_path))
    monkeypatch.setattr("pdz.config.config", lambda: Config(donnees=tmp_path))
    monkeypatch.setattr("pdz.db.config", lambda: Config(donnees=tmp_path))
    db.init()
    yield ExperienceMemory()
    config.cache_clear()


def _record(**extra) -> ExperienceRecord:
    base = dict(job_id="job_1", shot_id="shot_003", tentative=1,
                strategie=Strategie.DIRECT_I2V, backend="fal", modele="kling",
                fournisseur="fal", cout_estime_eur=0.05, cout_reel_eur=0.046,
                latence_ms=94_000, resultat="PASS")
    return ExperienceRecord(**{**base, **extra})


# ── Collecte ─────────────────────────────────────────────────────────────

def test_une_tentative_est_ecrite_et_relue_a_l_identique(memoire):
    identifiant = memoire.enregistrer(_record())
    relu = memoire.lire(identifiant)
    assert relu is not None
    assert relu.modele == "kling"
    assert relu.cout_reel_eur == pytest.approx(0.046)
    assert relu.strategie is Strategie.DIRECT_I2V


def test_chaque_tentative_est_une_ligne(memoire):
    """Un plan réparé trois fois produit trois enregistrements."""
    for n in (1, 2, 3):
        memoire.enregistrer(_record(tentative=n, resultat="FAIL" if n < 3 else "PASS"))
    tentatives = memoire.tentatives("job_1", "shot_003")
    assert [t.tentative for t in tentatives] == [1, 2, 3]
    assert [t.resultat for t in tentatives] == ["FAIL", "FAIL", "PASS"]


def test_reprendre_un_job_ne_duplique_pas_ses_experiences(memoire):
    """Sinon l'échantillon gonfle sans qu'aucune tentative de plus n'ait eu
    lieu — et la confiance accordée au chiffre avec lui."""
    memoire.enregistrer(_record(resultat="FAIL"))
    memoire.enregistrer(_record(resultat="PASS"))     # même job/plan/tentative
    tentatives = memoire.tentatives("job_1")
    assert len(tentatives) == 1
    assert tentatives[0].resultat == "PASS", "la relance met à jour, elle n'ajoute pas"


def test_l_histoire_d_une_reparation_se_lit_tentative_par_tentative(memoire):
    memoire.enregistrer(_record(tentative=1, resultat="FAIL",
                                diagnostic=ModeEchec.CAMERA_DOMINANTE))
    memoire.enregistrer(_record(tentative=2, resultat="PASS",
                                reparation=TypeReparation.AJUSTER_CAMERA))
    histoire = memoire.tentatives("job_1", "shot_003")
    assert histoire[0].diagnostic is ModeEchec.CAMERA_DOMINANTE
    assert histoire[1].reparation is TypeReparation.AJUSTER_CAMERA


def test_les_tentatives_d_un_autre_job_ne_se_melangent_pas(memoire):
    memoire.enregistrer(_record(job_id="job_1"))
    memoire.enregistrer(_record(job_id="job_2"))
    assert len(memoire.tentatives("job_1")) == 1


def test_un_identifiant_inconnu_rend_none(memoire):
    assert memoire.lire("exp_inexistant") is None


# ── Analyse ──────────────────────────────────────────────────────────────

def test_la_performance_compte_reussites_echecs_et_incertains(memoire):
    for n, resultat in enumerate(["PASS", "PASS", "FAIL", "UNCERTAIN"], start=1):
        memoire.enregistrer(_record(shot_id=f"s{n}", resultat=resultat))
    perf = performance_par_strategie(memoire.toutes())["DIRECT_I2V"]
    assert (perf.echantillon, perf.reussites, perf.echecs, perf.incertains) == (4, 2, 1, 1)
    assert perf.taux_de_reussite == pytest.approx(0.5)


def test_une_strategie_jamais_essayee_rend_none_pas_zero(memoire):
    """« On n'a jamais essayé » et « ça échoue toujours » sont deux
    informations opposées. Les confondre éliminerait pour toujours une
    stratégie qu'on n'a jamais tentée."""
    from pdz.memory.experience import Performance

    jamais = Performance(cle="TWO_POINT_FIVE_D", echantillon=0, reussites=0,
                         echecs=0, incertains=0, cout_total_eur=0.0,
                         latence_moyenne_ms=0.0)
    assert jamais.taux_de_reussite is None

    memoire.enregistrer(_record(resultat="FAIL"))
    toujours_ratee = performance_par_strategie(memoire.toutes())["DIRECT_I2V"]
    assert toujours_ratee.taux_de_reussite == 0.0


def test_une_ligne_sans_conclusion_n_entre_pas_dans_les_moyennes(memoire):
    """Du bruit : la compter ferait bouger des moyennes sans rien signifier."""
    memoire.enregistrer(_record(shot_id="s1", resultat="PASS"))
    memoire.enregistrer(_record(shot_id="s2", resultat=""))
    perf = performance_par_strategie(memoire.toutes())["DIRECT_I2V"]
    assert perf.echantillon == 1


def test_un_petit_echantillon_se_declare_non_significatif(memoire):
    """Le seuil ne bloque rien : il décide si une statistique a le droit de
    se présenter comme telle."""
    memoire.enregistrer(_record())
    assert not performance_par_strategie(memoire.toutes())["DIRECT_I2V"].significative

    for n in range(ECHANTILLON_MINIMAL):
        memoire.enregistrer(_record(shot_id=f"s{n}"))
    assert performance_par_strategie(memoire.toutes())["DIRECT_I2V"].significative


def test_strategie_et_modele_sont_agreges_separement(memoire):
    """`2.5D` peut être rendu par plusieurs moteurs, et un modèle peut servir
    plusieurs stratégies : les agréger masquerait lequel est en cause."""
    memoire.enregistrer(_record(shot_id="s1", strategie=Strategie.DIRECT_I2V,
                                modele="kling", resultat="PASS"))
    memoire.enregistrer(_record(shot_id="s2", strategie=Strategie.DEUX_ET_DEMI_D,
                                modele="local-vie", resultat="PASS"))
    memoire.enregistrer(_record(shot_id="s3", strategie=Strategie.DIRECT_I2V,
                                modele="local-vie", resultat="FAIL"))

    par_strategie = performance_par_strategie(memoire.toutes())
    par_modele = performance_par_modele(memoire.toutes())
    assert par_strategie["DIRECT_I2V"].echantillon == 2
    assert par_modele["local-vie"].echantillon == 2
    assert par_modele["local-vie"].reussites == 1


def test_le_cout_par_reussite_est_none_sans_aucune_reussite(memoire):
    memoire.enregistrer(_record(resultat="FAIL", cout_reel_eur=0.05))
    assert performance_par_strategie(memoire.toutes())["DIRECT_I2V"].cout_par_reussite_eur is None


def test_le_cout_par_reussite_agrege_les_echecs_payes(memoire):
    """Un échec coûte quand même : le prix d'une réussite inclut ce qu'on a
    payé pour les tentatives ratées qui l'ont précédée."""
    memoire.enregistrer(_record(shot_id="s1", resultat="FAIL", cout_reel_eur=0.04))
    memoire.enregistrer(_record(shot_id="s2", resultat="PASS", cout_reel_eur=0.06))
    perf = performance_par_strategie(memoire.toutes())["DIRECT_I2V"]
    assert perf.cout_par_reussite_eur == pytest.approx(0.10)


def test_une_memoire_vide_ne_casse_rien(memoire):
    assert performance_par_strategie(memoire.toutes()) == {}
    assert memoire.toutes() == []


# ── Honnêteté ────────────────────────────────────────────────────────────

def test_la_certitude_voyage_avec_la_qualite(memoire):
    """Une qualité de 0,9 issue d'un heuristique reste un heuristique."""
    identifiant = memoire.enregistrer(_record(qualite=0.9, certitude=Certitude.HEURISTIQUE))
    relu = memoire.lire(identifiant)
    assert relu.qualite == pytest.approx(0.9)
    assert relu.certitude is Certitude.HEURISTIQUE
    assert not relu.certitude.est_fiable


def test_l_ecart_de_cout_est_mesurable(memoire):
    """Un écart systématique invalide l'arbitrage coût/valeur bien avant
    qu'il n'invalide le budget."""
    relu = memoire.lire(memoire.enregistrer(_record(cout_estime_eur=0.05,
                                                    cout_reel_eur=0.12)))
    assert relu.ecart_de_cout == pytest.approx(0.07)


def test_la_signature_permet_de_reperer_un_fournisseur_non_deterministe(memoire):
    """Même signature d'entrée, résultats différents : aucune moyenne ne le
    montrerait, la signature si."""
    memoire.enregistrer(_record(shot_id="s1", signature_entrees="abc", resultat="PASS"))
    memoire.enregistrer(_record(shot_id="s2", signature_entrees="abc", resultat="FAIL"))
    resultats = {r.resultat for r in memoire.toutes() if r.signature_entrees == "abc"}
    assert resultats == {"PASS", "FAIL"}
