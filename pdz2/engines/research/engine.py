"""Research Engine : d'une question à un `ResearchState` refermé sur lui-même.

Enchaînement, conforme au §4 du cahier des charges :

    1. sonder les fournisseurs et rapporter des documents
    2. repérer les phrases qui portent une affirmation
    3. rattacher chaque affirmation à ses preuves, et chaque preuve à sa source
    4. calculer une confiance par une fonction écrite et rejouable
    5. construire le Fact Graph
    6. mesurer la démontrabilité visuelle de chaque affirmation

Ce que le moteur ne fait pas, et ne doit pas faire : reformuler, conclure à
la place des sources, ou rédiger une preuve visuelle. Une affirmation sort
d'ici **citée**, jamais réécrite.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pdz2.contracts.research import (
    Claim,
    Evidence,
    EvidenceStance,
    FactGraph,
    ResearchState,
    SourceReference,
    TopicRequest,
    VerificationStatus,
)
from pdz2.engines.research.confidence import ConfidenceModel, EvidenceSignal
from pdz2.engines.research.extraction import (
    ExtractionSettings,
    SentenceCandidate,
    extract_candidates,
    group_duplicates,
)
from pdz2.engines.research.graph import EdgeRules, GraphNode, build_edges
from pdz2.engines.research.ports import (
    ProviderCapability,
    SearchProvider,
    SearchQuery,
    SearchUnavailable,
    SourceDocument,
)
from pdz2.engines.research.text import normalise, tokens
from pdz2.engines.research.visual_evidence import demonstrability

__all__ = ["ResearchEngine", "ResearchOutcome", "NoUsableProvider"]


class NoUsableProvider(SearchUnavailable):
    """Aucun fournisseur joignable. On le dit, on ne rend pas un état vide."""


@dataclass
class ResearchOutcome:
    """Sortie du moteur : l'état, plus ce qu'il faut pour le juger."""

    state: ResearchState
    capabilities: list[ProviderCapability] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def usable_providers(self) -> list[str]:
        return [c.provider for c in self.capabilities if c.usable]


@dataclass
class ResearchEngine:
    providers: list[SearchProvider]
    extraction: ExtractionSettings = field(default_factory=ExtractionSettings)
    confidence: ConfidenceModel = field(default_factory=ConfidenceModel)
    edge_rules: EdgeRules = field(default_factory=EdgeRules)
    max_claims: int = 14

    def run(self, request: TopicRequest) -> ResearchOutcome:
        capabilities = [provider.get_capabilities() for provider in self.providers]
        usable = [
            provider
            for provider, capability in zip(self.providers, capabilities, strict=True)
            if capability.usable
        ]
        if not usable:
            reasons = "; ".join(
                f"{c.provider} : {c.detail or c.state.value}" for c in capabilities
            ) or "aucun fournisseur déclaré"
            raise NoUsableProvider(
                "recherche impossible, aucun fournisseur joignable — " + reasons
            )

        documents = self._gather(usable, request)
        if not documents:
            raise NoUsableProvider(
                f"aucun document rapporté pour {request.topic!r} par "
                f"{', '.join(p.name for p in usable)}"
            )

        sources = [_to_source(document) for document in documents]
        candidates = extract_candidates(
            topic=request.topic,
            documents=[(index, doc.text) for index, doc in enumerate(documents)],
            settings=self.extraction,
        )
        groups = group_duplicates(candidates, self.extraction.duplicate_threshold)[
            : self.max_claims
        ]

        evidence: list[Evidence] = []
        claims: list[Claim] = []
        nodes: list[GraphNode] = []

        for group in groups:
            leader = group[0]
            signals: list[EvidenceSignal] = []
            evidence_ids: list[str] = []
            for member in group:
                document = documents[member.document_index]
                source = sources[member.document_index]
                stance = (
                    EvidenceStance.CONTRADICTS
                    if member.negated != leader.negated
                    else EvidenceStance.SUPPORTS
                )
                strength = round(min(1.0, 0.30 + 0.70 * member.salience), 4)
                item = Evidence(
                    source_id=source.id,
                    stance=stance,
                    quote=member.text,
                    strength=strength,
                    locator=f"{document.locator_prefix}#p{member.sentence_index}",
                )
                evidence.append(item)
                evidence_ids.append(item.id)
                signals.append(
                    EvidenceSignal(
                        source_key=source.id,
                        stance=stance,
                        strength=strength,
                        authority=document.authority,
                    )
                )

            outcome = self.confidence.evaluate(signals)
            claim = Claim(
                text=leader.text,
                kind=leader.kind,
                evidence_ids=evidence_ids,
                verification=outcome.verification,
                confidence=outcome.confidence,
                demonstrability=demonstrability(leader.text, leader.kind),
            )
            claims.append(claim)
            nodes.append(
                GraphNode(
                    claim_id=claim.id,
                    text=claim.text,
                    kind=claim.kind,
                    document_index=leader.document_index,
                    sentence_index=leader.sentence_index,
                )
            )

        graph = FactGraph(
            claim_ids=[claim.id for claim in claims],
            edges=build_edges(nodes, self.edge_rules),
        )

        coverage, uncovered = _coverage(request.topic, claims)
        state = ResearchState(
            topic_request_id=request.id,
            question=request.topic,
            sources=sources,
            evidence=evidence,
            claims=claims,
            fact_graph=graph,
            coverage=coverage,
            open_questions=_open_questions(claims, uncovered),
        )
        return ResearchOutcome(
            state=state,
            capabilities=capabilities,
            notes=_notes(documents, candidates, groups, claims),
        )

    # ------------------------------------------------------------------ étapes

    def _gather(
        self,
        providers: list[SearchProvider],
        request: TopicRequest,
    ) -> list[SourceDocument]:
        query = SearchQuery(text=request.topic, language=request.language)
        seen: set[tuple[str, str]] = set()
        documents: list[SourceDocument] = []
        for provider in providers:
            for document in provider.search(query):
                key = (normalise(document.title), document.url or "")
                if key in seen:
                    continue
                seen.add(key)
                documents.append(document)
        return documents


def _to_source(document: SourceDocument) -> SourceReference:
    return SourceReference(
        title=document.title,
        kind=document.kind,
        url=document.url,
        publisher=document.publisher,
        retrieved_at=document.retrieved_at,
        authority=document.authority,
        excerpt=document.text[:280],
    )


def _coverage(topic: str, claims: list[Claim]) -> tuple[float, list[str]]:
    """Part des termes du sujet effectivement couverts par une affirmation."""
    terms = {term for term in tokens(normalise(topic)) if len(term) > 2}
    if not terms:
        return 0.0, []
    covered_text = normalise(" ".join(claim.text for claim in claims))
    uncovered = sorted(term for term in terms if term not in covered_text)
    return round((len(terms) - len(uncovered)) / len(terms), 4), uncovered


def _open_questions(claims: list[Claim], uncovered: list[str]) -> list[str]:
    questions: list[str] = []
    for term in uncovered:
        questions.append(f"aucune source ne traite le terme du sujet : « {term} »")
    unverified = [c for c in claims if c.verification is VerificationStatus.UNVERIFIED]
    for claim in unverified[:6]:
        questions.append(
            f"affirmation non corroborée, une seconde source est nécessaire : "
            f"« {claim.text[:110]} »"
        )
    disputed = [c for c in claims if c.verification is VerificationStatus.DISPUTED]
    for claim in disputed[:6]:
        questions.append(f"affirmation disputée par les sources : « {claim.text[:110]} »")
    return questions


def _notes(
    documents: list[SourceDocument],
    candidates: list[SentenceCandidate],
    groups: list[list[SentenceCandidate]],
    claims: list[Claim],
) -> list[str]:
    corroborated = sum(
        1 for claim in claims if claim.verification is VerificationStatus.CORROBORATED
    )
    return [
        f"{len(documents)} documents retenus",
        f"{len(candidates)} phrases candidates, regroupées en {len(groups)} affirmations",
        f"{corroborated}/{len(claims)} affirmations corroborées par au moins deux sources",
    ]
