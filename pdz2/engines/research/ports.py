"""Ports du moteur de recherche.

Le moteur ne connaît pas les fournisseurs : il connaît un protocole. Chaque
adaptateur déclare ce qu'il sait faire *et s'il est réellement joignable*,
selon la même discipline que la matrice de capacités (§14) :

    AVAILABLE   — vérifié à l'instant, avec la méthode et la date
    UNAVAILABLE — vérifié, et injoignable ; la raison est enregistrée
    UNKNOWN     — jamais vérifié récemment

Une capacité annoncée n'est jamais une capacité réelle. Un moteur qui trouve
une source `UNKNOWN` doit la sonder avant de compter dessus.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Protocol, runtime_checkable

from pydantic import Field, model_validator

from pdz2.contracts.base import Element
from pdz2.contracts.research import SourceKind

__all__ = [
    "CapabilityState",
    "ProviderCapability",
    "SourceDocument",
    "SearchQuery",
    "SearchProvider",
    "SearchUnavailable",
]


class SearchUnavailable(RuntimeError):
    """Un fournisseur de recherche déclaré joignable ne répond pas.

    Levée plutôt que retournée vide : une recherche silencieusement vide
    produirait un épisode sans sources, donc sans faits.
    """


class CapabilityState(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class ProviderCapability(Element):
    """Ce qu'un adaptateur sait faire, et depuis quand on le sait."""

    provider: str = Field(min_length=1)
    state: CapabilityState
    measured_at: datetime | None = None
    measurement_method: str = Field(default="", max_length=400)
    detail: str = ""
    """Raison d'une indisponibilité, en clair. Obligatoire si UNAVAILABLE."""

    requires_network: bool = True
    requires_credentials: bool = False
    max_results: int = Field(default=10, gt=0)

    @model_validator(mode="after")
    def _a_measurement_is_dated_and_explained(self):
        if self.state is CapabilityState.UNKNOWN:
            if self.measured_at is not None:
                raise ValueError("capacité UNKNOWN mais horodatée : choisir un état mesuré")
            return self
        if self.measured_at is None:
            raise ValueError(
                f"{self.provider} : état {self.state.value} sans date de mesure — "
                "une capacité non mesurée est UNKNOWN"
            )
        if self.measured_at.tzinfo is None:
            raise ValueError("date de mesure sans fuseau")
        if not self.measurement_method.strip():
            raise ValueError(
                f"{self.provider} : état mesuré sans méthode — une mesure se rejoue"
            )
        if self.state is CapabilityState.UNAVAILABLE and not self.detail.strip():
            raise ValueError(f"{self.provider} : indisponible sans raison enregistrée")
        return self

    @classmethod
    def unknown(cls, provider: str, **kwargs) -> ProviderCapability:
        return cls(provider=provider, state=CapabilityState.UNKNOWN, **kwargs)

    @classmethod
    def measured(
        cls,
        provider: str,
        *,
        reachable: bool,
        method: str,
        detail: str = "",
        **kwargs,
    ) -> ProviderCapability:
        return cls(
            provider=provider,
            state=CapabilityState.AVAILABLE if reachable else CapabilityState.UNAVAILABLE,
            measured_at=datetime.now(UTC),
            measurement_method=method,
            detail=detail,
            **kwargs,
        )

    @property
    def usable(self) -> bool:
        return self.state is CapabilityState.AVAILABLE


class SearchQuery(Element):
    text: str = Field(min_length=1)
    language: str = Field(default="fr", min_length=2, max_length=8)
    max_results: int = Field(default=8, gt=0, le=50)


class SourceDocument(Element):
    """Un document rapporté par un fournisseur, avant toute interprétation."""

    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    kind: SourceKind = SourceKind.UNKNOWN
    url: str | None = None
    publisher: str | None = None
    authority: float = Field(default=0.5, ge=0.0, le=1.0)
    """Autorité déclarée par l'adaptateur. Le moteur ne la recalcule pas."""

    retrieved_at: datetime | None = None
    locator_prefix: str = ""
    """Préfixe de localisation des citations : « §2 », « p. 14 »…"""


@runtime_checkable
class SearchProvider(Protocol):
    """Interface commune des fournisseurs de documents."""

    name: str

    def get_capabilities(self) -> ProviderCapability:
        """Sonde réellement le fournisseur. Ne jamais deviner l'état."""

    def search(self, query: SearchQuery) -> list[SourceDocument]:
        """Retourne des documents. Lève `SearchUnavailable` si injoignable."""
