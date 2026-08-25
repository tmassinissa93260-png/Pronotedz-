"""Exécution d'un plan : qui fait quoi, et ce qui se passe quand ça rate.

    STRATEGY DECIDES HOW. PROVIDER DECIDES WITH WHAT. RENDERER EXECUTES.
"""

from pdz2.execution.dispatcher import (
    Dispatch,
    ExecutionDispatcher,
    ExecutionOutcome,
    Executor,
)

__all__ = ["ExecutionDispatcher", "ExecutionOutcome", "Dispatch", "Executor"]
