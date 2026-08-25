"""Moteur de recherche factuelle — phase 1.

Chemins réellement disponibles :
  * `LocalCorpusProvider` — corpus de fichiers sourcés, sans réseau ni clé.
  * `HttpSearchProvider`  — client HTTP générique, sondé avant usage.

Le moteur refuse de rendre un état vide : sans fournisseur joignable, il lève
`NoUsableProvider` avec la raison de chaque indisponibilité.
"""

from pdz2.engines.research.confidence import ConfidenceModel, EvidenceSignal
from pdz2.engines.research.corpus import CorpusFormatError, LocalCorpusProvider
from pdz2.engines.research.engine import NoUsableProvider, ResearchEngine, ResearchOutcome
from pdz2.engines.research.extraction import ExtractionSettings
from pdz2.engines.research.graph import EdgeRules
from pdz2.engines.research.ports import (
    CapabilityState,
    ProviderCapability,
    SearchProvider,
    SearchQuery,
    SearchUnavailable,
    SourceDocument,
)
from pdz2.engines.research.visual_evidence import demonstrability

__all__ = [
    "ResearchEngine",
    "ResearchOutcome",
    "NoUsableProvider",
    "LocalCorpusProvider",
    "CorpusFormatError",
    "ConfidenceModel",
    "EvidenceSignal",
    "ExtractionSettings",
    "EdgeRules",
    "SearchProvider",
    "SearchQuery",
    "SourceDocument",
    "SearchUnavailable",
    "ProviderCapability",
    "CapabilityState",
    "demonstrability",
]
