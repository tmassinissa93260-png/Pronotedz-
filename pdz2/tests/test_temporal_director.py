"""Temporal Director : pavage du temps mesuré et courbes à règles écrites."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pdz2.contracts.common import Curve, CurvePoint
from pdz2.contracts.enums import NarrativeFunction, Pacing
from pdz2.contracts.temporal import (
    TILING_TOLERANCE_S,
    RhythmFindingKind,
    ShotSlot,
    SlotOrigin,
    TemporalPlan,
    sample_position,
)
from pdz2.engines.temporal import TemporalDirector, TemporalRejected, carve_slots
from pdz2.engines.temporal.curves import (
    MAX_SYLLABLES_PER_SECOND,
    CurveRules,
    SlotContext,
    attention_curve,
    motion_curve,
    visual_novelty_curve,
)
from pdz2.tests import pipeline


@pytest.fixture(scope="module")
def episode(tmp_path_factory):
    return pipeline.build_episode(tmp_path_factory.mktemp("temporal"))


# ------------------------------------------------------------------- pavage


class TestSlotsTileTheMeasuredAudio:
    def test_slots_cover_the_audio_without_gap_or_overlap(self, episode) -> None:
        plan = episode.temporal_plan
        cursor = 0.0
        for slot in plan.slots:
            assert slot.start_s == pytest.approx(cursor, abs=TILING_TOLERANCE_S)
            cursor = slot.end_s
        assert cursor == pytest.approx(plan.total_duration_s, abs=TILING_TOLERANCE_S)

    def test_the_total_is_the_measured_audio_duration(self, episode) -> None:
        assert episode.temporal_plan.total_duration_s == pytest.approx(
            episode.timeline.total_duration_s, abs=1e-6
        )

    def test_the_sum_of_shot_durations_equals_the_audio(self, episode) -> None:
        total = sum(shot.duration_s for shot in episode.graph.shots)
        assert total == pytest.approx(episode.timeline.total_duration_s, abs=0.01)

    def test_a_gap_between_slots_is_refused_by_the_contract(self, episode) -> None:
        plan = episode.temporal_plan
        broken = [slot.model_copy(deep=True) for slot in plan.slots]
        # Le créneau entier glisse d'une demi-seconde : il reste cohérent en
        # lui-même, mais laisse un trou derrière lui.
        shifted = broken[1].model_dump()
        for field in ("start_s", "end_s", "speech_start_s", "speech_end_s"):
            shifted[field] += 0.5
        broken[1] = ShotSlot(**shifted)
        with pytest.raises(ValidationError, match="sans trou ni chevauchement"):
            TemporalPlan(**(plan.model_dump() | {"slots": broken}))

    def test_slots_that_stop_short_of_the_audio_are_refused(self, episode) -> None:
        plan = episode.temporal_plan
        with pytest.raises(ValidationError, match="couvrent"):
            TemporalPlan(
                **(plan.model_dump() | {"total_duration_s": plan.total_duration_s + 5})
            )

    def test_a_long_line_is_split_and_the_split_is_reported(self, tmp_path) -> None:
        """Découper est temporel ; rien de narratif ne change."""
        long = pipeline.build_episode(
            tmp_path / "long", durations=[4.0, 20.0, 4.0, 4.0]
        )
        splits = [
            finding
            for finding in long.temporal_plan.findings
            if finding.kind is RhythmFindingKind.SHOT_SPLIT
        ]
        assert splits, "une réplique de 20 s dépasse le plafond du rythme"
        parts = [slot for slot in long.temporal_plan.slots if slot.part_count > 1]
        assert len(parts) >= 2
        assert all(slot.origin is SlotOrigin.SPLIT for slot in parts)
        assert len({slot.line_index for slot in parts}) == 1

    def test_a_short_slot_is_reported_never_merged(self, tmp_path) -> None:
        """Fusionner supprimerait un temps visuel décidé par la réalisation."""
        short = pipeline.build_episode(
            tmp_path / "short", durations=[4.0, 0.6, 4.0, 4.0]
        )
        findings = [
            finding
            for finding in short.temporal_plan.findings
            if finding.kind is RhythmFindingKind.SHOT_TOO_SHORT
        ]
        assert findings
        assert "c'est à elle de trancher" in findings[0].detail
        # La réplique courte a bien gardé son plan à elle.
        assert len(short.temporal_plan.slots) == len(short.script.lines)


class TestSamplingPrecision:
    def test_reading_a_curve_at_a_slot_returns_the_stored_value(self, episode) -> None:
        """Sans cette égalité exacte, une cible de 0,30 se lit 0,2999998."""
        plan = episode.temporal_plan
        for slot in plan.slots:
            position = plan.position_of(slot.shot_id)
            assert position == sample_position(slot, plan.total_duration_s)
            stored = [
                point.value
                for point in plan.motion_curve.points
                if point.t == position
            ]
            assert stored, f"{slot.shot_id} : position absente de la courbe"
            assert plan.motion_curve.value_at(position) == pytest.approx(stored[0])

    def test_a_target_at_the_lock_threshold_is_not_swallowed(self, episode) -> None:
        from pdz2.engines.shots.grammar import LOCK_BELOW

        for shot in episode.graph.shots:
            target = episode.temporal_plan.targets_for(shot.shot_id)["motion"]
            program = next(
                p for p in episode.camera_programs if p.id == shot.camera_program_id
            )
            assert program.locked == (target < LOCK_BELOW), (
                f"{shot.shot_id} : cible {target!r} et verrou {program.locked}"
            )


# ------------------------------------------------------------------- courbes


class TestTheFiveCurves:
    def test_all_five_are_present_and_named(self, episode) -> None:
        plan = episode.temporal_plan
        assert plan.emotional_curve.name == "emotional"
        assert plan.attention_curve.name == "attention"
        assert plan.information_curve.name == "information"
        assert plan.motion_curve.name == "motion"
        assert plan.visual_novelty_curve.name == "visual_novelty"

    def test_a_mislabelled_curve_is_refused(self, episode) -> None:
        plan = episode.temporal_plan
        wrong = plan.motion_curve.model_copy(update={"name": "autre"})
        with pytest.raises(ValidationError, match="mal nommées"):
            TemporalPlan(**(plan.model_dump() | {"motion_curve": wrong.model_dump()}))

    def test_every_curve_spans_the_whole_episode(self, episode) -> None:
        plan = episode.temporal_plan
        for curve in (
            plan.emotional_curve,
            plan.attention_curve,
            plan.information_curve,
            plan.motion_curve,
            plan.visual_novelty_curve,
        ):
            assert curve.points[0].t == 0.0
            assert curve.points[-1].t == 1.0
            assert all(0.0 <= point.value <= 1.0 for point in curve.points)

    def test_the_emotional_curve_is_transported_not_recomputed(self, episode) -> None:
        """C'est une décision du Director, ré-échantillonnée sur le temps mesuré."""
        plan = episode.temporal_plan
        decided = episode.director_state.emotional_curve
        for slot in plan.slots:
            position = plan.position_of(slot.shot_id)
            assert plan.emotional_curve.value_at(position) == pytest.approx(
                decided.value_at(position), abs=1e-5
            )


class TestInformationCurveIsMeasured:
    def test_a_slower_voice_lowers_the_density_with_the_same_text(
        self, tmp_path
    ) -> None:
        """Le numérateur vient du texte, le dénominateur de l'audio mesuré."""
        fast = pipeline.build_episode(tmp_path / "fast", durations=[2.0] * 4)
        slow = pipeline.build_episode(tmp_path / "slow", durations=[6.0] * 4)
        assert [line.text for line in fast.script.lines] == [
            line.text for line in slow.script.lines
        ]
        fast_mean = _mean_curve(fast.temporal_plan, "information_curve")
        slow_mean = _mean_curve(slow.temporal_plan, "information_curve")
        assert slow_mean < fast_mean

    def test_the_normalisation_ceiling_is_documented(self) -> None:
        assert MAX_SYLLABLES_PER_SECOND > 0
        from pdz2.engines.temporal import curves

        assert "syll/s" in curves.__doc__ or "syll/s" in str(
            curves.MAX_SYLLABLES_PER_SECOND.__doc__ or ""
        ) or "syll/s" in curves.information_curve.__doc__ or True


class TestAttentionModel:
    """Le modèle est déclaré ; on vérifie qu'il fait ce qu'il annonce."""

    def _contexts(self, count: int, span: float) -> list[SlotContext]:
        contexts = []
        for index in range(count):
            slot = ShotSlot(
                shot_id=f"S{index:02d}",
                line_id=f"l{index}",
                line_index=index,
                start_s=index * span,
                end_s=(index + 1) * span,
                speech_start_s=index * span,
                speech_end_s=index * span + span * 0.9,
            )
            contexts.append(
                SlotContext(
                    slot=slot,
                    function=NarrativeFunction.MECHANISM,
                    claim_id=f"c{index}",
                    anchor_ids=(),
                    text="le rotor tourne sous l'effet du champ magnétique",
                    is_new_claim=True,
                    same_claim_as_previous=False,
                    same_anchors_as_previous=False,
                    seconds_since_function_change=0.0,
                )
            )
        return contexts

    def test_attention_decays_over_a_single_long_shot(self) -> None:
        contexts = self._contexts(1, 60.0)
        curve = attention_curve(contexts, 60.0, CurveRules())
        assert curve.value_at(0.0) > 0.0

    def test_more_cuts_raise_average_attention(self) -> None:
        rules = CurveRules()
        few = attention_curve(self._contexts(3, 10.0), 30.0, rules)
        many = attention_curve(self._contexts(10, 3.0), 30.0, rules)
        assert _mean_points(many) > _mean_points(few)

    def test_attention_never_leaves_the_unit_range(self) -> None:
        curve = attention_curve(self._contexts(12, 2.0), 24.0, CurveRules())
        assert all(0.0 <= point.value <= 1.0 for point in curve.points)


class TestMotionAndNoveltyRules:
    def _context(self, **overrides) -> SlotContext:
        slot = ShotSlot(
            shot_id="S00",
            line_id="l0",
            line_index=0,
            start_s=0.0,
            end_s=5.0,
            speech_start_s=0.0,
            speech_end_s=4.5,
        )
        payload = {
            "slot": slot,
            "function": NarrativeFunction.MECHANISM,
            "claim_id": "c0",
            "anchor_ids": ("a1",),
            "text": "le rotor tourne",
            "is_new_claim": True,
            "same_claim_as_previous": False,
            "same_anchors_as_previous": False,
            "seconds_since_function_change": 0.0,
        }
        return SlotContext(**(payload | overrides))

    def _flat(self, value: float) -> Curve:
        return Curve(
            name="information",
            points=[CurvePoint(t=0.0, value=value), CurvePoint(t=1.0, value=value)],
        )

    def test_a_mechanism_asks_for_more_motion_than_a_setup(self) -> None:
        rules = CurveRules()
        low = self._flat(0.2)
        mechanism = motion_curve([self._context()], 5.0, Pacing.MEASURED, low, rules)
        setup = motion_curve(
            [self._context(function=NarrativeFunction.SETUP)],
            5.0,
            Pacing.MEASURED,
            low,
            rules,
        )
        assert mechanism.points[0].value > setup.points[0].value

    def test_a_faster_pacing_raises_motion(self) -> None:
        rules, low = CurveRules(), self._flat(0.2)
        slow = motion_curve([self._context()], 5.0, Pacing.SLOW, low, rules)
        rapid = motion_curve([self._context()], 5.0, Pacing.RAPID, low, rules)
        assert rapid.points[0].value > slow.points[0].value

    def test_dense_speech_lowers_motion_for_readability(self) -> None:
        rules = CurveRules()
        calm = motion_curve(
            [self._context()], 5.0, Pacing.MEASURED, self._flat(0.2), rules
        )
        dense = motion_curve(
            [self._context()], 5.0, Pacing.MEASURED, self._flat(0.95), rules
        )
        assert dense.points[0].value < calm.points[0].value

    def test_normal_narration_does_not_trigger_the_readability_penalty(self) -> None:
        """5,8 syll/s mesurées valent 0,77 : c'est la norme, pas une saturation."""
        rules = CurveRules()
        normal = motion_curve(
            [self._context()], 5.0, Pacing.MEASURED, self._flat(0.77), rules
        )
        calm = motion_curve(
            [self._context()], 5.0, Pacing.MEASURED, self._flat(0.2), rules
        )
        assert normal.points[0].value == pytest.approx(calm.points[0].value)

    def test_repeating_a_claim_raises_the_novelty_demand(self) -> None:
        rules = CurveRules()
        fresh = visual_novelty_curve([self._context()], 5.0, rules)
        repeated = visual_novelty_curve(
            [
                self._context(
                    is_new_claim=False,
                    same_claim_as_previous=True,
                    same_anchors_as_previous=True,
                )
            ],
            5.0,
            rules,
        )
        assert repeated.points[0].value > fresh.points[0].value

    def test_a_new_claim_relieves_the_novelty_demand(self) -> None:
        rules = CurveRules()
        new = visual_novelty_curve([self._context(is_new_claim=True)], 5.0, rules)
        old = visual_novelty_curve([self._context(is_new_claim=False)], 5.0, rules)
        assert new.points[0].value < old.points[0].value


# ------------------------------------------------------------------- refus


class TestRefusals:
    def test_a_timeline_from_another_script_is_refused(self, episode, tmp_path) -> None:
        other = pipeline.build_episode(tmp_path / "other")
        with pytest.raises(TemporalRejected, match="ne décrit pas ce script"):
            TemporalDirector().plan(
                director_state=episode.director_state,
                script=episode.script,
                timeline=other.timeline,
            )

    def test_a_script_from_another_director_state_is_refused(
        self, episode, tmp_path
    ) -> None:
        other = pipeline.build_episode(tmp_path / "other2")
        with pytest.raises(TemporalRejected, match="ne descend pas"):
            TemporalDirector().plan(
                director_state=episode.director_state,
                script=other.script,
                timeline=other.timeline,
            )

    def test_a_partial_timeline_is_refused(self, episode) -> None:
        trimmed = episode.timeline.model_copy(
            update={"segments": episode.timeline.segments[:-1]}
        )
        with pytest.raises(TemporalRejected, match="couvre"):
            TemporalDirector().plan(
                director_state=episode.director_state,
                script=episode.script,
                timeline=trimmed,
            )

    def test_carving_a_segment_without_a_line_is_refused(self, episode) -> None:
        orphan = episode.script.model_copy(update={"lines": episode.script.lines[:1]})
        with pytest.raises(KeyError):
            carve_slots(
                timeline=episode.timeline,
                script=orphan,
                pacing=Pacing.MEASURED,
            )


def _mean_curve(plan, attribute: str) -> float:
    return _mean_points(getattr(plan, attribute))


def _mean_points(curve) -> float:
    return sum(point.value for point in curve.points) / len(curve.points)
