"""Matrice de capacités et gouvernance du coût.

    ANNOUNCED ≠ MEASURED ≠ UNKNOWN

Le §14 est catégorique : une valeur annoncée par un fournisseur n'est jamais
une capacité réelle, et une capacité non mesurée récemment redevient inconnue.
Le contrat le tient — une entrée `MEASURED` sans date et sans méthode est
refusée, et une mesure trop vieille se déclare périmée d'elle-même.

Le gouverneur de coût, lui, ne compte pas seulement : il **autorise**. Une
dépense qui ferait franchir le plafond est refusée avant d'avoir lieu, pas
constatée après.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Self

from pydantic import Field, model_validator

from pdz2.contracts.base import Contract, Element, contract
from pdz2.contracts.render import RenderStrategy

__all__ = [
    "Provenance",
    "CapacityValue",
    "CapabilityEntry",
    "CapabilityMatrix",
    "SpendRecord",
    "CostLedger",
    "DEFAULT_FRESHNESS_DAYS",
]

DEFAULT_FRESHNESS_DAYS = 30
"""Au-delà, une mesure cesse de valoir mesure.

Les fournisseurs changent leurs modèles sans prévenir. Une capacité vérifiée
il y a deux mois est une capacité inconnue qui s'ignore.
"""


class Provenance(str, Enum):
    ANNOUNCED = "announced"
    """Ce que le fournisseur dit savoir faire. N'engage que lui."""

    MEASURED = "measured"
    """Ce qu'on a vérifié soi-même, à une date, par une méthode."""

    UNKNOWN = "unknown"
    """Jamais vérifié, ou vérifié il y a trop longtemps."""


class CapacityValue(Element):
    """Une capacité chiffrée, avec d'où elle vient."""

    name: str = Field(min_length=1)
    value: float | None = None
    unit: str = ""
    provenance: Provenance
    measured_at: datetime | None = None
    method: str = ""

    @model_validator(mode="after")
    def _a_measure_is_dated_and_explained(self) -> Self:
        if self.provenance is Provenance.MEASURED:
            if self.measured_at is None:
                raise ValueError(
                    f"{self.name} : déclarée MEASURED sans date — une capacité "
                    "non datée est UNKNOWN"
                )
            if not self.method.strip():
                raise ValueError(
                    f"{self.name} : déclarée MEASURED sans méthode — une mesure "
                    "se rejoue ou n'existe pas"
                )
            if self.value is None:
                raise ValueError(f"{self.name} : MEASURED sans valeur")
        if self.provenance is Provenance.UNKNOWN and self.value is not None:
            raise ValueError(
                f"{self.name} : UNKNOWN avec une valeur — on ne chiffre pas ce "
                "qu'on ne sait pas"
            )
        return self

    def is_stale(self, *, days: int = DEFAULT_FRESHNESS_DAYS, now=None) -> bool:
        """Vrai si la mesure a passé sa date de validité."""
        if self.provenance is not Provenance.MEASURED or self.measured_at is None:
            return self.provenance is not Provenance.ANNOUNCED
        moment = now or datetime.now(UTC)
        return moment - self.measured_at > timedelta(days=days)

    def trustworthy(self, *, days: int = DEFAULT_FRESHNESS_DAYS, now=None) -> bool:
        """Une capacité digne de confiance est mesurée **et** récente."""
        return self.provenance is Provenance.MEASURED and not self.is_stale(
            days=days, now=now
        )


@contract("capability_entry", "1.0.0")
class CapabilityEntry(Contract):
    """Ce qu'un couple fournisseur/modèle sait faire, ligne par ligne."""

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    strategies: list[RenderStrategy] = Field(default_factory=list)
    values: list[CapacityValue] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="after")
    def _no_duplicate_values(self) -> Self:
        names = [value.name for value in self.values]
        if len(set(names)) != len(names):
            raise ValueError(f"{self.provider}/{self.model} : capacité en double")
        return self

    def value(self, name: str) -> CapacityValue | None:
        for item in self.values:
            if item.name == name:
                return item
        return None

    def trustworthy_values(self, *, days: int = DEFAULT_FRESHNESS_DAYS, now=None):
        return [v for v in self.values if v.trustworthy(days=days, now=now)]


@contract("capability_matrix", "1.0.0")
class CapabilityMatrix(Contract):
    """L'ensemble de ce qu'on croit savoir, et de ce qu'on sait vraiment."""

    entries: list[CapabilityEntry] = Field(default_factory=list)
    freshness_days: int = Field(default=DEFAULT_FRESHNESS_DAYS, gt=0)

    @model_validator(mode="after")
    def _one_entry_per_pair(self) -> Self:
        pairs = [(entry.provider, entry.model) for entry in self.entries]
        if len(set(pairs)) != len(pairs):
            raise ValueError("matrice : deux entrées pour le même couple")
        return self

    def entry(self, provider: str, model: str) -> CapabilityEntry | None:
        for item in self.entries:
            if item.provider == provider and item.model == model:
                return item
        return None

    def stale_values(self, now=None) -> list[tuple[str, str, str]]:
        """Capacités périmées : à re-mesurer avant d'y compter."""
        stale: list[tuple[str, str, str]] = []
        for entry in self.entries:
            for value in entry.values:
                if value.provenance is Provenance.MEASURED and value.is_stale(
                    days=self.freshness_days, now=now
                ):
                    stale.append((entry.provider, entry.model, value.name))
        return stale


class SpendRecord(Element):
    """Une dépense réelle, imputée à une étape et à un plan."""

    stage: str = Field(min_length=1)
    shot_id: str | None = None
    provider: str | None = None
    amount_usd: float = Field(ge=0.0)
    at: datetime
    detail: str = ""

    @model_validator(mode="after")
    def _dated(self) -> Self:
        if self.at.tzinfo is None:
            raise ValueError("dépense sans fuseau horaire")
        return self


@contract("cost_ledger", "1.0.0")
class CostLedger(Contract):
    """Registre des dépenses d'un épisode, et son plafond."""

    episode_id: str = Field(min_length=1)
    budget_cap_usd: float | None = Field(default=None, ge=0.0)
    records: list[SpendRecord] = Field(default_factory=list)

    @property
    def spent_usd(self) -> float:
        return round(sum(record.amount_usd for record in self.records), 6)

    @property
    def remaining_usd(self) -> float | None:
        if self.budget_cap_usd is None:
            return None
        return round(self.budget_cap_usd - self.spent_usd, 6)

    def by_stage(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for record in self.records:
            totals[record.stage] = round(
                totals.get(record.stage, 0.0) + record.amount_usd, 6
            )
        return totals

    @model_validator(mode="after")
    def _never_over_the_cap(self) -> Self:
        if self.budget_cap_usd is None:
            return self
        total = sum(record.amount_usd for record in self.records)
        if total > self.budget_cap_usd + 1e-9:
            raise ValueError(
                f"registre à {total:.4f} USD au-dessus du plafond "
                f"{self.budget_cap_usd:.4f} USD — la dépense aurait dû être "
                "refusée avant d'avoir lieu"
            )
        return self
