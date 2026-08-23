"""Mesures déterministes sur un fichier vidéo.

    OBSERVERS MEASURE.

Rien ici ne juge : tout se compte. Chaque fonction lit des pixels et rend un
nombre, avec sa méthode nommée pour que la mesure soit rejouable. Le verdict
appartient aux contrôles, la cause au diagnostic, la correction à la
réparation — trois modules plus loin.

Les images sont décodées par ffmpeg en niveaux de gris et en petite taille :
mesurer un mouvement ne demande pas la pleine résolution, et travailler à
160 pixels de large rend l'observation cent fois plus rapide sans changer les
conclusions.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from pdz2.renderers.ffmpeg import EncodingFailed, probe_video

__all__ = [
    "FrameSequence",
    "decode_frames",
    "mean_absolute_difference",
    "first_to_last_difference",
    "motion_profile",
    "black_frame_ratio",
    "frozen_frame_ratio",
    "luminance_profile",
    "sharpness",
    "colour_distance_to_palette",
    "ANALYSIS_WIDTH",
    "BLACK_LEVEL",
    "FROZEN_LEVEL",
]

ANALYSIS_WIDTH = 160
"""Largeur d'analyse, en pixels.

Le mouvement, la luminance et le gel se mesurent aussi bien sur une image
réduite, et cent fois plus vite. La netteté est la seule mesure qui perde à
être réduite : elle est donc normalisée par la taille d'analyse.
"""

BLACK_LEVEL = 0.02
"""Luminance moyenne normalisée en dessous de laquelle une image est noire."""

FROZEN_LEVEL = 0.0
"""Différence en dessous de laquelle deux images sont *strictement* identiques.

Un mouvement de caméra lent produit des différences image à image minuscules
— de l'ordre de 10⁻⁴ — sans être figé pour autant. Seule l'égalité stricte
signale un rendu réellement bloqué : une image recopiée telle quelle.
"""


@dataclass(frozen=True)
class FrameSequence:
    """Images décodées, en niveaux de gris normalisés dans [0, 1]."""

    frames: np.ndarray
    """Tableau (n, hauteur, largeur), valeurs flottantes dans [0, 1]."""

    fps: float
    duration_s: float
    source_width: int
    source_height: int

    @property
    def count(self) -> int:
        return int(self.frames.shape[0])


def decode_frames(
    path: Path,
    *,
    width: int = ANALYSIS_WIDTH,
    binary: str = "ffmpeg",
) -> FrameSequence:
    """Décode toutes les images d'une vidéo en niveaux de gris réduits."""
    probe = probe_video(path)
    height = max(2, int(round(probe.height * width / probe.width)))
    height -= height % 2
    argv = [
        binary,
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(path),
        "-vf", f"scale={width}:{height}",
        "-pix_fmt", "gray",
        "-f", "rawvideo",
        "-",
    ]
    run = subprocess.run(argv, capture_output=True, check=False)
    if run.returncode != 0:
        raise EncodingFailed(
            f"décodage impossible : {run.stderr.decode(errors='replace')[:300]}"
        )
    raw = np.frombuffer(run.stdout, dtype=np.uint8)
    frame_size = width * height
    if frame_size == 0 or raw.size < frame_size:
        raise EncodingFailed(f"{path.name} : aucune image décodable")
    usable = (raw.size // frame_size) * frame_size
    frames = raw[:usable].reshape(-1, height, width).astype(np.float32) / 255.0
    return FrameSequence(
        frames=frames,
        fps=probe.fps,
        duration_s=probe.duration_s,
        source_width=probe.width,
        source_height=probe.height,
    )


def mean_absolute_difference(sequence: FrameSequence) -> float:
    """Différence moyenne entre images consécutives, dans [0, 1].

    C'est la mesure de mouvement la plus simple qui soit — et la plus robuste :
    elle ne suppose rien sur le contenu, et vaut zéro exactement quand rien ne
    change. Un flux optique dense dirait *où* ça bouge ; ici on demande
    seulement *si* ça bouge, et de combien.
    """
    if sequence.count < 2:
        return 0.0
    return float(np.abs(np.diff(sequence.frames, axis=0)).mean())


def first_to_last_difference(sequence: FrameSequence) -> float:
    """Déplacement total du plan : première image contre dernière.

    C'est la mesure qui répond à « ce plan a-t-il bougé ? ». La différence
    image à image ne le dit pas : un travelling lent de quatre secondes change
    l'image de 2 % au total et de 0,01 % d'une image à la suivante. Mesurée
    image à image, une poussée parfaitement réussie passerait pour un plan
    figé — et la réparation s'acharnerait sur un rendu correct.
    """
    if sequence.count < 2:
        return 0.0
    return float(np.abs(sequence.frames[-1] - sequence.frames[0]).mean())


def motion_profile(sequence: FrameSequence) -> np.ndarray:
    """Différence image à image, sur toute la durée."""
    if sequence.count < 2:
        return np.zeros(0, dtype=np.float32)
    return np.abs(np.diff(sequence.frames, axis=0)).mean(axis=(1, 2))


def black_frame_ratio(sequence: FrameSequence, level: float = BLACK_LEVEL) -> float:
    """Part d'images entièrement noires."""
    if sequence.count == 0:
        return 1.0
    means = sequence.frames.mean(axis=(1, 2))
    return float((means < level).mean())


def frozen_frame_ratio(
    sequence: FrameSequence, level: float = FROZEN_LEVEL
) -> float:
    """Part de transitions où l'image est **strictement** identique.

    Mesuré sur des rendus corrects : 0,000 à 0,023. Un rendu bloqué recopie la
    même image et tend vers 1,0.
    """
    profile = motion_profile(sequence)
    if profile.size == 0:
        return 1.0
    return float((profile <= level).mean())


def luminance_profile(sequence: FrameSequence) -> np.ndarray:
    """Luminance moyenne image par image."""
    if sequence.count == 0:
        return np.zeros(0, dtype=np.float32)
    return sequence.frames.mean(axis=(1, 2))


def sharpness(sequence: FrameSequence) -> float:
    """Netteté : variance du laplacien, moyennée sur les images.

    Normalisée par la largeur d'analyse pour rester comparable d'une taille à
    l'autre. Une valeur basse signale du flou — ou une image vide.
    """
    if sequence.count == 0:
        return 0.0
    kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    values = []
    for frame in sequence.frames[:: max(1, sequence.count // 8)]:
        padded = np.pad(frame, 1, mode="edge")
        response = (
            kernel[0, 1] * padded[:-2, 1:-1]
            + kernel[1, 0] * padded[1:-1, :-2]
            + kernel[1, 1] * padded[1:-1, 1:-1]
            + kernel[1, 2] * padded[1:-1, 2:]
            + kernel[2, 1] * padded[2:, 1:-1]
        )
        values.append(float(response.var()))
    return float(np.mean(values) * (ANALYSIS_WIDTH / max(1, sequence.frames.shape[2])))


def colour_distance_to_palette(
    path: Path, palette: list[str], *, binary: str = "ffmpeg", samples: int = 4
) -> float:
    """Distance moyenne des pixels à la couleur la plus proche de la palette.

    Rendue dans [0, 1]. Une valeur haute signale que l'image s'est éloignée du
    registre chromatique décidé dans la bible visuelle.
    """
    if not palette:
        raise ValueError("palette vide")
    probe = probe_video(path)
    step = max(1, probe.frame_count // max(1, samples))
    argv = [
        binary,
        "-hide_banner", "-loglevel", "error",
        "-i", str(path),
        "-vf", f"select=not(mod(n\\,{step})),scale=64:-2",
        "-vsync", "0",
        "-pix_fmt", "rgb24",
        "-f", "rawvideo", "-",
    ]
    run = subprocess.run(argv, capture_output=True, check=False)
    if run.returncode != 0 or not run.stdout:
        raise EncodingFailed(f"{path.name} : échantillonnage couleur impossible")
    pixels = np.frombuffer(run.stdout, dtype=np.uint8).reshape(-1, 3).astype(np.float32)
    reference = np.array(
        [[int(c.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)] for c in palette],
        dtype=np.float32,
    )
    # Distance au plus proche voisin de la palette, normalisée par la diagonale
    # de l'espace RGB.
    distances = np.linalg.norm(pixels[:, None, :] - reference[None, :, :], axis=2)
    nearest = distances.min(axis=1)
    return float(nearest.mean() / (255.0 * np.sqrt(3)))
