"""Montage, sous-titres et assemblage — phase 10.

Le montage n'invente rien : il pose les plans rendus aux instants du découpage,
qui dérive lui-même de la voix mesurée. Il refuse dès que deux durées
divergent — un montage bâti sur deux vérités temporelles produit un décalage
qu'on ne rattrape plus.
"""

from pdz2.editing.assembler import (
    DURATION_TOLERANCE_S,
    AssemblyFailed,
    AssemblyOutcome,
    VideoAssembler,
)
from pdz2.editing.subtitles import (
    MIN_CUE_S,
    SubtitleCompiler,
    SubtitleOutcome,
    SubtitleRejected,
    to_srt,
)
from pdz2.editing.timeline import (
    SYNC_TOLERANCE_S,
    EditCompiler,
    EditOutcome,
    EditRejected,
)

__all__ = [
    "EditCompiler",
    "EditOutcome",
    "EditRejected",
    "SYNC_TOLERANCE_S",
    "SubtitleCompiler",
    "SubtitleOutcome",
    "SubtitleRejected",
    "to_srt",
    "MIN_CUE_S",
    "VideoAssembler",
    "AssemblyOutcome",
    "AssemblyFailed",
    "DURATION_TOLERANCE_S",
]
