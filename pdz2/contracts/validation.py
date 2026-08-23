"""Rapport de validation statique.

Le validateur intervient **avant toute dépense**. Il ne répare rien, il ne
choisit rien : il constate, il classe, et il rejette. Un rapport bloquant
interdit à la machine à états de franchir la barrière de coût.

Chaque constat porte la règle qui l'a produit. Un rejet sans règle nommée
serait un caprice ; un rejet nommé se conteste, se corrige, et se teste.
"""

from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import Field, model_validator

from pdz2.contracts.base import Contract, Element, contract
from pdz2.contracts.enums import Severity

__all__ = ["ValidationRule", "ValidationIssue", "ValidationReport"]


class ValidationRule(str, Enum):
    """Les règles du §13, une par une."""

    SCHEMA = "schema"
    CONTRACT_VERSION = "contract_version"
    REQUIRED_FIELD = "required_field"
    LOGICAL_CONTRADICTION = "logical_contradiction"
    CAMERA_CONSTRAINT = "camera_constraint"
    DURATION_FEASIBILITY = "duration_feasibility"
    PROVIDER_CAPABILITY = "provider_capability"
    BUDGET = "budget"
    FALLBACK_AVAILABILITY = "fallback_availability"
    CONTINUITY = "continuity"
    EVIDENCE_LINK = "evidence_link"
    RESOLUTION_FORMAT = "resolution_format"


class ValidationIssue(Element):
    rule: ValidationRule
    severity: Severity
    subject_id: str = Field(min_length=1)
    """Ce sur quoi porte le constat : un shot_id, un identifiant de contrat."""

    detail: str = Field(min_length=1)
    remedy: str = ""
    """Ce qu'il faut faire pour lever le constat, quand c'est connu."""

    @model_validator(mode="after")
    def _blocking_issues_say_how_to_fix(self) -> Self:
        if self.severity is Severity.BLOCKING and not self.remedy.strip():
            raise ValueError(
                f"{self.rule.value} sur {self.subject_id} : un blocage doit dire "
                "comment le lever"
            )
        return self


@contract("validation_report", "1.0.0")
class ValidationReport(Contract):
    """Verdict du validateur statique sur un lot de demandes de rendu."""

    episode_id: str = Field(min_length=1)
    shot_graph_id: str = Field(min_length=1)
    requested_spec_ids: list[str] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)
    validator_version: str = Field(min_length=1)
    accepted: bool

    @model_validator(mode="after")
    def _verdict_follows_the_issues(self) -> Self:
        blocking = [
            issue for issue in self.issues if issue.severity is Severity.BLOCKING
        ]
        if self.accepted and blocking:
            raise ValueError(
                "rapport accepté malgré "
                f"{len(blocking)} blocage(s) : {[i.rule.value for i in blocking]}"
            )
        if not self.accepted and not blocking:
            raise ValueError("rapport rejeté sans aucun blocage à montrer")
        return self

    @property
    def blocking(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity is Severity.BLOCKING]

    def issues_for(self, subject_id: str) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.subject_id == subject_id]
