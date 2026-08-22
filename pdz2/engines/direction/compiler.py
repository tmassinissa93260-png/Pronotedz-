"""Director Core : compile une décision en `DirectorState`.

Entrées : la question, l'état de recherche, et **une** décision conceptuelle
(le `DirectorBrief`). Sortie : un `DirectorState` complet, obtenu sans aucun
appel supplémentaire à un modèle.

Ce que le compilateur calcule, et que personne n'a donc à décider :

    chaîne causale        ← ordre topologique du Fact Graph
    fonction de chaque plan ← nature de l'affirmation démontrée
    durée de chaque plan  ← budget réparti selon la fonction et le rythme
    courbe émotionnelle   ← suite des fonctions narratives
    densité d'information ← affirmations par seconde

Ce que le compilateur refuse, plutôt que de l'arranger :

    * une affirmation réfutée par les sources ;
    * une affirmation disputée sans aveu explicite dans le brief ;
    * une preuve visuelle portant sur une affirmation absente de la recherche ;
    * un budget temporel qui ne peut pas contenir les plans demandés.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pdz2.contracts.direction import (
    AnchorSpec,
    DirectorState,
    ShotIntent,
    VisualEvidencePlan,
)
from pdz2.contracts.enums import NarrativeFunction
from pdz2.contracts.research import (
    Claim,
    ClaimKind,
    ResearchState,
    TopicRequest,
    VerificationStatus,
)
from pdz2.engines.direction.brief import DirectorBrief
from pdz2.engines.direction.rhythm import (
    MIN_RHYTHM_VARIETY,
    PACING_SHOT_SECONDS,
    allocate_durations,
    emotional_curve,
    information_density,
    rhythm_variety,
)

__all__ = ["DirectorCompiler", "DirectionOutcome", "BriefRejected", "KIND_TO_FUNCTION"]


class BriefRejected(ValueError):
    """Le brief ne peut pas être compilé. La raison est toujours nommée."""


KIND_TO_FUNCTION: dict[ClaimKind, NarrativeFunction] = {
    ClaimKind.MECHANISM: NarrativeFunction.MECHANISM,
    ClaimKind.QUANTITY: NarrativeFunction.EVIDENCE,
    ClaimKind.COMPARISON: NarrativeFunction.CONTRAST,
    ClaimKind.CONSEQUENCE: NarrativeFunction.CONSEQUENCE,
    ClaimKind.DEFINITION: NarrativeFunction.SETUP,
    ClaimKind.FACT: NarrativeFunction.EVIDENCE,
}


@dataclass
class DirectionOutcome:
    state: DirectorState
    notes: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    """Affirmations écartées, avec la raison. Rien ne disparaît en silence."""


@dataclass
class DirectorCompiler:
    open_with_hook: bool = True
    close_with_payoff: bool = True
    max_shots: int = 12

    def compile(
        self,
        *,
        request: TopicRequest,
        research: ResearchState,
        brief: DirectorBrief,
    ) -> DirectionOutcome:
        self._check_lineage(request, research, brief)
        selected, dropped = self._select(research, brief)

        anchors = [
            AnchorSpec(
                name=draft.name,
                kind=draft.kind,
                canonical_description=draft.canonical_description,
                identity=list(draft.identity),
            )
            for draft in brief.anchors
        ]
        anchor_ids = {anchor.name: anchor.id for anchor in anchors}

        functions = [KIND_TO_FUNCTION[claim.kind] for claim in selected]
        if self.open_with_hook:
            functions.insert(0, NarrativeFunction.HOOK)
        if self.close_with_payoff:
            functions.append(NarrativeFunction.PAYOFF)

        durations = allocate_durations(functions, request.target_duration_s, brief.pacing)

        intents: list[ShotIntent] = []
        offset = 1 if self.open_with_hook else 0
        for order, (function, duration) in enumerate(
            zip(functions, durations, strict=True)
        ):
            claim = self._claim_for(order, offset, selected, function)
            proof = brief.proof_for(claim.id) if claim is not None else None
            intents.append(
                ShotIntent(
                    order=order,
                    narrative_function=function,
                    claim_id=claim.id if claim is not None else None,
                    what_the_viewer_must_understand=(
                        claim.text if claim is not None else brief.thesis
                    ),
                    what_the_viewer_must_see=(
                        proof.visual_proof
                        if proof is not None
                        else self._framing_shot_subject(function, brief)
                    ),
                    anchor_ids=[
                        anchor_ids[name]
                        for name in (proof.anchor_names if proof is not None else [])
                    ],
                    target_duration_s=duration,
                )
            )

        claim_ids = [claim.id for claim in selected]
        state = DirectorState(
            research_state_id=research.id,
            topic_request_id=request.id,
            thesis=brief.thesis,
            audience=brief.audience,
            tone=brief.tone,
            pacing=brief.pacing,
            causal_chain=claim_ids,
            claim_ids=claim_ids,
            evidence_plan=[
                VisualEvidencePlan(
                    claim_id=proof.claim_id,
                    causal_mechanism=proof.causal_mechanism,
                    evidence_required=proof.evidence_required,
                    visual_proof=proof.visual_proof,
                )
                for proof in brief.visual_proofs
                if proof.claim_id in set(claim_ids)
            ],
            visual_language=brief.visual_language,
            continuity_anchors=anchors,
            shot_intents=intents,
            emotional_curve=emotional_curve(functions, durations),
            information_density=information_density(
                len(selected), request.target_duration_s
            ),
            ending_payoff=brief.ending_payoff,
            parent_id=brief.id,
        )
        notes = [
            f"{len(selected)} affirmations retenues sur {len(research.claims)}",
            f"{len(intents)} plans pour {request.target_duration_s:g}s "
            f"({brief.pacing.value})",
            f"densité d'information {state.information_density}",
        ]
        notes.extend(self._rhythm_notes(durations, brief, request))
        return DirectionOutcome(state=state, notes=notes, dropped=dropped)

    @staticmethod
    def _rhythm_notes(
        durations: list[float],
        brief: DirectorBrief,
        request: TopicRequest,
    ) -> list[str]:
        variety = rhythm_variety(durations)
        if variety >= MIN_RHYTHM_VARIETY:
            return [f"variété de cadence {variety}"]
        floor, ceiling = PACING_SHOT_SECONDS[brief.pacing]
        span = request.target_duration_s / len(durations)
        saturated = "plafond" if span >= ceiling - 1e-6 else "plancher"
        return [
            f"cadence métronomique (variété {variety}) : les {len(durations)} plans "
            f"butent tous sur le {saturated} de « {brief.pacing.value} » "
            f"({floor:g}–{ceiling:g}s). Le §8 proscrit la répétition — ajouter des "
            f"affirmations démontrables, allonger la durée cible, ou changer de rythme."
        ]

    # ------------------------------------------------------------------ règles

    def _check_lineage(
        self,
        request: TopicRequest,
        research: ResearchState,
        brief: DirectorBrief,
    ) -> None:
        if research.topic_request_id != request.id:
            raise BriefRejected(
                "l'état de recherche ne porte pas sur cette question "
                f"({research.topic_request_id} ≠ {request.id})"
            )
        if brief.research_state_id != research.id:
            raise BriefRejected(
                "le brief a été rédigé sur un autre état de recherche "
                f"({brief.research_state_id} ≠ {research.id})"
            )

    def _select(
        self,
        research: ResearchState,
        brief: DirectorBrief,
    ) -> tuple[list[Claim], list[str]]:
        """Retient les affirmations démontrables, dans l'ordre causal.

        Le contrat garantit déjà qu'une affirmation n'est pas à la fois
        démontrée et exclue : inutile de refiltrer ici. Les exclusions sont
        une trace éditoriale — « j'ai vu ces affirmations et je les laisse de
        côté » — et le compilateur vérifie seulement qu'elles existent.
        """
        by_id = {claim.id: claim for claim in research.claims}
        dropped: list[str] = []
        keepers: dict[str, Claim] = {}

        unknown_exclusions = [
            claim_id for claim_id in brief.excluded_claim_ids if claim_id not in by_id
        ]
        if unknown_exclusions:
            raise BriefRejected(
                f"exclusions portant sur des affirmations inconnues : {unknown_exclusions}"
            )
        for claim_id in brief.excluded_claim_ids:
            dropped.append(f"{claim_id} : écartée explicitement par le brief")

        budget = self.max_shots - int(self.open_with_hook) - int(self.close_with_payoff)
        if budget < 1:
            raise BriefRejected(
                f"max_shots={self.max_shots} ne laisse aucun plan démonstratif "
                f"une fois l'ouverture et la chute posées"
            )

        for proof in brief.visual_proofs:
            claim = by_id.get(proof.claim_id)
            if claim is None:
                raise BriefRejected(
                    f"preuve visuelle sur une affirmation absente de la recherche : "
                    f"{proof.claim_id}"
                )
            if claim.verification is VerificationStatus.REFUTED:
                raise BriefRejected(
                    f"affirmation réfutée par les sources, elle ne peut pas être "
                    f"démontrée : « {claim.text[:100]} »"
                )
            if (
                claim.verification is VerificationStatus.DISPUTED
                and not proof.acknowledged_dispute
            ):
                raise BriefRejected(
                    "affirmation disputée par les sources sans aveu explicite — "
                    "poser acknowledged_dispute=true pour l'assumer, ou l'exclure : "
                    f"« {claim.text[:100]} »"
                )
            keepers[claim.id] = claim

        ordered = self._causal_order(research, keepers)
        if len(ordered) > budget:
            for claim in ordered[budget:]:
                dropped.append(
                    f"{claim.id} : au-delà de {budget} plans démonstratifs "
                    f"(confiance {claim.confidence})"
                )
            ordered = ordered[:budget]
        return ordered, dropped

    def _causal_order(
        self,
        research: ResearchState,
        keepers: dict[str, Claim],
    ) -> list[Claim]:
        """Ordre du Fact Graph restreint aux retenues ; sinon, confiance."""
        graph_order = research.fact_graph.topological_order(subset=keepers)
        ranked = [keepers[cid] for cid in graph_order if cid in keepers]
        seen = {claim.id for claim in ranked}
        leftovers = sorted(
            (claim for cid, claim in keepers.items() if cid not in seen),
            key=lambda claim: (-claim.confidence, claim.id),
        )
        return ranked + leftovers

    @staticmethod
    def _claim_for(
        order: int,
        offset: int,
        selected: list[Claim],
        function: NarrativeFunction,
    ) -> Claim | None:
        if function in {NarrativeFunction.HOOK, NarrativeFunction.PAYOFF}:
            return None
        index = order - offset
        return selected[index] if 0 <= index < len(selected) else None

    @staticmethod
    def _framing_shot_subject(function: NarrativeFunction, brief: DirectorBrief) -> str:
        """Sujet visuel des plans d'ouverture et de chute.

        Ils ne démontrent pas une affirmation : ils encadrent. Leur sujet est
        donc le registre visuel décidé dans le brief, pas une invention.
        """
        register = brief.visual_language.visual_register
        if function is NarrativeFunction.HOOK:
            return f"Ouverture dans le registre décidé : {register}"
        return f"Chute dans le registre décidé : {register}"
