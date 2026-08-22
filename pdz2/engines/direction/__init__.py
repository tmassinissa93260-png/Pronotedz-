"""Director Core — phase 1.

Une décision conceptuelle (`DirectorBrief`), puis un compilateur déterministe
(`DirectorCompiler`) qui en déduit tout le reste.

Le brief vient aujourd'hui d'un humain (`load_brief`). Le port `Reasoner` est
défini pour qu'un modèle de langue le produise, mais aucun adaptateur n'est
implémenté dans ce dépôt : voir `pdz2/engines/direction/ports.py`.
"""

from pdz2.engines.direction.brief import AnchorDraft, DirectorBrief, VisualProofDraft
from pdz2.engines.direction.compiler import (
    BriefRejected,
    DirectionOutcome,
    DirectorCompiler,
)
from pdz2.engines.direction.ports import (
    Reasoner,
    ReasonerUnavailable,
    load_brief,
    save_brief,
)
from pdz2.engines.direction.rhythm import (
    allocate_durations,
    emotional_curve,
    information_density,
)

__all__ = [
    "DirectorBrief",
    "AnchorDraft",
    "VisualProofDraft",
    "DirectorCompiler",
    "DirectionOutcome",
    "BriefRejected",
    "Reasoner",
    "ReasonerUnavailable",
    "load_brief",
    "save_brief",
    "allocate_durations",
    "emotional_curve",
    "information_density",
]
