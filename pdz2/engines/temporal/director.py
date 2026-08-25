"""Temporal Director : `DirectorState` + `VoiceTimeline` → `TemporalPlan`.

Il n'invente rien. Il découpe le temps **mesuré** en créneaux, transporte la
courbe émotionnelle décidée par la réalisation, dérive quatre courbes cibles
selon des règles écrites, et constate ce qu'il ne corrige pas.

Ce qu'il refuse, plutôt que de l'arranger :

* une timeline qui ne décrit pas ce script ;
* un script qui ne descend pas de ce DirectorState ;
* une réplique sans intention de plan correspondante.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pdz2.contracts.direction import DirectorState
from pdz2.contracts.script import ScriptState, VoiceTimeline
from pdz2.contracts.temporal import (
    RhythmFinding,
    RhythmFindingKind,
    TemporalPlan,
)
from pdz2.engines.temporal.curves import (
    CurveRules,
    SlotContext,
    attention_curve,
    emotional_curve,
    information_curve,
    motion_curve,
    visual_novelty_curve,
)
from pdz2.engines.temporal.slots import SlotRules, carve_slots

__all__ = ["TemporalDirector", "TemporalOutcome", "TemporalRejected"]

MONOTONY_THRESHOLD = 0.08
"""Coefficient de variation des durées sous lequel la cadence est métronomique."""

SATURATION_THRESHOLD = 0.93
"""Densité au-delà de laquelle le passage sature : 7 syllabes/seconde.

Repère mesuré : une narration documentaire courante tourne à 5,8 syll/s, soit
0,77. Le constat de saturation doit désigner l'exception, pas la norme."""

ATTENTION_TROUGH = 0.35
"""Attention modélisée sous laquelle un décrochage est probable."""


class TemporalRejected(ValueError):
    """Les entrées ne permettent pas de construire un plan temporel."""


@dataclass
class TemporalOutcome:
    plan: TemporalPlan
    notes: list[str] = field(default_factory=list)


@dataclass
class TemporalDirector:
    curve_rules: CurveRules = field(default_factory=CurveRules)
    slot_rules: SlotRules = field(default_factory=SlotRules)

    def plan(
        self,
        *,
        director_state: DirectorState,
        script: ScriptState,
        timeline: VoiceTimeline,
    ) -> TemporalOutcome:
        self._check_lineage(director_state, script, timeline)

        carving = carve_slots(
            timeline=timeline,
            script=script,
            pacing=director_state.pacing,
            rules=self.slot_rules,
        )
        contexts = self._contexts(director_state, script, carving.slots)
        total = timeline.total_duration_s

        information = information_curve(contexts, total, script)
        curves = {
            "emotional": emotional_curve(
                director_state.emotional_curve, contexts, total
            ),
            "information": information,
            "attention": attention_curve(contexts, total, self.curve_rules),
            "motion": motion_curve(
                contexts, total, director_state.pacing, information, self.curve_rules
            ),
            "visual_novelty": visual_novelty_curve(contexts, total, self.curve_rules),
        }

        findings = list(carving.findings)
        findings.extend(self._observe(contexts, curves, total))

        plan = TemporalPlan(
            director_state_id=director_state.id,
            voice_timeline_id=timeline.id,
            total_duration_s=round(total, 6),
            slots=carving.slots,
            emotional_curve=curves["emotional"],
            attention_curve=curves["attention"],
            information_curve=curves["information"],
            motion_curve=curves["motion"],
            visual_novelty_curve=curves["visual_novelty"],
            findings=findings,
            parent_id=timeline.id,
        )
        return TemporalOutcome(
            plan=plan,
            notes=[
                f"{len(carving.slots)} créneaux pavant {total:.3f}s d'audio mesuré",
                f"rythme « {director_state.pacing.value} »",
                f"{len(findings)} constat(s) de rythme",
            ],
        )

    # ------------------------------------------------------------------ règles

    @staticmethod
    def _check_lineage(
        director_state: DirectorState,
        script: ScriptState,
        timeline: VoiceTimeline,
    ) -> None:
        if script.director_state_id != director_state.id:
            raise TemporalRejected(
                "le script ne descend pas de ce DirectorState "
                f"({script.director_state_id} ≠ {director_state.id})"
            )
        if timeline.script_state_id != script.id:
            raise TemporalRejected(
                "la timeline ne décrit pas ce script "
                f"({timeline.script_state_id} ≠ {script.id})"
            )
        covered = {segment.line_index for segment in timeline.segments}
        expected = {line.index for line in script.lines}
        if covered != expected:
            raise TemporalRejected(
                f"la timeline couvre {sorted(covered)} pour un script en "
                f"{sorted(expected)}"
            )

    @staticmethod
    def _contexts(
        director_state: DirectorState,
        script: ScriptState,
        slots,
    ) -> list[SlotContext]:
        by_index = {line.index: line for line in script.lines}
        intents = {intent.order: intent for intent in director_state.shot_intents}
        contexts: list[SlotContext] = []
        seen_claims: set[str] = set()
        previous_function = None
        function_changed_at = 0.0

        for slot in slots:
            line = by_index[slot.line_index]
            if line.shot_intent_order is None:
                raise TemporalRejected(
                    f"réplique {line.index} sans intention de plan : le script ne "
                    "descend pas d'une décision de réalisation"
                )
            intent = intents.get(line.shot_intent_order)
            if intent is None:
                raise TemporalRejected(
                    f"réplique {line.index} renvoie au plan {line.shot_intent_order}, "
                    "absent du DirectorState"
                )
            claim_id = intent.claim_id
            previous = contexts[-1] if contexts else None
            anchors = tuple(intent.anchor_ids)

            if previous_function is not None and intent.narrative_function is not previous_function:
                function_changed_at = slot.start_s
            previous_function = intent.narrative_function

            contexts.append(
                SlotContext(
                    slot=slot,
                    function=intent.narrative_function,
                    claim_id=claim_id,
                    anchor_ids=anchors,
                    text=line.text,
                    is_new_claim=claim_id is not None and claim_id not in seen_claims,
                    same_claim_as_previous=(
                        previous is not None
                        and claim_id is not None
                        and previous.claim_id == claim_id
                    ),
                    same_anchors_as_previous=(
                        previous is not None
                        and bool(anchors)
                        and previous.anchor_ids == anchors
                    ),
                    seconds_since_function_change=slot.start_s - function_changed_at,
                )
            )
            if claim_id is not None:
                seen_claims.add(claim_id)
        return contexts

    @staticmethod
    def _observe(contexts, curves, total: float) -> list[RhythmFinding]:
        """Constats qui ne changent rien, mais que personne ne peut ignorer."""
        findings: list[RhythmFinding] = []
        durations = [context.slot.duration_s for context in contexts]

        if len(durations) >= 2:
            mean = sum(durations) / len(durations)
            variance = sum((value - mean) ** 2 for value in durations) / len(durations)
            variety = (variance**0.5 / mean) if mean > 0 else 0.0
            if variety < MONOTONY_THRESHOLD:
                findings.append(
                    RhythmFinding(
                        kind=RhythmFindingKind.MONOTONOUS_CADENCE,
                        detail=(
                            f"les {len(durations)} plans ont des durées quasi "
                            f"identiques (variation {variety:.3f}) — le §8 proscrit "
                            "la répétition autant que la surstimulation"
                        ),
                        measured=round(variety, 4),
                        threshold=MONOTONY_THRESHOLD,
                    )
                )

        for context in contexts:
            position = min(
                1.0, (context.slot.start_s + context.slot.duration_s / 2) / total
            )
            density = curves["information"].value_at(position)
            if density >= SATURATION_THRESHOLD:
                findings.append(
                    RhythmFinding(
                        kind=RhythmFindingKind.DENSITY_SATURATED,
                        shot_id=context.slot.shot_id,
                        detail=(
                            f"débit de parole saturé ({density:.2f}) — le spectateur "
                            "n'aura pas le temps de voir ce qu'on lui montre"
                        ),
                        measured=round(density, 4),
                        threshold=SATURATION_THRESHOLD,
                    )
                )
            attention = curves["attention"].value_at(position)
            if attention <= ATTENTION_TROUGH:
                findings.append(
                    RhythmFinding(
                        kind=RhythmFindingKind.ATTENTION_TROUGH,
                        shot_id=context.slot.shot_id,
                        detail=(
                            f"attention modélisée basse ({attention:.2f}) — prévoir "
                            "une rupture visuelle ou raccourcir ce qui précède"
                        ),
                        measured=round(attention, 4),
                        threshold=ATTENTION_TROUGH,
                    )
                )
            if context.same_claim_as_previous and context.same_anchors_as_previous:
                findings.append(
                    RhythmFinding(
                        kind=RhythmFindingKind.VISUAL_REPETITION,
                        shot_id=context.slot.shot_id,
                        detail=(
                            "même affirmation et mêmes ancres que le plan précédent — "
                            "la demande de nouveauté visuelle est relevée d'autant"
                        ),
                    )
                )
        return findings
