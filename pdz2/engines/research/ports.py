"""Ports du moteur de recherche.

Le moteur ne connaît pas les fournisseurs : il connaît un protocole. Chaque
adaptateur déclare ce qu'il sait faire *et s'il est réellement joignable*,
via `ProviderCapability`, dont le vocabulaire est partagé par toute la chaîne
(voir `pdz2.contracts.capability`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import Field

from pdz2.contracts.base import Element
from pdz2.contracts.capability import CapabilityState, ProviderCapability
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
