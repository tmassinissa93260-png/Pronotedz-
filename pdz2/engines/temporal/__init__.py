"""Temporal Director — phase 3.

`DirectorState` + `VoiceTimeline` → `TemporalPlan` : créneaux pavant l'audio
mesuré, et cinq courbes dont chaque règle est écrite dans `curves.py`.
"""

from pdz2.engines.temporal.curves import CurveRules, SlotContext
from pdz2.engines.temporal.director import (
    TemporalDirector,
    TemporalOutcome,
    TemporalRejected,
)
from pdz2.engines.temporal.slots import SlotRules, carve_slots

__all__ = [
    "TemporalDirector",
    "TemporalOutcome",
    "TemporalRejected",
    "CurveRules",
    "SlotContext",
    "SlotRules",
    "carve_slots",
]
