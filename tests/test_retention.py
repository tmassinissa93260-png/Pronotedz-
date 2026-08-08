"""Les résultats des publications : import, association, et refus de conclure.

Le test le plus important de ce fichier est le dernier : avec cinq épisodes,
le module doit **refuser de tirer une leçon**. Un outil qui annonce « les hooks
courts marchent 40 % mieux » sur cinq vidéos ne mesure que du bruit, et il est
plus nuisible que pas d'outil du tout.
"""

from __future__ import annotations

import json

import pytest

from pdz import db
from pdz.analyse import retention
from pdz.moteur.erreurs import ErreurPdz


@pytest.fixture
def base(tmp_path, monkeypatch):
    monkeypatch.setenv("DONNEES", str(tmp_path / "donnees"))
    from pdz.config import config
    config.cache_clear()
    db.init()
    yield tmp_path
    config.cache_clear()


def _episode(titre: str, *, mots_hook: int = 9, repliques: int = 12,
             animes: int = 2) -> str:
    """Crée un job terminé, avec son script et sa bande voix, comme en vrai."""
    job_id = db.nouvel_id("job")
    script = {
        "titre": titre,
        "repliques": [
            {"numero": i + 1, "personnage": "a",
             "replique": " ".join(["mot"] * (mots_hook if i == 0 else 8)),
             "emotion": "colere" if i == 0 else "calme",
             "relance": i in (3, 7)}
            for i in range(repliques)
        ],
    }
    plans = [{"index": i, "anime": i < animes, "methode": "modele",
              "fichier": f"/x/{i}.mp4"} for i in range(repliques)]

    with db.connexion() as conn:
        conn.execute(
            "INSERT INTO jobs (id, type, statut, entree, profil, budget_max,"
            " cree_le, maj_le) VALUES (?,?,?,?,?,?,?,?)",
            (job_id, "video_depuis_idee", "termine",
             json.dumps({"univers": "u", "situation": "s"}),
             "equilibre", 1.0, db.maintenant(), db.maintenant()),
        )
        for cle, resultat in (
            ("script", script),
            ("voix", {"durees_couvrantes_s": [3.5] * repliques}),
            ("animation", {"plans": plans}),
        ):
            conn.execute(
                "INSERT INTO etapes (id, job_id, cle, agent, statut, resultat,"
                " cree_le, fini_le) VALUES (?,?,?,?,?,?,?,?)",
                (db.nouvel_id("etp"), job_id, cle, cle, "termine",
                 db.vider(resultat), db.maintenant(), db.maintenant()),
            )
    return job_id


def _csv(tmp_path, lignes, entetes="Titre,Vues,Taux de completion"):
    chemin = tmp_path / "export.csv"
    chemin.write_text(entetes + "\n" + "\n".join(lignes), encoding="utf-8")
    return chemin


# ── Lecture des exports ──────────────────────────────────────────────────

def test_les_colonnes_sont_reperees_en_francais():
    colonnes = retention.reperer_colonnes(
        ["Titre", "Vues", "J'aime", "Partages", "Taux de complétion"]
    )
    assert colonnes["titre"] == "Titre"
    assert colonnes["vues"] == "Vues"
    assert colonnes["taux_completion"] == "Taux de complétion"


def test_les_colonnes_sont_reperees_en_anglais():
    colonnes = retention.reperer_colonnes(
        ["Video title", "Views", "Likes", "Average watch time", "Completion rate"]
    )
    assert colonnes["titre"] == "Video title"
    assert colonnes["duree_moyenne_s"] == "Average watch time"
    assert colonnes["taux_completion"] == "Completion rate"


def test_lordre_des_colonnes_est_indifferent():
    colonnes = retention.reperer_colonnes(["Views", "Titre", "Shares"])
    assert colonnes["titre"] == "Titre" and colonnes["vues"] == "Views"


@pytest.mark.parametrize("brut,attendu", [
    ("12 345", 12345.0),
    ("1.2K", 1200.0),
    ("3M", 3_000_000.0),
    ("43%", 0.43),
    ("12,5", 12.5),
    ("00:00:07", 7.0),
    ("1:30", 90.0),
    ("", 0.0),
    (None, 0.0),
    ("n/a", 0.0),
])
def test_les_nombres_des_exports_sont_lus(brut, attendu):
    """Chaque plateforme écrit ses nombres à sa façon, et change d'avis."""
    assert retention._nombre(brut) == pytest.approx(attendu)


def test_un_export_sans_titre_echoue_avec_les_colonnes_trouvees(base):
    chemin = _csv(base, ["100,0.4"], entetes="Vues,Taux")
    with pytest.raises(ErreurPdz) as e:
        retention.importer(chemin)
    assert "Vues" in str(e.value)


def test_un_export_vide_echoue_clairement(base):
    chemin = base / "vide.csv"
    chemin.write_text("", encoding="utf-8")
    with pytest.raises(ErreurPdz):
        retention.importer(chemin)


# ── Association aux épisodes produits ────────────────────────────────────

def test_un_export_est_associe_par_le_titre(base):
    job_id = _episode("La dernière rose")
    chemin = _csv(base, ["La dernière rose,4200,0.51", "Une autre vidéo,900,0.22"])

    lus, associes = retention.importer(chemin)
    assert (lus, associes) == (2, 1)

    with db.connexion() as conn:
        ligne = conn.execute(
            "SELECT * FROM publications WHERE job_id = ?", (job_id,)
        ).fetchone()
    assert ligne["vues"] == 4200
    assert ligne["taux_completion"] == pytest.approx(0.51)


def test_les_lignes_non_associees_sont_gardees(base):
    """Les résultats d'une vidéo faite à la main restent utiles à voir."""
    chemin = _csv(base, ["Vidéo faite ailleurs,1000,0.3"])
    retention.importer(chemin)
    with db.connexion() as conn:
        n = conn.execute("SELECT COUNT(*) n FROM publications").fetchone()["n"]
    assert n == 1


def test_reimporter_met_a_jour_au_lieu_de_dupliquer(base):
    _episode("Mon épisode")
    retention.importer(_csv(base, ["Mon épisode,100,0.30"]))
    retention.importer(_csv(base, ["Mon épisode,5000,0.62"]))

    with db.connexion() as conn:
        lignes = conn.execute("SELECT * FROM publications").fetchall()
    assert len(lignes) == 1
    assert lignes[0]["vues"] == 5000


def test_un_taux_donne_sur_100_est_ramene_sur_1(base):
    _episode("Ep")
    retention.importer(_csv(base, ["Ep,100,43"]))
    with db.connexion() as conn:
        ligne = conn.execute("SELECT taux_completion FROM publications").fetchone()
    assert ligne["taux_completion"] == pytest.approx(0.43)


def test_publier_a_la_main_fonctionne_aussi(base):
    job_id = _episode("Un titre")
    publication_id = retention.enregistrer(job_id, "tiktok", url="https://x")
    assert publication_id.startswith("pub_")

    with db.connexion() as conn:
        ligne = conn.execute("SELECT * FROM publications WHERE id = ?",
                             (publication_id,)).fetchone()
    assert ligne["titre"] == "Un titre"       # repris du script tout seul


def test_publier_un_job_inconnu_echoue(base):
    with pytest.raises(ErreurPdz) as e:
        retention.enregistrer("job_inexistant", "tiktok")
    assert "introuvable" in str(e.value)


# ── Les caractéristiques d'un épisode ────────────────────────────────────

def test_les_reglages_de_production_sont_relus(base):
    job_id = _episode("X", mots_hook=6, repliques=10, animes=3)
    traits = retention.caracteristiques(job_id)
    assert traits["mots_du_hook"] == 6
    assert traits["nb_repliques"] == 10
    assert traits["plans_animes"] == 3
    assert traits["hook_emotion_forte"] == 1.0
    assert traits["relances"] == 2


def test_un_job_sans_script_ne_donne_rien(base):
    assert retention.caracteristiques("job_vide") == {}


# ── Le refus de conclure ─────────────────────────────────────────────────

def _catalogue(base, combien: int, hooks: list[int], completions: list[float]):
    for i in range(combien):
        job_id = _episode(f"Episode {i}", mots_hook=hooks[i % len(hooks)])
        retention.enregistrer(job_id, "tiktok")
        with db.connexion() as conn:
            conn.execute(
                "UPDATE publications SET taux_completion = ?, vues = ?"
                " WHERE job_id = ?",
                (completions[i % len(completions)], 1000 + i * 10, job_id),
            )


def test_sans_publication_le_bilan_le_dit_sans_planter(base):
    b = retention.bilan()
    assert b.publications == []
    assert "Aucune publication" in b.resume()


def test_sous_dix_episodes_rien_nest_concluable(base):
    """Le test qui compte. Cinq épisodes avec un écart énorme et bien net :
    le module doit quand même refuser d'en tirer une leçon."""
    _catalogue(base, 5, hooks=[4, 4, 14, 14, 4], completions=[0.7, 0.7, 0.2, 0.2, 0.7])
    b = retention.bilan()

    assert not b.assez_de_donnees
    assert "10" in b.resume()
    assert any("indiscernable du hasard" in m for m in b.avertissements())


def test_au_dela_du_seuil_lecart_est_rapporte(base):
    _catalogue(base, 12, hooks=[4, 14], completions=[0.70, 0.25])
    b = retention.bilan()

    assert b.assez_de_donnees
    hook = next(f for f in b.facteurs if "première réplique" in f.nom)
    assert hook.exploitable
    # Les hooks longs sont associés à une complétion plus basse : l'écart
    # doit être négatif, et net.
    assert hook.ecart_pct < -40, hook.resume()


def test_un_groupe_trop_petit_est_marque_non_exploitable(base):
    """11 épisodes à hook court, 1 seul à hook long : rien à comparer."""
    _catalogue(base, 12, hooks=[4] * 11 + [14], completions=[0.5])
    b = retention.bilan()
    hook = next((f for f in b.facteurs if "première réplique" in f.nom), None)
    if hook is not None:
        assert not hook.exploitable


def test_un_reglage_qui_na_jamais_varie_nest_pas_compare(base):
    _catalogue(base, 12, hooks=[9], completions=[0.4, 0.5])
    b = retention.bilan()
    assert all("première réplique" not in f.nom for f in b.facteurs)


def test_les_avertissements_sont_toujours_la(base):
    """Un tableau de corrélations sans son avertissement se lit comme une
    explication. Il ne doit jamais pouvoir être affiché seul."""
    _catalogue(base, 12, hooks=[4, 14], completions=[0.7, 0.2])
    messages = retention.bilan().avertissements()
    assert any("associations, pas des causes" in m for m in messages)
    assert any("sujet" in m for m in messages)
