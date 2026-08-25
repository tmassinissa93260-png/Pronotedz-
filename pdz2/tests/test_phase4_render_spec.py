"""Phase 4 : mouvement, images, demandes de rendu, validation statique."""

from __future__ import annotations

import pytest

from pdz2.contracts.enums import Framing, Severity
from pdz2.contracts.motion import CameraMove
from pdz2.contracts.render import (
    AI_VIDEO_STRATEGIES,
    DETERMINISTIC_STRATEGIES,
    RenderStrategy,
)
from pdz2.contracts.validation import ValidationReport, ValidationRule
from pdz2.engines.imagery import RESOLUTIONS, ImageSpecCompiler, layers_for
from pdz2.engines.motion import MotionCompiler, MotionRejected
from pdz2.engines.renderspec import RenderSpecCompiler, RenderSpecRejected
from pdz2.engines.validation import StaticValidator
from pdz2.tests import pipeline


@pytest.fixture(scope="module")
def episode(tmp_path_factory):
    return pipeline.build_episode(
        tmp_path_factory.mktemp("phase4"), through_render_spec=True
    )


def _validate(episode, **overrides):
    payload = {
        "episode_id": "ep",
        "shot_graph": episode.graph,
        "requested": episode.render_specs,
        "motion_programs": episode.motion_programs,
        "camera_programs": episode.camera_programs,
        "image_specs": episode.image_specs,
        "request": episode.request,
    }
    validator = overrides.pop("validator", StaticValidator())
    return validator.validate(**(payload | overrides)).report


class TestMotionProgram:
    def test_one_program_per_shot(self, episode) -> None:
        assert len(episode.motion_programs) == len(episode.graph.shots)
        assert {p.shot_id for p in episode.motion_programs} == {
            s.shot_id for s in episode.graph.shots
        }

    def test_it_preserves_the_fixed_identity_traits(self, episode) -> None:
        anchors = {a.id: a for a in episode.director_state.continuity_anchors}
        for program in episode.motion_programs:
            shot = episode.graph.shot(program.shot_id)
            for anchor_id in shot.continuity_dependencies:
                anchor = anchors[anchor_id]
                for attribute in anchor.fixed_attributes():
                    assert any(
                        attribute.value in entry for entry in program.must_preserve
                    )

    def test_the_three_sets_never_overlap(self, episode) -> None:
        for program in episode.motion_programs:
            preserve, change = set(program.must_preserve), set(program.may_change)
            forbid = set(program.forbidden)
            assert not preserve & change
            assert not preserve & forbid
            assert not change & forbid

    def test_readability_is_the_complement_of_density(self, episode) -> None:
        for program in episode.motion_programs:
            density = episode.temporal_plan.targets_for(program.shot_id)["information"]
            assert program.perceptual_target.readability == pytest.approx(
                1.0 - density, abs=1e-3
            )

    def test_the_dominant_trajectory_follows_the_camera_when_it_moves(
        self, episode
    ) -> None:
        cameras = {c.id: c for c in episode.camera_programs}
        for program in episode.motion_programs:
            camera = cameras[program.camera_program_id]
            if not camera.locked:
                assert program.trajectory.primitive is camera.trajectory.primitive

    def test_a_missing_camera_is_refused(self, episode) -> None:
        with pytest.raises(MotionRejected, match="caméra"):
            MotionCompiler().compile(
                shot_graph=episode.graph,
                temporal_plan=episode.temporal_plan,
                camera_programs=[],
                director_state=episode.director_state,
                visual_bible=episode.bible,
            )

    def test_the_program_descends_from_its_shot(self, episode) -> None:
        parents = {shot.id for shot in episode.graph.shots}
        assert all(p.parent_id in parents for p in episode.motion_programs)


class TestImageSpec:
    def test_the_resolution_matches_the_requested_format(self, episode) -> None:
        expected = RESOLUTIONS[episode.request.aspect_ratio]
        for spec in episode.image_specs:
            assert spec.resolution == expected
            assert spec.resolution.matches(spec.aspect_ratio)

    def test_the_intent_only_quotes_decided_material(self, episode) -> None:
        for spec in episode.image_specs:
            assert spec.subject in spec.intent
            assert episode.bible.style in spec.intent
            assert episode.bible.lighting in spec.intent

    def test_forbidden_imagery_is_carried_to_every_image(self, episode) -> None:
        for spec in episode.image_specs:
            assert spec.forbidden == episode.bible.forbidden

    def test_a_flat_framing_gets_one_layer_a_wide_one_gets_depth(self) -> None:
        assert len(layers_for(Framing.CUTAWAY_DIAGRAM)) == 1
        assert len(layers_for(Framing.WIDE)) == 4
        assert len(layers_for(Framing.MEDIUM)) == 2

    def test_layers_are_ordered_from_back_to_front(self, episode) -> None:
        for spec in episode.image_specs:
            depths = [layer.depth for layer in spec.layers]
            assert depths == sorted(depths)

    def test_the_seed_is_reproducible_and_shot_specific(self, episode) -> None:
        again = ImageSpecCompiler().compile(
            shot_graph=episode.graph,
            visual_bible=episode.bible,
            director_state=episode.director_state,
            request=episode.request,
        ).specs
        assert [s.seed for s in again] == [s.seed for s in episode.image_specs]
        assert len({s.seed for s in episode.image_specs}) == len(episode.image_specs)

    def test_the_anchors_of_the_shot_reach_the_image(self, episode) -> None:
        for spec in episode.image_specs:
            shot = episode.graph.shot(spec.shot_id)
            assert spec.anchor_ids == shot.continuity_dependencies


class TestRenderSpecRequested:
    def test_it_names_no_provider_and_imposes_no_strategy(self, episode) -> None:
        for spec in episode.render_specs:
            assert spec.preferred_strategy is None
            assert "provider" not in type(spec).model_fields

    def test_the_duration_is_the_shot_duration(self, episode) -> None:
        for spec in episode.render_specs:
            shot = episode.graph.shot(spec.shot_id)
            assert spec.duration_s == pytest.approx(shot.duration_s, abs=1e-6)

    def test_the_camera_matches_the_camera_program(self, episode) -> None:
        cameras = {c.id: c for c in episode.camera_programs}
        for spec in episode.render_specs:
            assert spec.requested_camera is cameras[spec.camera_program_id].move

    def test_a_shot_without_an_image_spec_is_refused(self, episode) -> None:
        with pytest.raises(RenderSpecRejected, match="aucune spécification d'image"):
            RenderSpecCompiler().compile(
                shot_graph=episode.graph,
                motion_programs=episode.motion_programs,
                camera_programs=episode.camera_programs,
                image_specs=[],
                request=episode.request,
            )

    def test_a_shot_without_a_motion_program_is_refused(self, episode) -> None:
        with pytest.raises(RenderSpecRejected, match="programme de mouvement"):
            RenderSpecCompiler().compile(
                shot_graph=episode.graph,
                motion_programs=[],
                camera_programs=episode.camera_programs,
                image_specs=episode.image_specs,
                request=episode.request,
            )


class TestStaticValidator:
    def test_a_coherent_episode_is_accepted(self, episode) -> None:
        report = _validate(episode)
        assert report.accepted
        assert not report.blocking

    def test_it_says_when_no_ai_provider_is_reachable(self, episode) -> None:
        report = _validate(episode)
        minor = [
            issue
            for issue in report.issues
            if issue.rule is ValidationRule.PROVIDER_CAPABILITY
        ]
        assert minor
        assert all(issue.severity is Severity.MINOR for issue in minor)

    def test_a_missing_shot_is_blocking(self, episode) -> None:
        report = _validate(episode, requested=episode.render_specs[:-1])
        assert not report.accepted
        assert any(i.rule is ValidationRule.REQUIRED_FIELD for i in report.blocking)

    def test_a_duplicated_request_is_blocking(self, episode) -> None:
        report = _validate(
            episode, requested=[*episode.render_specs, episode.render_specs[0]]
        )
        assert not report.accepted
        assert any(
            i.rule is ValidationRule.LOGICAL_CONTRADICTION for i in report.blocking
        )

    def test_a_locked_camera_with_a_pan_is_blocking(self, episode) -> None:
        """L'exemple exact du §13."""
        spec = episode.render_specs[0]
        tampered = spec.model_copy(update={"requested_camera": CameraMove.PAN})
        report = _validate(
            episode, requested=[tampered, *episode.render_specs[1:]]
        )
        assert not report.accepted
        assert any(i.rule is ValidationRule.CAMERA_CONSTRAINT for i in report.blocking)

    def test_a_duration_beyond_the_ceiling_is_blocking(self, episode) -> None:
        spec = episode.render_specs[0].model_copy(update={"duration_s": 99.0})
        report = _validate(episode, requested=[spec, *episode.render_specs[1:]])
        assert any(
            i.rule is ValidationRule.DURATION_FEASIBILITY for i in report.blocking
        )

    def test_an_odd_resolution_is_blocking(self, episode) -> None:
        from pdz2.contracts.common import Resolution

        spec = episode.render_specs[0].model_copy(
            update={"resolution": Resolution(width=1081, height=1920)}
        )
        report = _validate(episode, requested=[spec, *episode.render_specs[1:]])
        assert any(
            i.rule is ValidationRule.RESOLUTION_FORMAT for i in report.blocking
        )

    def test_an_unavailable_preferred_strategy_is_blocking(self, episode) -> None:
        spec = episode.render_specs[0].model_copy(
            update={"preferred_strategy": RenderStrategy.DIRECT_I2V}
        )
        report = _validate(episode, requested=[spec, *episode.render_specs[1:]])
        assert any(
            i.rule is ValidationRule.PROVIDER_CAPABILITY for i in report.blocking
        )

    def test_an_available_strategy_is_accepted(self, episode) -> None:
        spec = episode.render_specs[0].model_copy(
            update={"preferred_strategy": RenderStrategy.KEN_BURNS}
        )
        report = _validate(episode, requested=[spec, *episode.render_specs[1:]])
        assert report.accepted

    def test_without_any_local_fallback_everything_is_blocking(self, episode) -> None:
        """Livraison garantie : sans repli local, on refuse d'avancer."""
        validator = StaticValidator(available_strategies=frozenset())
        report = _validate(episode, validator=validator)
        assert not report.accepted
        assert any(
            i.rule is ValidationRule.FALLBACK_AVAILABILITY for i in report.blocking
        )

    def test_a_budget_smaller_than_the_sum_of_caps_is_blocking(self, episode) -> None:
        request = episode.request.model_copy(update={"budget_cap_usd": 0.001})
        specs = [s.model_copy(update={"max_cost_usd": 1.0}) for s in episode.render_specs]
        report = _validate(episode, requested=specs, request=request)
        assert any(i.rule is ValidationRule.BUDGET for i in report.blocking)

    def test_a_shot_losing_its_anchor_image_is_blocking(self, episode) -> None:
        anchored = [
            spec
            for spec in episode.image_specs
            if spec.anchor_ids
        ]
        if not anchored:
            pytest.skip("aucun plan ancré dans cet épisode")
        stripped = [
            spec.model_copy(update={"anchor_ids": []})
            if spec.id == anchored[0].id
            else spec
            for spec in episode.image_specs
        ]
        report = _validate(episode, image_specs=stripped)
        assert any(i.rule is ValidationRule.CONTINUITY for i in report.blocking)

    def test_every_blocking_issue_says_how_to_fix_it(self, episode) -> None:
        report = _validate(episode, requested=episode.render_specs[:-1])
        assert all(issue.remedy.strip() for issue in report.blocking)

    def test_a_report_cannot_accept_with_a_blocking_issue(self, episode) -> None:
        from pydantic import ValidationError

        report = _validate(episode, requested=episode.render_specs[:-1])
        with pytest.raises(ValidationError, match="malgré"):
            ValidationReport(**(report.model_dump() | {"accepted": True}))


class TestStrategySets:
    def test_deterministic_and_ai_strategies_do_not_overlap(self) -> None:
        assert not DETERMINISTIC_STRATEGIES & AI_VIDEO_STRATEGIES

    def test_the_default_validator_only_trusts_local_strategies(self) -> None:
        assert StaticValidator().available_strategies == DETERMINISTIC_STRATEGIES
