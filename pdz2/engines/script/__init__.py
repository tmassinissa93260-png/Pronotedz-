"""Script Compiler — phase 2.

`DirectorState` → `ScriptState`, sans appel de modèle et sans nouvelle
décision narrative. La durée produite ici est une **estimation** ; la durée
officielle vient de `pdz2.audio`.
"""

from pdz2.engines.script.compiler import ScriptCompiler, ScriptOutcome, ScriptRejected
from pdz2.engines.script.estimation import (
    DEFAULT_SPEECH_RATE_WPM,
    estimate_duration_s,
    syllable_count,
)

__all__ = [
    "ScriptCompiler",
    "ScriptOutcome",
    "ScriptRejected",
    "estimate_duration_s",
    "syllable_count",
    "DEFAULT_SPEECH_RATE_WPM",
]
