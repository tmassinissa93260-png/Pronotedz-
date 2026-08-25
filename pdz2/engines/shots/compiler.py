"""ShotGraph Compiler : le découpage devient des plans exécutables.

Entrées : `DirectorState`, `TemporalPlan`, `VisualBible`, `ScriptState`,
`ResearchState`, `TopicRequest`. Sortie : un `ShotGraph` et les programmes
caméra qui vont avec.

**Aucune décision narrative n'apparaît ici.** Le sujet visuel d'un plan est la
preuve visuelle rédigée par la réalisation ; son exigence de preuve est celle
du plan de preuve ; son affirmation est celle de l'intention de plan. Le
compilateur les recopie. Ce qu'il décide est de la mise en image seule, et
chaque règle est écrite dans `grammar.py`.

Le lien exigé par le cahier des charges est structurel, pas rhétorique :

    Claim.id → VisualEvidencePlan.claim_id → ShotSpec.claim_id
                                          → ShotSpec.evidence_required
                                          → ShotSpec.visual_subject

Un plan démonstratif dont l'affirmation n'a pas de preuve visuelle rédigée est
refusé, et une affirmation de la chaîne causale sans aucun plan l'est aussi.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pdz2.contracts.direction import DirectorState
from pdz2.contracts.motion import CameraProgram
from pdz2.contracts.research import Claim, ResearchState, TopicRequest
from pdz2.contracts.script import ScriptState
from pdz2.contracts.shots import RenderConstraints, ShotEdge, ShotGraph, ShotSpec
from pdz2.contracts.temporal import TemporalPlan
from pdz2.contracts.visual import VisualBible
from pdz2.engines.shots.grammar import (
    audio_events_for,
    camera_for,
    compose,
    environment_motion_for,
    overlay_for,
    subject_motion_for,
    transition_between,
)

__all__ = ["ShotGraphCompiler", "ShotGraphOutcome", "ShotGraphRejected"]


class ShotGraphRejected(ValueError):
    """Les décisions amont ne permettent pas de composer un plan."""


@dataclass
class ShotGraphOutcome:
    graph: ShotGraph
    camera_programs: list[CameraProgram]
    notes: list[str] = field(default_factory=list)

    def camera_for_shot(self, shot_id: str) -> CameraProgram:
        shot = self.graph.shot(shot_id)
        for program in self.camera_programs:
            if program.id == shot.camera_program_id:
                return program
        raise KeyError(shot_id)


@dataclass
class ShotGraphCompiler:
    def compile(
        self,
        *,
        director_state: DirectorState,
        temporal_plan: TemporalPlan,
        visual_bible: VisualBible,
        script: ScriptState,
        research: ResearchState,
        request: TopicRequest,
    ) -> ShotGraphOutcome:
        self._check_lineage(director_state, temporal_plan, visual_bible, script)

        intents = {intent.order: intent for intent in director_state.shot_intents}
        lines = {line.index: line for line in script.lines}
        proofs = {plan.claim_id: plan for plan in director_state.evidence_plan}
        claims: dict[str, Claim] = {claim.id: claim for claim in research.claims}

        shots: list[ShotSpec] = []
        programs: list[CameraProgram] = []
        previous_claim: str | None = None
        previous_anchors: tuple[str, ...] = ()

        for index, slot in enumerate(temporal_plan.slots):
            line = lines[slot.line_index]
            intent = intents[line.shot_intent_order]
            targets = temporal_plan.targets_for(slot.shot_id)
            claim = claims.get(intent.claim_id) if intent.claim_id else None
            claim_kind = claim.kind if claim else None

            subject, evidence = self._subject_and_evidence(intent, proofs)
            camera = camera_for(
                motion_target=targets["motion"],
                index=index,
                duration_s=slot.duration_s,
            )
            programs.append(camera)

            anchors = tuple(intent.anchor_ids)
            shared = bool(anchors) and anchors == previous_anchors
            transition_in = (
                transition_between(
                    previous_claim=previous_claim,
                    claim_id=intent.claim_id,
                    shared_anchors=shared,
                    downstream_duration_s=slot.duration_s,
                    upstream_duration_s=temporal_plan.slots[index - 1].duration_s,
                )
                if index > 0
                else self._opening_transition(slot.duration_s)
            )

            shots.append(
                ShotSpec(
                    shot_id=slot.shot_id,
                    duration_s=round(slot.duration_s, 6),
                    narrative_function=intent.narrative_function,
                    claim_id=intent.claim_id,
                    evidence_required=evidence,
                    visual_subject=subject,
                    composition=compose(
                        function=intent.narrative_function,
                        novelty_target=targets["visual_novelty"],
                        index=index,
                        density=visual_bible.visual_density,
                    ),
                    camera_program_id=camera.id,
                    subject_motion=subject_motion_for(
                        motion_target=targets["motion"], claim_kind=claim_kind
                    ),
                    environment_motion=environment_motion_for(
                        motion_target=targets["motion"]
                    ),
                    transition_in=transition_in,
                    transition_out=self._closing_transition(
                        index, temporal_plan, slot.duration_s
                    ),
                    audio_events=audio_events_for(
                        function=intent.narrative_function,
                        motion_target=targets["motion"],
                        duration_s=slot.duration_s,
                    ),
                    text_overlay=overlay_for(
                        text=line.text,
                        claim_kind=claim_kind,
                        duration_s=slot.duration_s,
                        max_chars=visual_bible.typography.max_chars_per_line,
                    ),
                    continuity_dependencies=list(anchors),
                    render_constraints=self._constraints(
                        request, anchors, len(temporal_plan.slots)
                    ),
                    parent_id=intent.id,
                )
            )
            previous_claim = intent.claim_id
            previous_anchors = anchors

        shots = self._align_transitions(shots)
        edges = self._edges(shots)
        graph = ShotGraph(
            director_state_id=director_state.id,
            voice_timeline_id=temporal_plan.voice_timeline_id,
            visual_bible_id=visual_bible.id,
            shots=shots,
            edges=edges,
            total_duration_s=round(temporal_plan.total_duration_s, 6),
            parent_id=temporal_plan.id,
        )
        self._check_every_claim_is_shown(graph, director_state)
        return ShotGraphOutcome(
            graph=graph,
            camera_programs=programs,
            notes=self._notes(graph, programs, temporal_plan),
        )

    # ------------------------------------------------------------------ règles

    @staticmethod
    def _check_lineage(
        director_state: DirectorState,
        temporal_plan: TemporalPlan,
        visual_bible: VisualBible,
        script: ScriptState,
    ) -> None:
        if temporal_plan.director_state_id != director_state.id:
            raise ShotGraphRejected(
                "le plan temporel ne porte pas sur cet état de réalisation"
            )
        if visual_bible.director_state_id != director_state.id:
            raise ShotGraphRejected(
                "la bible visuelle ne porte pas sur cet état de réalisation"
            )
        if script.director_state_id != director_state.id:
            raise ShotGraphRejected(
                "le script ne descend pas de cet état de réalisation"
            )

    @staticmethod
    def _subject_and_evidence(intent, proofs) -> tuple[str, str | None]:
        """Sujet visuel et exigence de preuve, recopiés depuis la réalisation."""
        if intent.claim_id is None:
            # Ouverture et chute ne démontrent rien : leur sujet est déjà écrit.
            return intent.what_the_viewer_must_see, None
        proof = proofs.get(intent.claim_id)
        if proof is None:
            raise ShotGraphRejected(
                f"plan {intent.order} démontre {intent.claim_id} sans preuve visuelle "
                "au plan de preuve — le compilateur n'en invente pas"
            )
        return proof.visual_proof, proof.evidence_required

    @staticmethod
    def _opening_transition(duration_s: float):
        from pdz2.contracts.common import Transition
        from pdz2.contracts.enums import TransitionKind

        span = round(min(0.4, 0.25 * duration_s), 3)
        if span < 0.05:
            return Transition(kind=TransitionKind.CUT, duration_s=0.0)
        return Transition(kind=TransitionKind.FADE_IN, duration_s=span)

    @staticmethod
    def _closing_transition(index: int, plan: TemporalPlan, duration_s: float):
        from pdz2.contracts.common import Transition
        from pdz2.contracts.enums import TransitionKind

        if index < len(plan.slots) - 1:
            return Transition(kind=TransitionKind.CUT, duration_s=0.0)
        span = round(min(0.6, 0.25 * duration_s), 3)
        if span < 0.05:
            return Transition(kind=TransitionKind.CUT, duration_s=0.0)
        return Transition(kind=TransitionKind.FADE_OUT, duration_s=span)

    @staticmethod
    def _align_transitions(shots: list[ShotSpec]) -> list[ShotSpec]:
        """Un raccord est une seule chose, vue des deux côtés.

        La sortie d'un plan et l'entrée du suivant doivent décrire le même
        raccord, sans quoi le montage aurait deux vérités pour une coupe.
        """
        aligned = list(shots)
        for index in range(len(aligned) - 1):
            downstream = aligned[index + 1]
            upstream = aligned[index]
            if downstream.transition_in.kind.value == "cut":
                continue
            upstream.transition_out = downstream.transition_in.model_copy(deep=True)
        return aligned

    @staticmethod
    def _edges(shots: list[ShotSpec]) -> list[ShotEdge]:
        edges: list[ShotEdge] = []
        for upstream, downstream in zip(shots, shots[1:], strict=False):
            carried = [
                anchor
                for anchor in upstream.continuity_dependencies
                if anchor in downstream.continuity_dependencies
            ]
            edges.append(
                ShotEdge(
                    from_shot_id=upstream.shot_id,
                    to_shot_id=downstream.shot_id,
                    carried_anchor_ids=carried,
                )
            )
        return edges

    @staticmethod
    def _constraints(
        request: TopicRequest, anchors: tuple[str, ...], shot_count: int
    ) -> RenderConstraints:
        budget = (
            round(request.budget_cap_usd / shot_count, 6)
            if request.budget_cap_usd is not None and shot_count
            else None
        )
        return RenderConstraints(
            max_cost_usd=budget,
            requires_identity_lock=bool(anchors),
            allow_ai_video=request.allow_ai_video,
            deterministic_only=not request.allow_ai_video,
        )

    @staticmethod
    def _check_every_claim_is_shown(
        graph: ShotGraph, director_state: DirectorState
    ) -> None:
        shown = {shot.claim_id for shot in graph.shots if shot.claim_id}
        missing = [claim for claim in director_state.causal_chain if claim not in shown]
        if missing:
            raise ShotGraphRejected(
                "affirmations de la chaîne causale sans aucun plan qui les "
                f"démontre : {missing}"
            )

    @staticmethod
    def _notes(graph, programs, plan) -> list[str]:
        moving = sum(1 for program in programs if not program.locked)
        overlays = sum(1 for shot in graph.shots if shot.text_overlay is not None)
        demonstrative = sum(1 for shot in graph.shots if shot.claim_id)
        return [
            f"{len(graph.shots)} plans pavant {graph.total_duration_s:.3f}s",
            f"{demonstrative} plans démontrent une affirmation, "
            f"{len(graph.shots) - demonstrative} encadrent",
            f"{moving}/{len(programs)} caméras en mouvement",
            f"{overlays} incrustation(s) de grandeur chiffrée",
            f"{len(plan.findings)} constat(s) de rythme repris du plan temporel",
        ]
