"""Renderers — exécution des stratégies de rendu.

Phase 7 : les quatre stratégies déterministes, qui n'ont besoin de personne.
Aucun renderer génératif : voir `pdz2.providers` pour le port et l'absence
déclarée d'adaptateur.

Dépendance système : `ffmpeg` (paquet Debian/Ubuntu `ffmpeg`). Absent, les
renderers se déclarent injoignables avec la raison.
"""

from pdz2.renderers.deterministic import (
    RENDERER_VERSION,
    SUPPORTED_STRATEGIES,
    DeterministicRenderer,
    RenderFailed,
    RenderOutcome,
    ShotRender,
)
from pdz2.renderers.ffmpeg import (
    EncodingFailed,
    FfmpegUnavailable,
    VideoProbe,
    encode_frames,
    ffmpeg_capability,
    probe_video,
)
from pdz2.renderers.motion_paths import SUPPORTED_PRIMITIVES, ease, sample_trajectory

__all__ = [
    "DeterministicRenderer",
    "ShotRender",
    "RenderOutcome",
    "RenderFailed",
    "SUPPORTED_STRATEGIES",
    "RENDERER_VERSION",
    "ffmpeg_capability",
    "encode_frames",
    "probe_video",
    "VideoProbe",
    "FfmpegUnavailable",
    "EncodingFailed",
    "sample_trajectory",
    "ease",
    "SUPPORTED_PRIMITIVES",
]
