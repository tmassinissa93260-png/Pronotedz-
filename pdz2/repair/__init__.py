"""Diagnostic et réparation — phase 9.

    DIAGNOSTICS EXPLAIN.  REPAIR COMPILERS ADAPT.  FALLBACKS GUARANTEE DELIVERY.

Le diagnostic ne re-mesure rien : il traduit des contrôles en échec en causes
nommées, mesures à l'appui. Le compilateur de réparation transforme ces causes
en actions bornées, dont la dernière aboutit toujours.
"""

from pdz2.repair.compiler import (
    RESPONSES,
    RepairCompiler,
    RepairOutcome,
    RepairRejected,
)
from pdz2.repair.diagnosis import (
    CHECK_TO_FAILURE,
    DiagnosisOutcome,
    FailureDiagnoser,
)

__all__ = [
    "FailureDiagnoser",
    "DiagnosisOutcome",
    "CHECK_TO_FAILURE",
    "RepairCompiler",
    "RepairOutcome",
    "RepairRejected",
    "RESPONSES",
]
