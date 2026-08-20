"""L'animation écrit ce qu'elle a réellement fait — sinon la phase 19 reste
verrouillée pour toujours.

Le piège central, et c'est tout l'enjeu de ce fichier : **un plan jamais tenté
au modèle ne doit pas être enregistré comme un échec du modèle.** Ce serait
inventer des échecs à une stratégie qui n'a rien tenté, et le taux de réussite
qu'on en tirerait serait faux dans le sens qui coûte le plus cher — celui qui
fait renoncer à ce qui marche.
"""

from __future__ import annotations

import pytest

from pdz import db
from pdz.contracts import Certitude, ModeEchec, Strategie
from pdz.memory import ExperienceMemory, performance_par_strategie
from pdz.production.animation import PlanAnime, _enregistrer_experience


@pytest.fixture
def memoire(tmp_path, monkeypatch):
    from pdz.config import Config, config

    config.cache_clear()
    monkeypatch.setattr("pdz.config.config", lambda: Config(donnees=tmp_path))
    monkeypatch.setattr("pdz.db.config", lambda: Config(donnees=tmp_path))
    db.init()
    yield ExperienceMemory()
    config.cache_clear()


def _plans(n: int = 3) -> list[dict]:
    return [{"numero": i, "duree_s": 3.0} for i in range(n)]


def _ecrire(resultats, *, job_id="job_1", plans=None):
    _enregistrer_experience(resultats, plans or _plans(), job_id=job_id,
                            profil="equilibre")


# ── Ce qui est enregistré, et comme quoi ────────────────────────────────

def test_un_clip_modele_confirme_est_une_reussite_de_direct_i2v(memoire):
    _ecrire([PlanAnime(0, "x.mp4", True, "modele", 0.23,
                       diagnostic="mouvement_confirme")])
    ligne = memoire.toutes()[0]
    assert ligne.strategie is Strategie.DIRECT_I2V
    assert ligne.resultat == "PASS"
    assert ligne.diagnostic is None
    assert ligne.cout_reel_eur == pytest.approx(0.23)


def test_un_clip_statique_est_un_rendu_statique(memoire):
    _ecrire([PlanAnime(0, "x.mp4", False, "modele", 0.23,
                       diagnostic="rejete_mouvement")])
    ligne = memoire.toutes()[0]
    assert ligne.diagnostic is ModeEchec.RENDU_STATIQUE
    assert ligne.resultat == "FAIL"
    assert ligne.cout_reel_eur > 0, "un clip rejeté a coûté malgré tout"


def test_un_clip_trop_court_est_une_duree_incorrecte(memoire):
    _ecrire([PlanAnime(0, "x.mp4", False, "modele", 0.23, diagnostic="rejete_duree")])
    assert memoire.toutes()[0].diagnostic is ModeEchec.DUREE_INCORRECTE


@pytest.mark.parametrize("diagnostic", ["timeout", "erreur_appel"])
def test_une_erreur_de_fournisseur_n_est_pas_un_mode_d_echec_du_rendu(memoire, diagnostic):
    """Le modèle n'a rien produit qu'on puisse juger. Le confondre avec un
    rendu statique fausserait la taxonomie."""
    _ecrire([PlanAnime(0, "x.jpg", False, "modele", 0.0, diagnostic=diagnostic)])
    assert memoire.toutes()[0].diagnostic is ModeEchec.INCONNU


# ── LE piège : ne pas inventer d'échecs ─────────────────────────────────

@pytest.mark.parametrize("diagnostic", ["non_elu", "hors_portee"])
def test_un_plan_jamais_tente_n_est_pas_un_echec_du_modele(memoire, diagnostic):
    """Le cœur du fichier. Enregistrer ces plans comme des `DIRECT_I2V`
    ratés ferait chuter un taux de réussite que le modèle n'a jamais eu
    l'occasion de tenir."""
    _ecrire([PlanAnime(0, "x.mp4", True, "vie", 0.0, diagnostic=diagnostic)])
    ligne = memoire.toutes()[0]
    assert ligne.strategie is Strategie.DEUX_ET_DEMI_D
    assert ligne.resultat == "PASS"
    assert ligne.diagnostic is None


def test_les_plans_non_elus_ne_polluent_pas_la_statistique_du_modele(memoire):
    """Trois plans en repli, un seul tenté : le modèle doit avoir un
    échantillon de 1, pas de 4."""
    _ecrire([
        PlanAnime(0, "a.mp4", True, "modele", 0.23, diagnostic="mouvement_confirme"),
        PlanAnime(1, "b.mp4", True, "vie", 0.0, diagnostic="non_elu"),
        PlanAnime(2, "c.jpg", False, "camera", 0.0, diagnostic="non_elu"),
    ])
    perf = performance_par_strategie(memoire.toutes())
    assert perf["DIRECT_I2V"].echantillon == 1
    assert perf["DIRECT_I2V"].taux_de_reussite == 1.0
    assert perf["TWO_POINT_FIVE_D"].echantillon == 1


def test_le_repli_local_est_attribue_a_la_bonne_strategie(memoire):
    _ecrire([
        PlanAnime(0, "a.mp4", True, "vie", 0.0, diagnostic="rejete_mouvement"),
        PlanAnime(1, "b.jpg", False, "camera", 0.0, diagnostic="non_elu"),
    ])
    strategies = {r.strategie for r in memoire.toutes()}
    assert strategies == {Strategie.DEUX_ET_DEMI_D, Strategie.PROCEDURAL}


def test_un_repli_local_n_est_jamais_attribue_a_un_fournisseur(memoire):
    _ecrire([PlanAnime(0, "a.mp4", True, "vie", 0.0, diagnostic="non_elu")])
    ligne = memoire.toutes()[0]
    assert ligne.fournisseur == "local"
    assert ligne.capacites_requises == ()


# ── Honnêteté du verdict ────────────────────────────────────────────────

def test_le_verdict_reste_un_heuristique(memoire):
    """Il vient d'une sonde de mouvement, qui mesure des pixels et non la
    réussite narrative du plan. Le déclarer FAIT reviendrait à confondre
    « ça bouge » et « ça montre ce qu'il fallait »."""
    _ecrire([PlanAnime(0, "x.mp4", True, "modele", 0.23,
                       diagnostic="mouvement_confirme")])
    ligne = memoire.toutes()[0]
    assert ligne.certitude is Certitude.HEURISTIQUE
    assert not ligne.certitude.est_fiable


def test_chaque_ligne_est_exploitable(memoire):
    """Une ligne sans stratégie, sans modèle ou sans résultat est du bruit :
    l'agréger ferait bouger des moyennes sans rien signifier."""
    _ecrire([
        PlanAnime(0, "a.mp4", True, "modele", 0.23, diagnostic="mouvement_confirme"),
        PlanAnime(1, "b.mp4", True, "vie", 0.0, diagnostic="non_elu"),
        PlanAnime(2, "c.jpg", False, "camera", 0.0, diagnostic="non_elu"),
    ])
    assert all(r.exploitable for r in memoire.toutes())


# ── Ce qui ne doit RIEN écrire ──────────────────────────────────────────

def test_sans_job_rien_n_est_ecrit(memoire):
    """Les démonstrations et les outils n'ont pas de job, et leurs résultats
    ne décrivent pas une production réelle. Les compter fausserait les
    statistiques avec des cas de test."""
    _ecrire([PlanAnime(0, "x.mp4", True, "modele", 0.23,
                       diagnostic="mouvement_confirme")], job_id=None)
    assert memoire.toutes() == []


def test_une_erreur_d_ecriture_n_interrompt_pas_la_production(memoire, monkeypatch):
    """Une mémoire d'expérience est un instrument de mesure, pas une étape
    du rendu. Perdre une ligne coûte une observation ; perdre l'épisode
    coûte la vidéo."""
    def _casse(self, record):
        raise RuntimeError("disque plein")

    monkeypatch.setattr(ExperienceMemory, "enregistrer", _casse)
    _ecrire([PlanAnime(0, "x.mp4", True, "modele", 0.23,
                       diagnostic="mouvement_confirme")])  # ne lève pas


def test_un_diagnostic_inconnu_ne_casse_rien(memoire):
    """Un diagnostic qu'on n'a pas prévu ne doit ni lever, ni être compté
    comme une réussite."""
    _ecrire([PlanAnime(0, "x.mp4", True, "vie", 0.0, diagnostic="jamais_vu")])
    ligne = memoire.toutes()[0]
    assert ligne.resultat == ""
    assert not ligne.exploitable, "une ligne sans verdict est du bruit"


def test_un_resultat_hors_bornes_des_plans_ne_leve_pas(memoire):
    """`resultats` et `plans` peuvent diverger sur un chemin d'erreur : la
    mémoire ne doit pas être ce qui fait tomber la production."""
    _ecrire([PlanAnime(7, "x.mp4", True, "vie", 0.0, diagnostic="non_elu")],
            plans=_plans(2))
    assert memoire.toutes()[0].duree_demandee_s == 0.0
