"""Vérifie, après génération, qu'un clip animé contient un VRAI mouvement.

Jusqu'ici, la seule barrière de qualité après un appel au modèle vidéo était
la durée (`animation.py`, `sonder(destination).duree_s`). Mesuré en
production (enquête run #66) : un clip peut être un fichier vidéo valide, de
la bonne durée, et pourtant visuellement statique — le modèle d'image→vidéo
a rendu quelque chose, mais rien qui bouge. « API 200 » et « fichier livré »
ne prouvent jamais qu'une image a réellement changé d'une frame à l'autre.

Méthode (celle déjà validée dans l'enquête, pas une réinvention) :
échantillonner le clip à basse fréquence, comparer les échantillons
consécutifs en niveaux de gris (élimine le bruit chromatique/compression),
mesurer la différence moyenne de pixels. Zéro appel IA — `ffprobe`/`ffmpeg`
(déjà des dépendances du projet) et `PIL`/`numpy` (déjà des dépendances
Python du projet) suffisent.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from pdz.analyse.sonde import sonder
from pdz.moteur.erreurs import ErreurConfig, ErreurPdz

log = logging.getLogger(__name__)

# Mesuré sur le run #66 : le seul plan animé par un vrai modèle vidéo mais
# resté statique plafonnait à 2,135/255 de différence moyenne inter-frame
# (moyenne 0,509) ; tous les plans avec un mouvement réel (repli « vie »,
# donc un zoom/pan mécanique mais réel) avaient un MINIMUM à 1,723/255. Le
# seuil tombe dans cet écart net, sans zone grise entre les deux groupes.
SEUIL_MOUVEMENT = 1.0
ECHANTILLONNAGE_FPS = 5


@dataclass
class VerdictMouvement:
    fichier_valide: bool
    duree_s: float = 0.0
    fps: float = 0.0
    frames_echantillonnees: int = 0
    diff_moyenne: float = 0.0
    mouvement_detecte: bool = False
    raison: str = ""    # "ok" | "static_clip" | "fichier_invalide"


def _diff_moyenne(dossier_frames: Path) -> tuple[float, int]:
    """Différence moyenne de pixels (niveaux de gris) entre échantillons
    consécutifs — la même mesure que l'enquête, appliquée ici en fonction
    réutilisable."""
    fichiers = sorted(dossier_frames.glob("*.png"))
    if len(fichiers) < 2:
        return 0.0, len(fichiers)

    diffs = []
    precedente = None
    for f in fichiers:
        courante = np.asarray(Image.open(f).convert("L"), dtype=np.float32)
        if precedente is not None:
            diffs.append(float(np.mean(np.abs(courante - precedente))))
        precedente = courante

    return (sum(diffs) / len(diffs) if diffs else 0.0), len(fichiers)


def _echantillonner(source: Path, dossier_frames: Path, *,
                    debut_s: float = 0.0, duree_s: float | None = None) -> None:
    dossier_frames.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    if debut_s > 0:
        cmd += ["-ss", f"{debut_s:.3f}"]
    cmd += ["-i", str(source)]
    if duree_s is not None:
        cmd += ["-t", f"{duree_s:.3f}"]
    cmd += ["-vf", f"fps={ECHANTILLONNAGE_FPS}", str(dossier_frames / "f_%04d.png")]
    subprocess.run(cmd, check=True, timeout=60, capture_output=True)


def verifier(chemin: Path) -> VerdictMouvement:
    """Le verdict de mouvement pour un clip entier."""
    try:
        meta = sonder(chemin)
    except (ErreurPdz, ErreurConfig) as e:
        log.warning("Clip animé invalide (%s) : %s", chemin.name, e)
        return VerdictMouvement(fichier_valide=False, raison="fichier_invalide")

    with tempfile.TemporaryDirectory() as tmp:
        dossier = Path(tmp)
        try:
            _echantillonner(chemin, dossier)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            log.warning("Échantillonnage impossible (%s) : %s", chemin.name, e)
            return VerdictMouvement(fichier_valide=False, raison="fichier_invalide")
        diff_moyenne, n_frames = _diff_moyenne(dossier)

    detecte = diff_moyenne >= SEUIL_MOUVEMENT
    return VerdictMouvement(
        fichier_valide=True, duree_s=meta.duree_s, fps=meta.fps,
        frames_echantillonnees=n_frames, diff_moyenne=round(diff_moyenne, 3),
        mouvement_detecte=detecte, raison="ok" if detecte else "static_clip",
    )


def verifier_segment(video: Path, *, debut_s: float, duree_s: float) -> VerdictMouvement:
    """Le verdict de mouvement pour une FENÊTRE d'une vidéo déjà montée —
    utilisé pour la QA finale (voir `pdz.production.qa_video_finale`), où
    les bornes de chaque plan sont déjà connues exactement, contrairement à
    un clip isolé."""
    try:
        sonder(video)
    except (ErreurPdz, ErreurConfig):
        return VerdictMouvement(fichier_valide=False, raison="fichier_invalide")

    with tempfile.TemporaryDirectory() as tmp:
        dossier = Path(tmp)
        try:
            _echantillonner(video, dossier, debut_s=debut_s, duree_s=duree_s)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return VerdictMouvement(fichier_valide=False, raison="fichier_invalide")
        diff_moyenne, n_frames = _diff_moyenne(dossier)

    detecte = diff_moyenne >= SEUIL_MOUVEMENT
    return VerdictMouvement(
        fichier_valide=True, duree_s=duree_s, frames_echantillonnees=n_frames,
        diff_moyenne=round(diff_moyenne, 3), mouvement_detecte=detecte,
        raison="ok" if detecte else "static_clip",
    )
