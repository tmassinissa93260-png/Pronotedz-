"""Phase 6 : port fournisseur vidéo et routeur de stratégie."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pdz2.contracts.capability import CapabilityState, ProviderCapability
from pdz2.contracts.capacity import CapabilityMatrix
from pdz2.contracts.motion import CameraMove
from pdz2.contracts.render import (
    AI_VIDEO_STRATEGIES,
    DegradationSeverity,
    RenderStrategy,
)
from pdz2.engines.routing import (
    MOTION_COMPLEXITY_ORDER,
    RenderRouter,
    RoutingRejected,
)
from pdz2.providers import NO_VIDEO_PROVIDERS, VideoCapability, VideoProvider
from pdz2.tests import pipeline


@pytest.fixture(scope="module")
def episode(tmp_path_factory):
    return pipeline.build_episode(
        tmp_path_factory.mktemp("phase6"), through_render_spec=True
    )


def _route(episode, **overrides):
    router = overrides.pop("router", RenderRouter())
    payload = {
        "episode_id": "ep",
        "requested": episode.render_specs,
        "motion_programs": episode.motion_programs,
        "image_specs": episode.image_specs,
    }
    return router.route(**(payload | overrides))


def _reachable_capability(**overrides) -> VideoCapability:
    payload = {
        "capability": ProviderCapability(
            provider="adaptateur-de-test",
            state=CapabilityState.AVAILABLE,
            measured_at=datetime.now(UTC),
            measurement_method="sonde de test",
            detail="joignable",
        ),
        "strategies": [RenderStrategy.DIRECT_I2V],
        "camera_moves": [CameraMove.ORBIT],
        "supports_image_to_video": True,
    }
    return VideoCapability(**(payload | overrides))


class TestTheProviderPortIsHonest:
    def test_no_video_adapter_is_implemented(self) -> None:
        assert NO_VIDEO_PROVIDERS == ()

    def test_the_protocol_exists_and_is_checkable(self) -> None:
        class Stub:
            name = "stub"

            def get_capabilities(self):  # pragma: no cover - forme seule
                ...

            def generate(self, job):  # pragma: no cover - forme seule
                ...

        assert isinstance(Stub(), VideoProvider)

    def test_an_unmeasured_capability_is_unknown_and_unusable(self) -> None:
        capability = VideoCapability(
            capability=ProviderCapability.unknown("jamais-sondé")
        )
        assert capability.capability.state is CapabilityState.UNKNOWN
        assert not capability.usable


class TestRoutingWithoutAnyProvider:
    def test_every_shot_gets_a_local_strategy(self, episode) -> None:
        outcome = _route(episode)
        assert len(outcome.executables) == len(episode.render_specs)
        for executable in outcome.executables:
            assert executable.strategy not in AI_VIDEO_STRATEGIES
            assert executable.provider is None

    def test_the_unreachable_provider_is_declared_shot_by_shot(self, episode) -> None:
        outcome = _route(episode)
        for executable in outcome.executables:
            fields = {d.field for d in executable.degradations}
            assert "provider_availability" in fields
        reasons = {
            d.reason for d in outcome.degradations if d.field == "provider_availability"
        }
        assert any("aucun adaptateur n'est implémenté" in reason for reason in reasons)

    def test_no_degradation_is_left_undeclared(self, episode) -> None:
        """Le contrat le refuserait : on vérifie qu'il est bien sollicité."""
        outcome = _route(episode)
        for executable in outcome.executables:
            if executable.execution_camera is not executable.requested.camera:
                assert any(d.field == "camera" for d in executable.degradations)

    def test_forbidding_ai_video_removes_the_provider_note(self, episode) -> None:
        specs = [
            spec.model_copy(update={"allow_ai_video": False})
            for spec in episode.render_specs
        ]
        outcome = _route(episode, requested=specs)
        fields = {d.field for d in outcome.degradations}
        assert "provider_availability" not in fields


class TestStrategyChoice:
    def test_low_energy_gets_a_still_or_ken_burns(self, episode) -> None:
        calm = [
            program.model_copy(
                update={
                    "perceptual_target": program.perceptual_target.model_copy(
                        update={"motion_energy": 0.05}
                    )
                }
            )
            for program in episode.motion_programs
        ]
        outcome = _route(episode, motion_programs=calm)
        assert all(
            e.strategy is RenderStrategy.STILL for e in outcome.executables
        )

    def test_high_energy_reaches_the_procedural_end_of_the_scale(
        self, episode
    ) -> None:
        lively = [
            program.model_copy(
                update={
                    "perceptual_target": program.perceptual_target.model_copy(
                        update={"motion_energy": 0.95}
                    )
                }
            )
            for program in episode.motion_programs
        ]
        outcome = _route(episode, motion_programs=lively)
        assert all(
            e.strategy is RenderStrategy.PROCEDURAL for e in outcome.executables
        )

    def test_a_single_layer_forbids_parallax_and_says_so(self, episode) -> None:
        """Un seul calque : le parallaxe n'a rien à décaler, et on le déclare."""
        flat = [
            spec.model_copy(update={"layers": spec.layers[:1]})
            for spec in episode.image_specs
        ]
        mid = [
            program.model_copy(
                update={
                    "perceptual_target": program.perceptual_target.model_copy(
                        update={"motion_energy": 0.55}
                    )
                }
            )
            for program in episode.motion_programs
        ]
        outcome = _route(episode, image_specs=flat, motion_programs=mid)
        assert all(e.strategy is RenderStrategy.KEN_BURNS for e in outcome.executables)
        motion_notes = [d for d in outcome.degradations if d.field == "motion"]
        assert motion_notes
        assert "un seul calque" in motion_notes[0].reason

    def test_a_reachable_provider_unlocks_its_strategies(self, episode) -> None:
        # Un instantané de capacités est requis pour retenir un fournisseur :
        # le contrat refuse un choix qu'on ne peut pas justifier.
        router = RenderRouter(
            video_capabilities=[_reachable_capability()],
            capability_matrix=CapabilityMatrix(),
        )
        lively = [
            program.model_copy(
                update={
                    "perceptual_target": program.perceptual_target.model_copy(
                        update={"motion_energy": 0.95}
                    )
                }
            )
            for program in episode.motion_programs
        ]
        outcome = _route(episode, router=router, motion_programs=lively)
        fields = {d.field for d in outcome.degradations}
        assert "provider_availability" not in fields

    def test_a_provider_without_a_capability_snapshot_is_set_aside(
        self, episode
    ) -> None:
        """Sans instantané, le fournisseur n'est pas retenu — et c'est déclaré."""
        router = RenderRouter(video_capabilities=[_reachable_capability()])
        outcome = _route(episode, router=router)
        assert all(e.provider is None for e in outcome.executables)
        raisons = " ".join(d.reason for d in outcome.degradations)
        assert "instantané de capacités" in raisons

    def test_the_snapshot_identifier_reaches_every_executable(
        self, episode
    ) -> None:
        matrice = CapabilityMatrix()
        outcome = _route(
            episode, router=RenderRouter(capability_matrix=matrice)
        )
        assert all(
            e.capability_snapshot_id == matrice.id for e in outcome.executables
        )

    def test_previous_failures_push_the_shot_to_a_guaranteed_fallback(
        self, episode
    ) -> None:
        shot = episode.render_specs[0].shot_id
        router = RenderRouter(
            previous_failures={shot: set(MOTION_COMPLEXITY_ORDER)}
        )
        outcome = _route(episode, router=router)
        executable = outcome.for_shot(shot)
        assert executable.strategy is RenderStrategy.STILL
        retries = [d for d in executable.degradations if d.field == "retry_strategy"]
        assert retries
        assert retries[0].severity is DegradationSeverity.NARRATIVE

    def test_without_any_strategy_the_router_refuses(self, episode) -> None:
        router = RenderRouter(local_strategies=frozenset())
        specs = [
            spec.model_copy(update={"allow_ai_video": False})
            for spec in episode.render_specs
        ]
        with pytest.raises(RoutingRejected, match="aucune stratégie"):
            _route(episode, router=router, requested=specs)

    def test_a_missing_motion_program_is_refused(self, episode) -> None:
        with pytest.raises(RoutingRejected, match="mouvement introuvable"):
            _route(episode, motion_programs=[])


class TestCameraFallback:
    def test_a_still_shot_cannot_pan(self, episode) -> None:
        calm = [
            program.model_copy(
                update={
                    "perceptual_target": program.perceptual_target.model_copy(
                        update={"motion_energy": 0.02}
                    )
                }
            )
            for program in episode.motion_programs
        ]
        moving = [
            spec.model_copy(update={"requested_camera": CameraMove.PAN})
            for spec in episode.render_specs
        ]
        outcome = _route(episode, motion_programs=calm, requested=moving)
        for executable in outcome.executables:
            assert executable.execution_camera is CameraMove.LOCK
            camera = [d for d in executable.degradations if d.field == "camera"]
            assert camera
            assert "n'expose pas le mouvement" in camera[0].reason

    def test_an_orbit_survives_only_on_the_procedural_strategy(self, episode) -> None:
        lively = [
            program.model_copy(
                update={
                    "perceptual_target": program.perceptual_target.model_copy(
                        update={"motion_energy": 0.95}
                    )
                }
            )
            for program in episode.motion_programs
        ]
        orbiting = [
            spec.model_copy(update={"requested_camera": CameraMove.ORBIT})
            for spec in episode.render_specs
        ]
        outcome = _route(episode, motion_programs=lively, requested=orbiting)
        for executable in outcome.executables:
            assert executable.strategy is RenderStrategy.PROCEDURAL
            assert executable.execution_camera is CameraMove.ORBIT


class TestExecutionPlan:
    def test_the_plan_renders_then_observes_then_assembles(self, episode) -> None:
        outcome = _route(episode)
        order = outcome.plan.topological_order()
        for executable in outcome.executables:
            render = order.index(f"render-{executable.shot_id}")
            observe = order.index(f"observe-{executable.shot_id}")
            assert render < observe < order.index("assemble")

    def test_the_plan_is_acyclic_and_costed(self, episode) -> None:
        outcome = _route(episode)
        assert outcome.plan.total_estimated_cost_usd == pytest.approx(0.0)
        assert len(outcome.plan.steps) == 2 * len(episode.render_specs) + 1

    def test_a_budget_cap_is_carried_into_the_plan(self, episode) -> None:
        outcome = _route(episode, budget_cap_usd=3.0)
        assert outcome.plan.budget_cap_usd == 3.0
