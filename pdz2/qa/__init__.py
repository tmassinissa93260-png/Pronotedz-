"""Observation déterministe — phase 8.

    OBSERVERS MEASURE.

Rien ici ne juge : tout se compte, et chaque mesure porte sa méthode. Ce que
l'observateur ne prétend pas mesurer — la beauté, la reconnaissance d'un
objet, la fidélité au sujet — revient à la revue humaine, parce que sans
modèle, prétendre le rendre serait une mesure inventée.
"""

from pdz2.qa.measures import (
    ANALYSIS_WIDTH,
    FrameSequence,
    black_frame_ratio,
    colour_distance_to_palette,
    decode_frames,
    first_to_last_difference,
    frozen_frame_ratio,
    luminance_profile,
    mean_absolute_difference,
    motion_profile,
    sharpness,
)
from pdz2.qa.observer import (
    MOTION_TOLERANCE,
    OBSERVER_VERSION,
    DeterministicObserver,
    ObservationFailed,
    ObservationOutcome,
)

__all__ = [
    "DeterministicObserver",
    "ObservationOutcome",
    "ObservationFailed",
    "OBSERVER_VERSION",
    "MOTION_TOLERANCE",
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
]
