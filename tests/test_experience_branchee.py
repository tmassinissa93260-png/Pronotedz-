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


# ── Le diagnostic précis l'emporte sur l'étiquette ──────────────────────

def test_la_cause_precise_remplace_l_etiquette(memoire):
    """`rejete_mouvement` ne dit que le symptôme. `CAMERA_DOMINANT` dit la
    cause — et deux causes opposées sous une même étiquette rendraient la
    statistique inexploitable pour le routage empirique."""
    from pdz.contracts import FailureDiagnosis, Severite

    cause = FailureDiagnosis(shot_id="shot_000", mode=ModeEchec.CAMERA_DOMINANTE,
                             severite=Severite.CRITIQUE, confiance=0.6)
    _ecrire([PlanAnime(0, "x.mp4", False, "modele", 0.23,
                       diagnostic="rejete_mouvement", cause=cause)])
    assert memoire.toutes()[0].diagnostic is ModeEchec.CAMERA_DOMINANTE


def test_sans_cause_l_etiquette_fait_foi(memoire):
    """Le repli reste correct : une étiquette vaut mieux que rien."""
    _ecrire([PlanAnime(0, "x.mp4", False, "modele", 0.23,
                       diagnostic="rejete_mouvement")])
    assert memoire.toutes()[0].diagnostic is ModeEchec.RENDU_STATIQUE


def test_un_plan_jamais_tente_n_a_aucune_cause(memoire):
    """Il n'y a rien à diagnostiquer d'une génération qui n'a pas eu lieu."""
    _ecrire([PlanAnime(0, "x.mp4", True, "vie", 0.0, diagnostic="non_elu")])
    assert memoire.toutes()[0].diagnostic is None


# ── Le diagnostic produit par l'animation ──────────────────────────────

def _verdict(**extra):
    from pdz.production.verification_mouvement import VerdictMouvement
    base = dict(fichier_valide=True, duree_s=4.8, fps=25.0,
                frames_echantillonnees=24, diff_moyenne=0.509,
                mouvement_detecte=False, raison="static_clip")
    return VerdictMouvement(**{**base, **extra})


@pytest.mark.parametrize("plan,attendu", [
    # Caméra VERROUILLÉE : rien ne peut avoir « mangé » le mouvement du
    # sujet, puisqu'aucun mouvement de caméra n'a été demandé. Ce qui
    # manque est le rendu lui-même.
    ({"mouvement_sujet": "turns her head", "mouvement_camera": "fixe"},
     ModeEchec.RENDU_STATIQUE),
    # Caméra qui DOIT bouger, sujet qui devait bouger, et rien ne bouge :
    # c'est là — et seulement là — que la caméra peut être la cause.
    ({"mouvement_sujet": "turns her head", "mouvement_camera": "pan_lent"},
     ModeEchec.CAMERA_DOMINANTE),
])
def test_l_animation_distingue_des_causes_que_les_etiquettes_confondaient(plan, attendu):
    """Même symptôme mesuré — un clip statique — deux causes opposées, qui
    appellent des corrections inverses.

    Les deux attentes ont été ÉCHANGÉES avec la correction de
    CAMERA_DOMINANT : le diagnostic exige désormais que la caméra ait eu
    le droit de bouger. Diagnostiquer « la caméra domine » sur un plan
    dont la caméra est déjà fixe menait à la réparation CAMERA_FIX, qui
    verrouille une caméra déjà verrouillée — une correction sans effet,
    donc une relance à l'identique, donc une dépense pour un résultat
    déjà mesuré.

    Ce que le test protège n'a pas changé : un même symptôme mesuré porte
    deux causes distinctes. Seule la façon de les distinguer est devenue
    juste."""
    from pdz.production.animation import _diagnostiquer

    diagnostic = _diagnostiquer(_verdict(), plan, 0, duree_requise=4.5)
    assert diagnostic.mode is attendu


def test_un_plan_sans_mouvement_demande_n_est_pas_diagnostique():
    """L'erreur symétrique : un plan qui ne devait pas bouger n'échoue pas
    en ne bougeant pas."""
    from pdz.production.animation import _diagnostiquer

    assert _diagnostiquer(_verdict(), {}, 0, duree_requise=4.5) is None


def test_un_clip_trop_court_est_diagnostique_avant_le_mouvement():
    """Le montage ne peut pas RALLONGER un clip trop court : la vidéo
    s'arrêterait avant la voix."""
    from pdz.production.animation import _diagnostiquer

    diagnostic = _diagnostiquer(_verdict(duree_s=2.0, mouvement_detecte=True),
                                {"mouvement_sujet": "x"}, 1, duree_requise=4.5)
    assert diagnostic.mode is ModeEchec.DUREE_INCORRECTE


def test_le_premier_plan_est_juge_plus_severement():
    """Trois secondes décident de tout."""
    from pdz.contracts import Severite
    from pdz.production.animation import _diagnostiquer

    premier = _diagnostiquer(_verdict(), {"mouvement_sujet": "x"}, 0, duree_requise=4.5)
    suivant = _diagnostiquer(_verdict(), {"mouvement_sujet": "x"}, 5, duree_requise=4.5)
    assert premier.severite is Severite.CRITIQUE
    assert suivant.severite is not Severite.CRITIQUE


def test_le_diagnostic_ne_relance_aucun_echantillonnage(monkeypatch):
    """`depuis_verdict()` et non `observer_clip()` : rappeler la sonde
    relancerait un échantillonnage ffmpeg complet pour recalculer un nombre
    qu'on tient déjà."""
    from pdz.production import verification_mouvement
    from pdz.production.animation import _diagnostiquer

    def _interdit(*a, **k):
        raise AssertionError("la sonde ne doit pas être rappelée")

    monkeypatch.setattr(verification_mouvement, "verifier", _interdit)
    assert _diagnostiquer(_verdict(), {"mouvement_sujet": "x"}, 0,
                          duree_requise=4.5) is not None
