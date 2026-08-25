"""Compilation du Shot Graph — phase 3.

`DirectorState` + `TemporalPlan` + `VisualBible` → `ShotGraph` + programmes
caméra. Aucune décision narrative n'y naît : les règles de mise en image sont
dans `grammar.py`, et rien d'autre n'est décidé.
"""

from pdz2.engines.shots.compiler import (
    ShotGraphCompiler,
    ShotGraphOutcome,
    ShotGraphRejected,
)
from pdz2.engines.shots.grammar import FUNCTION_FRAMING, LOCK_BELOW

__all__ = [
    "ShotGraphCompiler",
    "ShotGraphOutcome",
    "ShotGraphRejected",
    "FUNCTION_FRAMING",
    "LOCK_BELOW",
]
