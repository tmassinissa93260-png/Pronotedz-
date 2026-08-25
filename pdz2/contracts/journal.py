"""Journal de production.

Un épisode qu'on ne peut pas expliquer après coup n'est pas reproductible : il
est simplement arrivé. Le journal réunit ce qu'il faut pour répondre, six mois
plus tard, à « pourquoi cette vidéo est-elle comme ça ? ».

Il ne recopie pas les contrats — ils sont déjà sur le disque. Il enregistre ce
qui n'est écrit nulle part ailleurs : l'enchaînement des étapes, les décisions
prises, les dégradations subies, les constats non corrigés, ce qui a coûté, et
ce que l'environnement offrait ce jour-là.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Self

from pydantic import Field, model_validator

from pdz2.contracts.base import Contract, Element, contract
from pdz2.contracts.capability import ProviderCapability
from pdz2.contracts.pipeline import EpisodeStatus, StateTransition

__all__ = ["JournalEntryKind", "JournalEntry", "ProductionJournal"]


class JournalEntryKind(str, Enum):
    DECISION = "decision"
    """Un choix pris, humain ou compilé, avec sa raison."""

    DEGRADATION = "degradation"
    """Un écart entre ce qui était demandé et ce qui a été fait."""

    FINDING = "finding"
    """Un constat que personne n'a corrigé."""

    REFUSAL = "refusal"
    """Un refus : validation, budget, contrat."""

    CAPABILITY = "capability"
    """Ce que l'environnement offrait, mesuré ce jour-là."""

    SPEND = "spend"
    """Une dépense engagée."""

    LIMITATION = "limitation"
    """Une limite déclarée plutôt que masquée."""


class JournalEntry(Element):
    kind: JournalEntryKind
    at: datetime
    stage: str = ""
    subject_id: str = ""
    summary: str = Field(min_length=1)
    detail: str = ""

    @model_validator(mode="after")
    def _dated(self) -> Self:
        if self.at.tzinfo is None:
            raise ValueError("entrée de journal sans fuseau horaire")
        return self


@contract("production_journal", "1.0.0")
class ProductionJournal(Contract):
    """Ce qu'il faut pour expliquer un épisode après coup."""

    episode_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    episode_status: EpisodeStatus
    started_at: datetime
    ended_at: datetime | None = None
    entries: list[JournalEntry] = Field(default_factory=list)
    transitions: list[StateTransition] = Field(default_factory=list)
    capabilities: list[ProviderCapability] = Field(default_factory=list)
    total_spent_usd: float = Field(default=0.0, ge=0.0)
    contract_versions: list[str] = Field(default_factory=list)
    """Versions de contrats en vigueur, pour relire l'épisode plus tard."""

    tool_versions: list[str] = Field(default_factory=list)
    """Versions des outils système utilisés : eSpeak NG, ffmpeg…"""

    @model_validator(mode="after")
    def _chronological(self) -> Self:
        times = [entry.at for entry in self.entries]
        if times != sorted(times):
            raise ValueError("journal : entrées dans le désordre")
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("journal : fin avant début")
        return self

    def of_kind(self, kind: JournalEntryKind) -> list[JournalEntry]:
        return [entry for entry in self.entries if entry.kind is kind]

    @property
    def unresolved(self) -> list[JournalEntry]:
        """Ce que personne n'a corrigé, et qu'il faut lire avant de publier."""
        return [
            entry
            for entry in self.entries
            if entry.kind
            in {
                JournalEntryKind.FINDING,
                JournalEntryKind.DEGRADATION,
                JournalEntryKind.LIMITATION,
            }
        ]
