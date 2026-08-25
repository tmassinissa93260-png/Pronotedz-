"""Déclaration de capacité d'un adaptateur — vocabulaire commun.

Toute la discipline du §14 tient ici, et vaut pour n'importe quel adaptateur,
qu'il cherche des documents, parle, ou fabrique une image :

    AVAILABLE   — vérifié à l'instant, avec la méthode et la date
    UNAVAILABLE — vérifié, et injoignable ; la raison est enregistrée
    UNKNOWN     — jamais vérifié récemment

Une capacité annoncée n'est jamais une capacité réelle. Un moteur qui trouve
un adaptateur `UNKNOWN` doit le sonder avant de compter dessus.

Ce vocabulaire vit avec les contrats, et non dans un moteur : il est partagé
par tous, et l'y laisser obligerait la chaîne audio à importer le moteur de
recherche pour savoir dire « injoignable ».
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import Field, model_validator

from pdz2.contracts.base import Element

__all__ = ["CapabilityState", "ProviderCapability"]


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
