"""Shot Graph et contraintes de plan."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pdz2.contracts import (
    AudioEvent,
    AudioEventKind,
    NarrativeFunction,
    RenderConstraints,
    Resolution,
    ScreenPosition,
    ShotEdge,
    ShotGraph,
    TextOverlay,
    Transition,
    TransitionKind,
)
from pdz2.tests import factories


class TestShotSpec:
    def test_a_mechanism_shot_needs_a_claim(self) -> None:
        with pytest.raises(ValidationError, match="sans claim_id"):
            factories.shot_spec(claim_id=None)

    def test_a_mechanism_shot_needs_visual_evidence(self) -> None:
        with pytest.raises(ValidationError, match="evidence_required"):
            factories.shot_spec(evidence_required=None)

    def test_a_hook_shot_may_stand_alone(self) -> None:
        shot = factories.shot_spec(
            narrative_function=NarrativeFunction.HOOK,
            claim_id=None,
            evidence_required=None,
        )
        assert shot.claim_id is None

    def test_audio_event_must_fit_inside_the_shot(self) -> None:
        with pytest.raises(ValidationError, match="hors du plan"):
            factories.shot_spec(
                duration_s=3.0,
                audio_events=[
                    AudioEvent(kind=AudioEventKind.WHOOSH, at_s=2.5, duration_s=2.0)
                ],
            )

    def test_overlay_must_fit_inside_the_shot(self) -> None:
        with pytest.raises(ValidationError, match="incrustation hors du plan"):
            factories.shot_spec(
                duration_s=3.0,
                text_overlay=TextOverlay(
                    text="couple immédiat",
                    at_s=2.0,
                    duration_s=3.0,
                    position=ScreenPosition.LOWER_THIRD,
                ),
            )

    def test_transitions_cannot_swallow_the_shot(self) -> None:
        with pytest.raises(ValidationError, match="plus longues"):
            factories.shot_spec(
                duration_s=1.0,
                transition_in=Transition(kind=TransitionKind.DISSOLVE, duration_s=0.6),
                transition_out=Transition(kind=TransitionKind.DISSOLVE, duration_s=0.6),
            )

    def test_a_cut_is_instantaneous(self) -> None:
        with pytest.raises(ValidationError, match="coupe franche"):
            Transition(kind=TransitionKind.CUT, duration_s=0.4)

    def test_a_dissolve_needs_a_duration(self) -> None:
        with pytest.raises(ValidationError, match="exige une durée"):
            Transition(kind=TransitionKind.DISSOLVE, duration_s=0.0)


class TestRenderConstraints:
    def test_deterministic_only_excludes_ai_video(self) -> None:
        with pytest.raises(ValidationError, match="deterministic_only"):
            RenderConstraints(deterministic_only=True, allow_ai_video=True)

    def test_deterministic_only_without_ai_video_is_accepted(self) -> None:
        constraints = RenderConstraints(deterministic_only=True, allow_ai_video=False)
        assert constraints.deterministic_only

    def test_minimum_resolution_is_expressible(self) -> None:
        constraints = RenderConstraints(min_resolution=Resolution(width=720, height=1280))
        assert constraints.min_resolution.height == 1280


class TestShotGraph:
    def _graph(self, **overrides) -> ShotGraph:
        shots = [
            factories.shot_spec("S01", duration_s=4.0),
            factories.shot_spec("S02", duration_s=6.0, continuity_dependencies=["a1"]),
        ]
        payload = {
            "director_state_id": "director_state-x",
            "voice_timeline_id": "voice_timeline-x",
            "visual_bible_id": "visual_bible-x",
            "shots": shots,
            "edges": [
                ShotEdge(from_shot_id="S01", to_shot_id="S02", carried_anchor_ids=["a1"])
            ],
            "total_duration_s": 10.0,
        }
        return ShotGraph(**(payload | overrides))

    def test_valid_graph_is_accepted(self) -> None:
        graph = self._graph()
        assert graph.shot("S02").duration_s == 6.0

    def test_duplicate_shot_id_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="shot_id en double"):
            self._graph(
                shots=[
                    factories.shot_spec("S01", duration_s=4.0),
                    factories.shot_spec("S01", duration_s=6.0),
                ],
                edges=[],
            )

    def test_durations_must_add_up(self) -> None:
        with pytest.raises(ValidationError, match="somme des plans"):
            self._graph(total_duration_s=30.0)

    def test_edge_to_unknown_shot_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="plan inconnu"):
            self._graph(
                edges=[ShotEdge(from_shot_id="S01", to_shot_id="S99")]
            )

    def test_carried_anchor_must_be_declared_downstream(self) -> None:
        with pytest.raises(ValidationError, match="continuité rompue"):
            self._graph(
                shots=[
                    factories.shot_spec("S01", duration_s=4.0),
                    factories.shot_spec("S02", duration_s=6.0),
                ],
                edges=[
                    ShotEdge(
                        from_shot_id="S01", to_shot_id="S02", carried_anchor_ids=["a1"]
                    )
                ],
            )

    def test_unknown_shot_lookup_raises(self) -> None:
        with pytest.raises(KeyError):
            self._graph().shot("S99")
