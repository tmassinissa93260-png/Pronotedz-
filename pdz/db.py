"""Base SQLite — un seul fichier, `donnees/pronotedz.db`.

Choix assumé : sqlite3 de la bibliothèque standard, sans ORM. À un seul
utilisateur, un ORM n'apporterait que des dépendances et de l'indirection.

Les deux tables qui portent tout le système :
  - `etapes`  : une ligne par étape terminée → c'est ce qui rend la reprise possible
  - `appels_ia` : une ligne par appel payant → c'est ce qui rend le coût visible
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pdz.config import config

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ── Un job = une vidéo à produire, ou une vidéo à analyser ──────────────
CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,
    type          TEXT NOT NULL,          -- video_depuis_idee | analyse | remix
    statut        TEXT NOT NULL,          -- en_attente|en_cours|attente_validation
                                          -- |termine|echoue|annule
    entree        TEXT NOT NULL,          -- JSON : idée, sujet, chemin source…
    structure_id  TEXT,                   -- recette appliquée, si remix
    profil        TEXT NOT NULL DEFAULT 'equilibre',
    budget_max    REAL NOT NULL,
    cout_total    REAL NOT NULL DEFAULT 0,
    degrade       INTEGER NOT NULL DEFAULT 0,   -- 1 si repli qualité utilisé
    erreur        TEXT,
    cree_le       REAL NOT NULL,
    maj_le        REAL NOT NULL,
    FOREIGN KEY (structure_id) REFERENCES structures(id)
);
CREATE INDEX IF NOT EXISTS idx_jobs_statut ON jobs(statut, cree_le DESC);

-- ── Une étape terminée = un point de reprise ────────────────────────────
-- L'unicité (job_id, cle) est le socle de la reprise : le moteur ne se
-- « souvient » pas de sa position, il relit ce qui est fait et en déduit
-- ce qui reste.
CREATE TABLE IF NOT EXISTS etapes (
    id          TEXT PRIMARY KEY,
    job_id      TEXT NOT NULL,
    cle         TEXT NOT NULL,
    agent       TEXT NOT NULL,
    statut      TEXT NOT NULL,            -- en_cours|termine|echoue|ignore_cache
    tentative   INTEGER NOT NULL DEFAULT 1,
    empreinte   TEXT,                     -- sha256(entrées+versions) → cache
    resultat    TEXT,                     -- JSON
    cout        REAL NOT NULL DEFAULT 0,
    duree_ms    INTEGER,
    erreur      TEXT,
    cree_le     REAL NOT NULL,
    fini_le     REAL,
    UNIQUE (job_id, cle),
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_etapes_empreinte
    ON etapes(empreinte) WHERE statut = 'termine';

-- ── Les moments où le système m'attend ──────────────────────────────────
CREATE TABLE IF NOT EXISTS validations (
    id         TEXT PRIMARY KEY,
    job_id     TEXT NOT NULL,
    etape_cle  TEXT NOT NULL,
    type       TEXT NOT NULL,             -- script | storyboard | video
    statut     TEXT NOT NULL,             -- en_attente|approuve|rejete|edite
    contenu    TEXT NOT NULL,             -- JSON : ce que je dois regarder
    decision   TEXT,
    edits      TEXT,                      -- JSON : mes corrections
    note       TEXT,
    cree_le    REAL NOT NULL,
    decide_le  REAL,
    UNIQUE (job_id, etape_cle),
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_validations_attente
    ON validations(statut, cree_le) WHERE statut = 'en_attente';

-- ── Les recettes extraites de vidéos qui marchent ───────────────────────
CREATE TABLE IF NOT EXISTS structures (
    id             TEXT PRIMARY KEY,
    nom            TEXT,
    source         TEXT,                  -- chemin ou URL d'origine
    schema_version TEXT NOT NULL DEFAULT '1.0',
    mesures        TEXT NOT NULL,         -- JSON — niveau 1, mesuré
    interpretation TEXT,                  -- JSON — niveau 2, inféré par Claude
    confiance      TEXT,                  -- JSON — confiance par section
    utilisations   INTEGER NOT NULL DEFAULT 0,
    cree_le        REAL NOT NULL
);

-- ── Chaque appel payant, pour savoir où part l'argent ───────────────────
CREATE TABLE IF NOT EXISTS appels_ia (
    id            TEXT PRIMARY KEY,
    job_id        TEXT,
    etape_cle     TEXT,
    agent         TEXT,
    modele        TEXT NOT NULL,
    prompt_ref    TEXT,                   -- id@version du prompt utilisé
    tokens_in     INTEGER NOT NULL DEFAULT 0,
    tokens_out    INTEGER NOT NULL DEFAULT 0,
    tokens_cache  INTEGER NOT NULL DEFAULT 0,
    unites        REAL NOT NULL DEFAULT 0,   -- images, caractères TTS, secondes audio
    cout          REAL NOT NULL DEFAULT 0,
    duree_ms      INTEGER,
    cree_le       REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_appels_date ON appels_ia(cree_le);
CREATE INDEX IF NOT EXISTS idx_appels_job ON appels_ia(job_id);

-- ── Fichiers produits, adressés par leur contenu ────────────────────────
-- Deux jobs qui produisent la même image ne stockent qu'un fichier.
CREATE TABLE IF NOT EXISTS artefacts (
    id       TEXT PRIMARY KEY,
    sha256   TEXT NOT NULL UNIQUE,
    type     TEXT NOT NULL,               -- image | audio | video | sous_titres
    chemin   TEXT NOT NULL,
    taille   INTEGER,
    meta     TEXT,
    refs     INTEGER NOT NULL DEFAULT 1,
    cree_le  REAL NOT NULL
);

-- ── Cache : ne jamais repayer deux fois la même chose ───────────────────
CREATE TABLE IF NOT EXISTS cache (
    empreinte  TEXT PRIMARY KEY,
    valeur     TEXT NOT NULL,             -- JSON
    cout_evite REAL NOT NULL DEFAULT 0,
    cree_le    REAL NOT NULL,
    expire_le  REAL
);
CREATE INDEX IF NOT EXISTS idx_cache_expire ON cache(expire_le);
"""


def nouvel_id(prefixe: str) -> str:
    return f"{prefixe}_{uuid.uuid4().hex[:12]}"


def maintenant() -> float:
    return time.time()


@contextmanager
def connexion(chemin: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Ouvre la base, crée le schéma si besoin, commit ou rollback en sortie."""
    cfg = config()
    cfg.preparer_dossiers()
    conn = sqlite3.connect(chemin or cfg.base_sqlite, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init(chemin: Path | None = None) -> Path:
    """Crée la base et les dossiers. Idempotent."""
    cfg = config()
    with connexion(chemin):
        pass
    return chemin or cfg.base_sqlite


# ── Petits helpers JSON ───────────────────────────────────────────────────

def charger(valeur: str | None, defaut: Any = None) -> Any:
    if not valeur:
        return defaut
    try:
        return json.loads(valeur)
    except json.JSONDecodeError:
        return defaut


def vider(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
