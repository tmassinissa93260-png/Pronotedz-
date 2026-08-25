"""Contrats du moteur de recherche factuelle et du Fact Graph.

Invariant central du cahier des charges : **jamais transformer une
affirmation non vérifiée en fait certain**. Il est ici structurel, pas
documentaire — une `Claim` sans preuve ne peut pas porter de confiance.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from enum import Enum
from typing import Self

from pydantic import Field, model_validator

from pdz2.contracts.base import Contract, Element, contract
from pdz2.contracts.enums import AspectRatio, Platform, Tone

__all__ = [
    "SourceKind",
    "EvidenceStance",
    "ClaimKind",
    "VerificationStatus",
    "CausalRelation",
    "SourceReference",
    "Evidence",
    "Claim",
    "CausalEdge",
    "FactGraph",
    "ResearchState",
    "TopicRequest",
    "UNVERIFIED_CONFIDENCE_CEILING",
]

UNVERIFIED_CONFIDENCE_CEILING = 0.5
"""Plafond de confiance d'une affirmation non vérifiée.

Au-dessus, l'affirmation serait présentée au spectateur comme un fait ; le
contrat le refuse.
"""


class SourceKind(str, Enum):
    PAPER = "paper"
    ENCYCLOPEDIA = "encyclopedia"
    DOCUMENTATION = "documentation"
    NEWS = "news"
    BOOK = "book"
    DATASET = "dataset"
    STANDARD = "standard"
    EXPERT = "expert"
    UNKNOWN = "unknown"


class EvidenceStance(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    QUALIFIES = "qualifies"
    UNCLEAR = "unclear"


class ClaimKind(str, Enum):
    FACT = "fact"
    MECHANISM = "mechanism"
    QUANTITY = "quantity"
    DEFINITION = "definition"
    CONSEQUENCE = "consequence"
    COMPARISON = "comparison"


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    CORROBORATED = "corroborated"
    DISPUTED = "disputed"
    REFUTED = "refuted"


class CausalRelation(str, Enum):
    CAUSES = "causes"
    ENABLES = "enables"
    REQUIRES = "requires"
    CONTRASTS_WITH = "contrasts_with"
    QUANTIFIES = "quantifies"


@contract("source_reference", "1.0.0")
class SourceReference(Contract):
    title: str = Field(min_length=1)
    kind: SourceKind = SourceKind.UNKNOWN
    url: str | None = None
    publisher: str | None = None
    published_on: date | None = None
    retrieved_at: datetime | None = None
    authority: float = Field(default=0.5, ge=0.0, le=1.0)
    """Autorité de la source, estimée par le moteur de recherche."""

    excerpt: str | None = None


@contract("evidence", "1.0.0")
class Evidence(Contract):
    source_id: str = Field(min_length=1)
    stance: EvidenceStance
    quote: str = Field(min_length=1)
    strength: float = Field(ge=0.0, le=1.0)
    locator: str | None = None
    """Où retrouver la citation dans la source : page, section, horodatage."""


@contract("claim", "1.1.0")
class Claim(Contract):
    """Une affirmation, ses preuves, et ce qu'il faut montrer pour la prouver."""

    text: str = Field(min_length=1)
    kind: ClaimKind = ClaimKind.FACT
    evidence_ids: list[str] = Field(default_factory=list)
    verification: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    load_bearing: bool = False
    """Affirmation « importante » : la démonstration s'écroule sans elle."""

    demonstrability: float = Field(default=0.0, ge=0.0, le=1.0)
    """MESURE : à quel point l'affirmation est *montrable*, calculée par le
    moteur de recherche. Indice de tri, pas une autorisation — cocher
    `visually_demonstrable` reste une décision du Director Core, adossée à un
    `visual_proof` rédigé. Ajouté en 1.1.0 ; absent des documents 1.0.0, où il
    vaut 0.0 (« jamais mesuré »)."""

    # Visual Evidence Engine — cahier des charges §5.
    causal_mechanism: str | None = None
    evidence_required: str | None = None
    visual_proof: str | None = None
    visually_demonstrable: bool = False

    depends_on: list[str] = Field(default_factory=list)
    """Identifiants d'affirmations dont celle-ci découle."""

    @model_validator(mode="after")
    def _never_certain_without_evidence(self) -> Self:
        if not self.evidence_ids:
            if self.verification is not VerificationStatus.UNVERIFIED:
                raise ValueError(
                    f"affirmation sans preuve marquée {self.verification.value} : "
                    "une affirmation non étayée reste 'unverified'"
                )
            if self.confidence != 0.0:
                raise ValueError("affirmation sans preuve : confiance forcée à 0")
        if (
            self.verification is VerificationStatus.UNVERIFIED
            and self.confidence > UNVERIFIED_CONFIDENCE_CEILING
        ):
            raise ValueError(
                f"confiance {self.confidence} au-dessus du plafond "
                f"{UNVERIFIED_CONFIDENCE_CEILING} pour une affirmation non vérifiée"
            )
        if self.verification is VerificationStatus.REFUTED and self.confidence > 0.0:
            raise ValueError("une affirmation réfutée ne porte pas de confiance")
        return self

    @model_validator(mode="after")
    def _visual_proof_is_concrete(self) -> Self:
        if self.visually_demonstrable and not (self.visual_proof or "").strip():
            raise ValueError(
                "affirmation déclarée démontrable visuellement sans visual_proof : "
                "que doit physiquement voir le spectateur ?"
            )
        if self.load_bearing:
            missing = [
                name
                for name, value in (
                    ("causal_mechanism", self.causal_mechanism),
                    ("evidence_required", self.evidence_required),
                    ("visual_proof", self.visual_proof),
                )
                if not (value or "").strip()
            ]
            if missing:
                raise ValueError(
                    "affirmation porteuse incomplète, manque : " + ", ".join(missing)
                )
        if self.id in self.depends_on:
            raise ValueError("une affirmation ne dépend pas d'elle-même")
        return self


class CausalEdge(Element):
    from_claim_id: str = Field(min_length=1)
    to_claim_id: str = Field(min_length=1)
    relation: CausalRelation = CausalRelation.CAUSES
    explanation: str = ""

    @model_validator(mode="after")
    def _no_self_loop(self) -> Self:
        if self.from_claim_id == self.to_claim_id:
            raise ValueError("arête causale réflexive")
        return self


@contract("fact_graph", "1.0.0")
class FactGraph(Contract):
    """Graphe causal des affirmations. Acyclique par construction."""

    claim_ids: list[str] = Field(default_factory=list)
    edges: list[CausalEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        known = set(self.claim_ids)
        if len(known) != len(self.claim_ids):
            raise ValueError("fact graph : identifiant d'affirmation en double")
        for edge in self.edges:
            for endpoint in (edge.from_claim_id, edge.to_claim_id):
                if endpoint not in known:
                    raise ValueError(f"fact graph : arête vers un inconnu {endpoint!r}")
        if self._has_cycle():
            raise ValueError("fact graph : chaîne causale cyclique")
        return self

    def _has_cycle(self) -> bool:
        successors: dict[str, list[str]] = {claim: [] for claim in self.claim_ids}
        for edge in self.edges:
            successors[edge.from_claim_id].append(edge.to_claim_id)
        state: dict[str, int] = {}

        def visit(node: str) -> bool:
            mark = state.get(node, 0)
            if mark == 1:
                return True
            if mark == 2:
                return False
            state[node] = 1
            for nxt in successors[node]:
                if visit(nxt):
                    return True
            state[node] = 2
            return False

        return any(visit(node) for node in self.claim_ids)

    def topological_order(self, subset: Iterable[str] | None = None) -> list[str]:
        """Ordre causal : une cause précède toujours sa conséquence.

        `subset` restreint l'ordre au **sous-graphe induit** par ces
        affirmations. C'est ce qu'il faut quand la réalisation n'en retient
        qu'une partie : une dépendance vers une affirmation écartée ne doit
        plus peser sur l'ordre de celles qui restent, sinon un plan se
        retrouve relégué à cause d'un lien vers un plan qui n'existe pas.
        """
        if subset is None:
            nodes = list(self.claim_ids)
        else:
            kept = set(subset)
            unknown = kept - set(self.claim_ids)
            if unknown:
                raise KeyError(f"affirmations hors du graphe : {sorted(unknown)}")
            nodes = [claim for claim in self.claim_ids if claim in kept]

        scope = set(nodes)
        indegree = dict.fromkeys(nodes, 0)
        successors: dict[str, list[str]] = {claim: [] for claim in nodes}
        for edge in self.edges:
            if edge.from_claim_id not in scope or edge.to_claim_id not in scope:
                continue
            successors[edge.from_claim_id].append(edge.to_claim_id)
            indegree[edge.to_claim_id] += 1
        ready = [node for node in nodes if indegree[node] == 0]
        order: list[str] = []
        while ready:
            node = ready.pop(0)
            order.append(node)
            for nxt in successors[node]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    ready.append(nxt)
        return order


@contract("topic_request", "1.0.0")
class TopicRequest(Contract):
    """Entrée du compilateur : une idée, un format, un budget."""

    topic: str = Field(min_length=1)
    language: str = Field(default="fr", min_length=2, max_length=8)
    target_duration_s: float = Field(gt=0.0, le=600.0)
    aspect_ratio: AspectRatio = AspectRatio.VERTICAL
    platform: Platform = Platform.TIKTOK
    """Plateforme visée. Contraint le format : voir `_the_format_suits_the_platform`."""
    audience: str = "grand public curieux"
    tone: Tone = Tone.DOCUMENTARY
    budget_cap_usd: float | None = Field(default=None, ge=0.0)
    allow_ai_video: bool = True
    """Faux : l'épisode doit être produit sans génération vidéo par IA."""

    seed: int | None = None
    """Graine de reproductibilité, propagée jusqu'aux générateurs."""

    @model_validator(mode="after")
    def _the_format_suits_the_platform(self) -> Self:
        """Un format qui contredit la plateforme est une incohérence muette.

        `platform` était enregistrée et lue par personne, pendant que
        `aspect_ratio` gouvernait seule la forme du livrable. Rien n'empêchait
        de commander un épisode TikTok en 16:9 — l'épisode se serait produit,
        et son format aurait été découvert à la publication.

        Les plateformes verticales n'acceptent pas un format paysage. YouTube
        et « generic » n'imposent rien : on ne refuse que ce qui est
        réellement incompatible.
        """
        verticales = {Platform.TIKTOK, Platform.SHORTS, Platform.REELS}
        if self.platform in verticales and self.aspect_ratio is AspectRatio.HORIZONTAL:
            raise ValueError(
                f"{self.platform.value} n'accepte pas un format "
                f"{self.aspect_ratio.value} : choisir un format vertical, ou "
                "une plateforme qui prend le paysage"
            )
        return self


@contract("research_state", "1.0.0")
class ResearchState(Contract):
    """Sortie complète du moteur de recherche, refermée sur elle-même."""

    topic_request_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    sources: list[SourceReference] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    fact_graph: FactGraph
    coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    open_questions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _referentially_closed(self) -> Self:
        source_ids = {source.id for source in self.sources}
        evidence_ids = {item.id for item in self.evidence}
        claim_ids = {claim.id for claim in self.claims}

        for item in self.evidence:
            if item.source_id not in source_ids:
                raise ValueError(f"preuve {item.id} : source inconnue {item.source_id!r}")
        for claim in self.claims:
            for ref in claim.evidence_ids:
                if ref not in evidence_ids:
                    raise ValueError(f"affirmation {claim.id} : preuve inconnue {ref!r}")
            for ref in claim.depends_on:
                if ref not in claim_ids:
                    raise ValueError(f"affirmation {claim.id} : dépendance inconnue {ref!r}")
        graph_claims = set(self.fact_graph.claim_ids)
        if not graph_claims <= claim_ids:
            unknown = sorted(graph_claims - claim_ids)
            raise ValueError(f"fact graph : affirmations absentes de l'état {unknown}")
        return self

    def claim(self, claim_id: str) -> Claim:
        for item in self.claims:
            if item.id == claim_id:
                return item
        raise KeyError(claim_id)

    def demonstrable_claims(self) -> list[Claim]:
        """Affirmations que le Visual Evidence Engine peut mettre en image."""
        return [claim for claim in self.claims if claim.visually_demonstrable]
