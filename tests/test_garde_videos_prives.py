"""Tests du garde-fou anti-vidéo-privée (scripts/verifier_videos_prives.py).

Contexte : `.gitignore` protège `git add` en local, mais pas l'upload web
de GitHub (qui l'ignore complètement — voir TELEPHONE.md, étape 5). Ce
garde-fou est une sécurité SUPPLÉMENTAIRE, testée ici sur sa seule
responsabilité : détecter une extension vidéo dans un dossier sensible.
Il ne remplace ni la vigilance humaine ni la vérification CI qui, elle,
voit aussi les fichiers arrivés par le web.

Aucune vraie vidéo dans ce fichier — uniquement des chemins et, pour les
tests touchant au vrai `.gitignore`, un fichier synthétique de quelques
octets, nettoyé immédiatement après.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.verifier_videos_prives import chemins_interdits

RACINE = Path(__file__).resolve().parent.parent


# ── La logique de détection, pure ───────────────────────────────────────

def test_un_mp4_dans_donnees_references_est_detecte():
    assert chemins_interdits(["donnees/references/clip.mp4"]) == [
        "donnees/references/clip.mp4"
    ]


def test_un_mp4_dans_donnees_sources_est_detecte():
    assert chemins_interdits(["donnees/sources/reference.mp4"]) == [
        "donnees/sources/reference.mp4"
    ]


def test_toutes_les_extensions_video_courantes_sont_detectees():
    chemins = [f"donnees/references/clip{ext}"
               for ext in (".mp4", ".mov", ".webm", ".mkv", ".avi")]
    assert chemins_interdits(chemins) == chemins


def test_la_detection_est_insensible_a_la_casse():
    assert chemins_interdits(["donnees/references/Clip.MP4"]) == [
        "donnees/references/Clip.MP4"
    ]


def test_un_fichier_normal_nest_jamais_bloque():
    """Un fichier normal continue de fonctionner : rien n'est signalé."""
    assert chemins_interdits([
        "donnees/references/notes.yaml",
        "donnees/references/exemple.univers.yaml",
        "pdz/cli.py",
        "README.md",
    ]) == []


def test_une_video_hors_dun_dossier_sensible_nest_pas_signalee():
    """Portée volontairement limitée à `donnees/` : c'est là que le risque
    est concret, pas une interdiction générale de committer un .mp4."""
    assert chemins_interdits(["assets/demo.mp4"]) == []


def test_lignes_vides_ignorees():
    assert chemins_interdits(["", "  ", "donnees/references/clip.mp4"]) == [
        "donnees/references/clip.mp4"
    ]


def test_seuls_les_chemins_interdits_sont_retenus_parmi_un_melange():
    chemins = [
        "pdz/cli.py",
        "donnees/references/clip.mp4",
        "tests/test_cli.py",
        "donnees/sources/reference.mov",
        "README.md",
    ]
    assert chemins_interdits(chemins) == [
        "donnees/references/clip.mp4",
        "donnees/sources/reference.mov",
    ]


# ── Le vrai .gitignore du dépôt ─────────────────────────────────────────

def test_donnees_references_est_ignore_par_git():
    """`donnees/` est dans .gitignore : un fichier qui y atterrit ne doit
    jamais être proposé au suivi par un `git add` ordinaire."""
    resultat = subprocess.run(
        ["git", "check-ignore", "-q", "donnees/references/un-fichier-test.mp4"],
        cwd=RACINE,
    )
    assert resultat.returncode == 0, "donnees/references/ devrait être ignoré par git"


def test_donnees_sources_est_ignore_par_git():
    resultat = subprocess.run(
        ["git", "check-ignore", "-q", "donnees/sources/un-fichier-test.mp4"],
        cwd=RACINE,
    )
    assert resultat.returncode == 0, "donnees/sources/ devrait être ignoré par git"


def test_un_fichier_synthetique_dans_donnees_references_nest_pas_suivi(tmp_path_factory):
    """Bout en bout, avec un fichier synthétique minuscule (pas une vraie
    vidéo) : déposé dans donnees/references/, `git status` ne doit
    jamais le proposer — c'est le comportement que le garde-fou vient
    renforcer, pas remplacer."""
    dossier = RACINE / "donnees" / "references"
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / "synthetique-test-garde-fou.mp4"
    fichier.write_bytes(b"pas une vraie video, juste un test")
    try:
        sortie = subprocess.run(
            ["git", "status", "--porcelain", str(fichier)],
            cwd=RACINE, capture_output=True, text=True,
        )
        assert sortie.stdout.strip() == "", (
            "un fichier dans donnees/references/ ne doit jamais apparaître "
            "dans git status (donc jamais être `git add`-able par erreur)"
        )
    finally:
        fichier.unlink(missing_ok=True)


# ── Le script complet, en conditions réelles ────────────────────────────

def test_le_script_ne_signale_rien_sur_letat_actuel_du_depot():
    """Aucune vidéo n'est suivie aujourd'hui (voir l'audit d'historique) :
    le script doit sortir avec le code 0 sur le dépôt réel."""
    resultat = subprocess.run(
        ["python3", "scripts/verifier_videos_prives.py", "--tous"],
        cwd=RACINE, capture_output=True, text=True,
    )
    assert resultat.returncode == 0, resultat.stderr


def test_le_hook_pre_commit_pointe_vers_le_meme_script():
    hook = (RACINE / ".githooks" / "pre-commit").read_text(encoding="utf-8")
    assert "verifier_videos_prives.py" in hook
