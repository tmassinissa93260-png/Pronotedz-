"""Le journal : une seule autorité sur la reprise, le cache et le point d'arrêt.

Le dépôt en avait deux — `moteur/pipeline.py` et `production/episode.py` —
écrivant dans la même table sans se connaître. Le second produit les vidéos,
donc le chemin réel de production n'avait aucun accès au cache du moteur.

Ces tests protègent trois choses :

  · la **revérification des fichiers**, acquis d'`episode.py` monté au noyau —
    une étape terminée dont le `.mp4` a disparu doit être refaite ;
  · la **distinction reprise / cache** — l'une est par job, l'autre par
    empreinte ; les confondre ferait resservir à un job les fichiers d'un autre ;
  · l'**unicité** — aucun troisième mécanisme ne doit réapparaître.
"""

from __future__ import annotations

import pytest

from pdz import db
from pdz.moteur import journal


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


# ── Reprise ──────────────────────────────────────────────────────────────

def test_une_etape_notee_est_relue_a_l_identique(base):
    journal.noter_etape("job_1", "script", "script", {"titre": "essai"}, cout=0.02)
    assert journal.etape_faite("job_1", "script") == {"titre": "essai"}


def test_une_etape_jamais_faite_rend_none(base):
    assert journal.etape_faite("job_1", "jamais") is None


def test_le_cout_d_une_etape_remonte_sur_le_job(base):
    journal.noter_etape("job_1", "script", "script", {}, cout=0.03)
    journal.noter_etape("job_1", "images", "images", {}, cout=0.05)
    with db.connexion() as conn:
        total = conn.execute("SELECT cout_total FROM jobs WHERE id = ?", ("job_1",)).fetchone()
    assert total["cout_total"] == pytest.approx(0.08)


def test_refaire_une_etape_incremente_sa_tentative(base):
    """Rend visible qu'une étape a été refaite, plutôt que de le masquer
    sous une simple mise à jour."""
    journal.noter_etape("job_1", "script", "script", {"v": 1})
    journal.noter_etape("job_1", "script", "script", {"v": 2})
    with db.connexion() as conn:
        ligne = conn.execute(
            "SELECT tentative FROM etapes WHERE job_id = ? AND cle = ?",
            ("job_1", "script")).fetchone()
    assert ligne["tentative"] == 2
    assert journal.etape_faite("job_1", "script") == {"v": 2}


def test_une_etape_servie_par_le_cache_compte_comme_faite(base):
    """`ignore_cache` est un statut terminé : l'étape est faite, elle n'a
    simplement rien coûté."""
    journal.noter_etape("job_1", "script", "script", {"x": 1}, statut="ignore_cache")
    assert journal.etape_faite("job_1", "script") == {"x": 1}


# ── L'acquis d'episode.py : les fichiers doivent exister ────────────────

def test_une_etape_dont_le_fichier_a_disparu_est_a_refaire(base):
    """Sinon le montage échoue trente secondes plus tard, sur une erreur qui
    ne ressemble plus du tout à sa cause."""
    fichier = base / "plan.mp4"
    fichier.write_bytes(b"x")
    journal.noter_etape("job_1", "animation", "animation", {"clip": str(fichier)})
    assert journal.etape_faite("job_1", "animation") is not None

    fichier.unlink()
    assert journal.etape_faite("job_1", "animation") is None


def test_les_fichiers_sont_cherches_en_profondeur(base):
    """Un chemin oublié au troisième niveau produit exactement le bug que la
    revérification existe pour empêcher."""
    fichier = base / "img.png"
    fichier.write_bytes(b"x")
    resultat = {"plans": [{"visuels": {"image": str(fichier)}}]}
    journal.noter_etape("job_1", "images", "images", resultat)
    assert journal.etape_faite("job_1", "images") is not None
    fichier.unlink()
    assert journal.etape_faite("job_1", "images") is None


def test_une_chaine_qui_n_est_pas_un_fichier_ne_declenche_aucun_acces_disque():
    """Tester `exists()` sur toute chaîne contenant « / » ferait des accès
    disque sur des prompts, des URL et des identifiants."""
    assert journal.fichiers_cites({"prompt": "a cat and/or a dog"}) == []
    assert journal.fichiers_cites({"url": "https://exemple.fr/page"}) == []
    assert journal.fichiers_cites({"clip": "/travail/a.mp4"}) == ["/travail/a.mp4"]


def test_l_extension_est_insensible_a_la_casse():
    assert journal.fichiers_cites({"x": "/t/IMG.PNG"}) == ["/t/IMG.PNG"]


def test_toutes_les_etapes_faites_sont_revues(base):
    bon, mauvais = base / "a.mp3", base / "b.mp4"
    bon.write_bytes(b"x")
    mauvais.write_bytes(b"x")
    journal.noter_etape("job_1", "voix", "voix", {"f": str(bon)})
    journal.noter_etape("job_1", "animation", "animation", {"f": str(mauvais)})
    journal.noter_etape("job_1", "script", "script", {"titre": "t"})

    mauvais.unlink()
    faites = journal.etapes_faites("job_1")
    assert set(faites) == {"voix", "script"}, "l'étape au fichier disparu ne doit pas remonter"


# ── Correction humaine ───────────────────────────────────────────────────

def test_une_correction_humaine_efface_l_empreinte(base):
    """Le contenu ne correspond plus à ce que l'agent avait produit : garder
    l'empreinte servirait un jour ce résultat corrigé comme s'il venait du
    modèle."""
    journal.noter_etape("job_1", "script", "script", {"v": 1}, empreinte="abc123")
    journal.reecrire_etape("job_1", "script", {"v": "corrigé"})
    with db.connexion() as conn:
        ligne = conn.execute(
            "SELECT empreinte FROM etapes WHERE job_id = ? AND cle = ?",
            ("job_1", "script")).fetchone()
    assert ligne["empreinte"] is None
    assert journal.etape_faite("job_1", "script") == {"v": "corrigé"}


# ── Cache : par empreinte, pas par job ──────────────────────────────────

def test_le_cache_sert_un_resultat_identique(base):
    journal.ecrire_cache("emp1", {"titre": "x"}, cout_evite=0.02)
    assert journal.lire_cache("emp1") == {"titre": "x"}


def test_une_empreinte_inconnue_ne_rend_rien(base):
    assert journal.lire_cache("jamais_vue") is None


def test_une_entree_de_cache_expiree_est_supprimee(base):
    journal.ecrire_cache("emp1", {"x": 1}, cout_evite=0.0, ttl_s=-1)
    assert journal.lire_cache("emp1") is None
    with db.connexion() as conn:
        reste = conn.execute("SELECT COUNT(*) c FROM cache").fetchone()
    assert reste["c"] == 0, "une entrée expirée est purgée, pas seulement ignorée"


def test_un_cache_dont_les_fichiers_ont_disparu_est_rejete(base):
    """Même acquis que pour la reprise : servir un cache mort ferait échouer
    le montage bien plus tard, avec une erreur méconnaissable."""
    fichier = base / "c.mp4"
    fichier.write_bytes(b"x")
    journal.ecrire_cache("emp1", {"clip": str(fichier)}, cout_evite=0.05)
    assert journal.lire_cache("emp1") is not None

    fichier.unlink()
    assert journal.lire_cache("emp1") is None
    with db.connexion() as conn:
        reste = conn.execute("SELECT COUNT(*) c FROM cache").fetchone()
    assert reste["c"] == 0


def test_reprise_et_cache_restent_distincts(base):
    """La reprise est par JOB, le cache par EMPREINTE. Les confondre ferait
    resservir à un job les fichiers d'un autre."""
    journal.noter_etape("job_1", "script", "script", {"v": "du job"})
    journal.ecrire_cache("emp1", {"v": "du cache"}, cout_evite=0.0)
    assert journal.etape_faite("job_1", "script") == {"v": "du job"}
    assert journal.lire_cache("emp1") == {"v": "du cache"}
    assert journal.etape_faite("job_2", "script") is None
