"""Couche INTENTION NARRATIVE.

Le `DirectorState` dit *ce que l'épisode démontre et pourquoi*. Il ne dit
jamais *comment* c'est rendu : ni fournisseur, ni modèle, ni résolution, ni
stratégie de rendu. Cette frontière est vérifiée par un test d'architecture
(`pdz2/tests/test_layering.py`).
"""

from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import Field, model_validator

from pdz2.contracts.base import Contract, Element, contract
from pdz2.contracts.common import Curve
from pdz2.contracts.enums import NarrativeFunction, Pacing, Tone

__all__ = [
    "AnchorKind",
    "AttributeBinding",
    "IdentityAttribute",
    "AnchorSpec",
    "VisualEvidencePlan",
    "VisualLanguage",
    "ShotIntent",
    "DirectorState",
]


class AnchorKind(str, Enum):
    PERSON = "person"
    VEHICLE = "vehicle"
    OBJECT = "object"
    BUILDING = "building"
    MACHINE = "machine"
    ENVIRONMENT = "environment"


class AttributeBinding(str, Enum):
    FIXED = "fixed"
    """Ne doit jamais changer d'un plan à l'autre."""

    SOFT = "soft"
    """Peut varier dans une plage tolérée (angle, lumière)."""


class IdentityAttribute(Element):
    """Un trait d'identité nommé, pas une chaîne libre.

    La continuité est représentée dans les données : on ne demande jamais à un
    modèle de « se souvenir » d'un objet.
    """

    name: str = Field(min_length=1)
    value: str = Field(min_length=1)
    binding: AttributeBinding = AttributeBinding.FIXED


@contract("anchor_spec", "1.0.0")
class AnchorSpec(Contract):
    """Ancre de continuité : une entité qui doit rester elle-même."""

    name: str = Field(min_length=1)
    kind: AnchorKind
    canonical_description: str = Field(min_length=1)
    identity: list[IdentityAttribute] = Field(min_length=1)
    reference_asset_ids: list[str] = Field(default_factory=list)
    must_persist_across_shots: bool = True

    @model_validator(mode="after")
    def _identity_is_pinned(self) -> Self:
        names = [attribute.name for attribute in self.identity]
        if len(set(names)) != len(names):
            raise ValueError(f"ancre {self.name} : trait d'identité en double")
        if not any(a.binding is AttributeBinding.FIXED for a in self.identity):
            raise ValueError(
                f"ancre {self.name} : aucun trait 'fixed', l'identité n'est pas ancrée"
            )
        return self

    def fixed_attributes(self) -> list[IdentityAttribute]:
        return [a for a in self.identity if a.binding is AttributeBinding.FIXED]


class VisualEvidencePlan(Element):
    """Réponse à : que doit physiquement voir le spectateur ?"""

    claim_id: str = Field(min_length=1)
    causal_mechanism: str = Field(min_length=1)
    evidence_required: str = Field(min_length=1)
    visual_proof: str = Field(min_length=1)

    @model_validator(mode="after")
    def _not_an_abstract_illustration(self) -> Self:
        proof = self.visual_proof.strip()
        if len(proof.split()) < 4:
            raise ValueError(
                f"visual_proof trop vague pour {self.claim_id!r} : "
                "décrire ce qui est visible à l'écran, pas un thème"
            )
        return self


class VisualLanguage(Element):
    """Intention visuelle, au niveau narratif. La VisualBible la spécifie."""

    visual_register: str = Field(min_length=1)
    """Registre : documentaire technique, coupe transparente, macro réelle…"""

    metaphors: list[str] = Field(default_factory=list)
    forbidden_imagery: list[str] = Field(default_factory=list)
    recurring_motifs: list[str] = Field(default_factory=list)


@contract("shot_intent", "1.0.0")
class ShotIntent(Contract):
    """Ce qu'un plan doit accomplir. Aucune donnée de rendu ici."""

    order: int = Field(ge=0)
    narrative_function: NarrativeFunction
    claim_id: str | None = None
    what_the_viewer_must_understand: str = Field(min_length=1)
    what_the_viewer_must_see: str = Field(min_length=1)
    anchor_ids: list[str] = Field(default_factory=list)
    target_duration_s: float = Field(gt=0.0)
    """Cible indicative. La durée officielle vient du TTS réel (règle VOICE FIRST)."""

    @model_validator(mode="after")
    def _evidence_shots_cite_a_claim(self) -> Self:
        needs_claim = {
            NarrativeFunction.EVIDENCE,
            NarrativeFunction.MECHANISM,
        }
        if self.narrative_function in needs_claim and not self.claim_id:
            raise ValueError(
                f"plan {self.order} ({self.narrative_function.value}) sans claim_id : "
                "un plan de démonstration doit démontrer quelque chose"
            )
        return self


@contract("director_state", "1.0.0")
class DirectorState(Contract):
    """Décision conceptuelle unique, ensuite compilée de façon déterministe."""

    research_state_id: str = Field(min_length=1)
    topic_request_id: str = Field(min_length=1)

    thesis: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    tone: Tone
    pacing: Pacing

    causal_chain: list[str] = Field(min_length=1)
    """Identifiants d'affirmations, dans l'ordre de la démonstration."""

    claim_ids: list[str] = Field(min_length=1)
    evidence_plan: list[VisualEvidencePlan] = Field(default_factory=list)

    visual_language: VisualLanguage
    continuity_anchors: list[AnchorSpec] = Field(default_factory=list)
    shot_intents: list[ShotIntent] = Field(min_length=1)

    emotional_curve: Curve
    information_density: float = Field(ge=0.0, le=1.0)
    ending_payoff: str = Field(min_length=1)

    @model_validator(mode="after")
    def _internally_consistent(self) -> Self:
        known_claims = set(self.claim_ids)
        if len(known_claims) != len(self.claim_ids):
            raise ValueError("director state : claim_id en double")

        unknown_chain = [c for c in self.causal_chain if c not in known_claims]
        if unknown_chain:
            raise ValueError(f"chaîne causale hors périmètre : {unknown_chain}")

        planned = [plan.claim_id for plan in self.evidence_plan]
        if len(set(planned)) != len(planned):
            raise ValueError("plan de preuve visuelle : deux entrées pour une affirmation")
        unknown_plan = [c for c in planned if c not in known_claims]
        if unknown_plan:
            raise ValueError(f"plan de preuve visuelle hors périmètre : {unknown_plan}")

        anchor_ids = {anchor.id for anchor in self.continuity_anchors}
        orders = [intent.order for intent in self.shot_intents]
        if sorted(orders) != list(range(len(orders))):
            raise ValueError(f"intentions de plan non contiguës depuis 0 : {sorted(orders)}")
        for intent in self.shot_intents:
            if intent.claim_id is not None and intent.claim_id not in known_claims:
                raise ValueError(
                    f"plan {intent.order} : affirmation inconnue {intent.claim_id!r}"
                )
            unknown_anchors = [a for a in intent.anchor_ids if a not in anchor_ids]
            if unknown_anchors:
                raise ValueError(f"plan {intent.order} : ancres inconnues {unknown_anchors}")
        return self

    def intent(self, order: int) -> ShotIntent:
        for intent in self.shot_intents:
            if intent.order == order:
                return intent
        raise KeyError(order)

    def anchor(self, anchor_id: str) -> AnchorSpec:
        for anchor in self.continuity_anchors:
            if anchor.id == anchor_id:
                return anchor
        raise KeyError(anchor_id)
