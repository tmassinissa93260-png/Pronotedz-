"""Validation statique — refuser avant de dépenser."""

from pdz2.engines.validation.validator import (
    MAX_SHOT_DURATION_S,
    MIN_SHOT_DURATION_S,
    VALIDATOR_VERSION,
    StaticValidator,
    ValidationOutcome,
)

__all__ = [
    "StaticValidator",
    "ValidationOutcome",
    "VALIDATOR_VERSION",
    "MAX_SHOT_DURATION_S",
    "MIN_SHOT_DURATION_S",
]
