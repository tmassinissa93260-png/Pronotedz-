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
from pdz2.contracts.common import Curve, HexColour
from pdz2.contracts.enums import NarrativeFunction, Pacing, Tone

__all__ = [
    "AnchorKind",
    "AnchorDraft",
    "VisualStyleDecision",
    "VisualProofDraft",
    "DirectorBrief",
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


# ---------------------------------------------------------------------------
# Le brief de réalisation : la décision conceptuelle, produite **une fois**.
#
# Le cahier des charges est explicite : « Une décision conceptuelle doit être
# produite une fois puis transformée par des compilateurs déterministes. » Ce
# contrat est cette décision — et rien d'autre. Tout ce qui s'en déduit
# (chaîne causale, découpage, courbes, densité) est calculé, pas décidé.
#
# Il contient exactement ce qu'aucun calcul ne peut produire : une thèse, un
# ton, un registre visuel, une chute, et — pour chaque affirmation qu'on veut
# démontrer — ce que le spectateur doit physiquement voir.
#
# Il vit ici, avec les autres contrats, et non dans le moteur qui le consomme :
# un contrat est le langage commun des couches, pas la propriété de l'une
# d'elles. Il est ainsi enregistré dès l'import de `pdz2.contracts`.
# ---------------------------------------------------------------------------

class VisualStyleDecision(Element):
    """Le parti pris visuel, décidé une fois, comme le reste du brief.

    Ce sont les seuls champs de la `VisualBible` qu'aucun calcul ne peut
    produire : un choix de matière, de lumière et de couleur. Tout le reste de
    la bible s'en déduit — densité visuelle depuis la densité d'information,
    interdits depuis l'imagerie proscrite, langage caméra depuis le rythme.
    """

    style: str = Field(min_length=1)
    lighting: str = Field(min_length=1)
    palette: list[HexColour] = Field(min_length=2)
    """La première est la dominante. La forme est tenue par le type lui-même.

    Elle ne l'était pas : un raisonneur a rendu « bleu électrique, gris acier,
    blanc pur », le brief a été accepté, et la compilation visuelle est tombée
    trois étapes plus loin. Le refus appartient à la porte d'entrée."""

    lens_language: str = Field(min_length=1)
    materials: list[str] = Field(default_factory=list)
    texture: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    graphics: str = Field(min_length=1)
    typography_family: str = Field(default="Inter", min_length=1)


class AnchorDraft(Element):
    """Une ancre de continuité, telle que la réalisation la conçoit."""

    name: str = Field(min_length=1)
    kind: AnchorKind
    canonical_description: str = Field(min_length=1)
    identity: list[IdentityAttribute] = Field(min_length=1)


class VisualProofDraft(Element):
    """La réponse à « qu'est-ce que le spectateur doit physiquement voir ? »."""

    claim_id: str = Field(min_length=1)
    causal_mechanism: str = Field(min_length=1)
    evidence_required: str = Field(min_length=1)
    visual_proof: str = Field(min_length=1)
    anchor_names: list[str] = Field(default_factory=list)

    acknowledged_dispute: bool = False
    """À cocher pour employer une affirmation que les sources contestent.

    Le compilateur refuse une affirmation disputée sans cet aveu explicite :
    une vidéo documentaire ne présente pas par inadvertance un point contesté
    comme un fait acquis."""

    @model_validator(mode="after")
    def _proof_is_concrete(self) -> Self:
        if len(self.visual_proof.split()) < 4:
            raise ValueError(
                f"preuve visuelle trop vague pour {self.claim_id} : décrire ce qui "
                "est à l'écran, pas un thème"
            )
        return self


@contract("director_brief", "1.1.0")
class DirectorBrief(Contract):
    """Décision de réalisation. Aucune donnée de rendu, aucun fournisseur."""

    topic_request_id: str = Field(min_length=1)
    research_state_id: str = Field(min_length=1)

    thesis: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    tone: Tone
    pacing: Pacing
    ending_payoff: str = Field(min_length=1)
    visual_language: VisualLanguage

    visual_style: VisualStyleDecision | None = None
    """Parti pris esthétique de l'épisode. Ajouté en 1.1.0, facultatif.

    Absent, le compilateur applique un **préréglage déclaré** choisi sur le ton
    de l'épisode, et l'écrit dans ses notes : le style aura été *défaut*, pas
    *décidé*. Un préréglage est une table publiée dans
    `pdz2.engines.visual.presets`, pas une génération — rien n'est inventé au
    moment de la compilation."""

    anchors: list[AnchorDraft] = Field(default_factory=list)
    visual_proofs: list[VisualProofDraft] = Field(min_length=1)
    excluded_claim_ids: list[str] = Field(default_factory=list)

    author: str = Field(default="human", min_length=1)
    """Qui a pris la décision : « human », ou le nom du raisonneur."""

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        names = [anchor.name for anchor in self.anchors]
        if len(set(names)) != len(names):
            raise ValueError("brief : deux ancres portent le même nom")
        known = set(names)

        claims = [proof.claim_id for proof in self.visual_proofs]
        if len(set(claims)) != len(claims):
            raise ValueError("brief : deux preuves visuelles pour la même affirmation")

        excluded = set(self.excluded_claim_ids)
        clash = excluded & set(claims)
        if clash:
            raise ValueError(f"brief : affirmations à la fois retenues et exclues {sorted(clash)}")

        for proof in self.visual_proofs:
            unknown = [name for name in proof.anchor_names if name not in known]
            if unknown:
                raise ValueError(
                    f"brief : preuve de {proof.claim_id} citant des ancres inconnues {unknown}"
                )
        return self

    def proof_for(self, claim_id: str) -> VisualProofDraft | None:
        for proof in self.visual_proofs:
            if proof.claim_id == claim_id:
                return proof
        return None
