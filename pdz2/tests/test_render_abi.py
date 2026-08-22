"""ABI de rendu : aucune dégradation silencieuse, aucun plan hors budget."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pdz2.contracts import (
    ArtifactKind,
    CameraMove,
    Degradation,
    DegradationSeverity,
    ExecutionPlan,
    ExecutionStep,
    ExecutionStepKind,
    RenderArtifact,
    RenderStrategy,
    Resolution,
)
from pdz2.tests import factories

SHA = "0" * 64


class TestRequestedSpec:
    def test_a_banned_strategy_cannot_be_preferred(self) -> None:
        with pytest.raises(ValidationError, match="génération vidéo IA est interdite"):
            factories.render_spec_requested(
                allow_ai_video=False,
                preferred_strategy=RenderStrategy.DIRECT_I2V,
            )

    def test_a_local_strategy_is_allowed_without_ai_video(self) -> None:
        spec = factories.render_spec_requested(
            allow_ai_video=False,
            preferred_strategy=RenderStrategy.PARALLAX_2_5D,
        )
        assert spec.preferred_strategy is RenderStrategy.PARALLAX_2_5D

    def test_echo_captures_what_was_asked(self) -> None:
        spec = factories.render_spec_requested()
        echo = spec.echo()
        assert echo.camera is spec.requested_camera
        assert echo.duration_s == spec.duration_s
        assert echo.fps == spec.fps


class TestNoSilentDegradation:
    def test_camera_change_without_declaration_is_refused(self) -> None:
        requested = factories.render_spec_requested()  # ORBIT
        with pytest.raises(ValidationError, match="dégradation silencieuse"):
            factories.render_spec_executable(
                requested, execution_camera=CameraMove.LOCK
            )

    def test_the_specification_example_is_expressible(self) -> None:
        """requested ORBIT, provider NONE → dégradation enregistrée."""
        requested = factories.render_spec_requested(
            requested_camera=CameraMove.ORBIT,
            preferred_strategy=RenderStrategy.DIRECT_I2V,
        )
        executable = factories.render_spec_executable(
            requested,
            strategy=RenderStrategy.PARALLAX_2_5D,
            execution_camera=CameraMove.LOCK,
            degradations=[
                factories.camera_degradation(),
                Degradation(
                    field="strategy",
                    requested="direct_i2v",
                    executed="parallax_2_5d",
                    reason="provider does not expose required camera control",
                    description="camera orbit replaced by deterministic 2.5D approximation",
                    severity=DegradationSeverity.NARRATIVE,
                ),
            ],
        )
        assert executable.execution_camera is CameraMove.LOCK
        assert len(executable.narrative_degradations) == 1
        assert executable.degradations[0].reason

    def test_duration_change_must_be_declared(self) -> None:
        requested = factories.render_spec_requested()
        with pytest.raises(ValidationError, match="duration_s"):
            factories.render_spec_executable(requested, duration_s=4.0)

    def test_resolution_change_must_be_declared(self) -> None:
        requested = factories.render_spec_requested()
        with pytest.raises(ValidationError, match="resolution"):
            factories.render_spec_executable(
                requested, resolution=Resolution(width=720, height=1280)
            )

    def test_fps_change_must_be_declared(self) -> None:
        requested = factories.render_spec_requested()
        with pytest.raises(ValidationError, match="fps"):
            factories.render_spec_executable(requested, fps=12)

    def test_declaring_a_degradation_on_a_conforming_field_is_refused(self) -> None:
        requested = factories.render_spec_requested()
        with pytest.raises(ValidationError, match="champ conforme"):
            factories.render_spec_executable(
                requested, degradations=[factories.camera_degradation()]
            )

    def test_free_form_degradation_fields_are_allowed(self) -> None:
        requested = factories.render_spec_requested()
        executable = factories.render_spec_executable(
            requested,
            degradations=[
                Degradation(
                    field="identity_lock",
                    requested="strict",
                    executed="best effort",
                    reason="provider exposes no reference image slot",
                    description="anchor reinforced through prompt only",
                    severity=DegradationSeverity.PERCEPTUAL,
                )
            ],
        )
        assert executable.degradations[0].field == "identity_lock"


class TestProviderCoupling:
    def test_a_deterministic_strategy_carries_no_provider(self) -> None:
        with pytest.raises(ValidationError, match="stratégie déterministe"):
            factories.render_spec_executable(provider="un-fournisseur")

    def test_an_ai_strategy_without_provider_is_refused(self) -> None:
        requested = factories.render_spec_requested(
            requested_camera=CameraMove.LOCK,
            preferred_strategy=RenderStrategy.DIRECT_I2V,
        )
        with pytest.raises(ValidationError, match="sans fournisseur"):
            factories.render_spec_executable(
                requested,
                strategy=RenderStrategy.DIRECT_I2V,
                execution_camera=CameraMove.LOCK,
                provider=None,
            )

    def test_an_ai_strategy_with_a_provider_is_accepted(self) -> None:
        requested = factories.render_spec_requested(
            requested_camera=CameraMove.LOCK,
            preferred_strategy=RenderStrategy.DIRECT_I2V,
        )
        executable = factories.render_spec_executable(
            requested,
            strategy=RenderStrategy.DIRECT_I2V,
            execution_camera=CameraMove.LOCK,
            provider="adaptateur-exemple",
            model="modele-exemple",
        )
        assert executable.provider == "adaptateur-exemple"


class TestExecutionPlan:
    def _plan(self, **overrides) -> ExecutionPlan:
        steps = [
            ExecutionStep(
                step_id="img-1",
                kind=ExecutionStepKind.GENERATE_IMAGE,
                estimated_cost_usd=0.01,
            ),
            ExecutionStep(
                step_id="vid-1",
                kind=ExecutionStepKind.GENERATE_VIDEO,
                depends_on=["img-1"],
                estimated_cost_usd=0.20,
            ),
        ]
        payload = {
            "episode_id": "ep-1",
            "steps": steps,
            "total_estimated_cost_usd": 0.21,
        }
        return ExecutionPlan(**(payload | overrides))

    def test_valid_plan_is_accepted(self) -> None:
        plan = self._plan()
        assert plan.topological_order() == ["img-1", "vid-1"]

    def test_total_must_match_the_steps(self) -> None:
        with pytest.raises(ValidationError, match="coût total déclaré"):
            self._plan(total_estimated_cost_usd=1.0)

    def test_budget_cap_is_enforced(self) -> None:
        with pytest.raises(ValidationError, match="au-dessus du plafond"):
            self._plan(budget_cap_usd=0.10)

    def test_cyclic_dependencies_are_refused(self) -> None:
        steps = [
            ExecutionStep(step_id="a", kind=ExecutionStepKind.OBSERVE, depends_on=["b"]),
            ExecutionStep(step_id="b", kind=ExecutionStepKind.OBSERVE, depends_on=["a"]),
        ]
        with pytest.raises(ValidationError, match="cycliques"):
            self._plan(steps=steps, total_estimated_cost_usd=0.0)

    def test_unknown_dependency_is_refused(self) -> None:
        steps = [
            ExecutionStep(step_id="a", kind=ExecutionStepKind.OBSERVE, depends_on=["z"]),
        ]
        with pytest.raises(ValidationError, match="dépendances inconnues"):
            self._plan(steps=steps, total_estimated_cost_usd=0.0)

    def test_self_dependency_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="dépend d'elle-même"):
            ExecutionStep(step_id="a", kind=ExecutionStepKind.OBSERVE, depends_on=["a"])


class TestRenderArtifact:
    def test_a_video_declares_duration_fps_and_resolution(self) -> None:
        with pytest.raises(ValidationError, match="artefact vidéo"):
            RenderArtifact(
                kind=ArtifactKind.VIDEO,
                path="renders/s01.mp4",
                sha256=SHA,
                size_bytes=1234,
            )

    def test_an_image_has_no_duration(self) -> None:
        with pytest.raises(ValidationError, match="ni durée ni fps"):
            RenderArtifact(
                kind=ArtifactKind.IMAGE,
                path="assets/s01.png",
                sha256=SHA,
                size_bytes=10,
                resolution=Resolution(width=1080, height=1920),
                duration_s=2.0,
            )

    def test_a_valid_video_artifact_is_accepted(self) -> None:
        artifact = RenderArtifact(
            kind=ArtifactKind.VIDEO,
            path="renders/s01.mp4",
            sha256=SHA,
            size_bytes=999,
            duration_s=6.0,
            fps=24,
            resolution=Resolution(width=1080, height=1920),
            actual_cost_usd=0.18,
        )
        assert artifact.attempt == 1

    def test_checksum_length_is_enforced(self) -> None:
        with pytest.raises(ValidationError):
            RenderArtifact(
                kind=ArtifactKind.TEXT, path="x.txt", sha256="abc", size_bytes=1
            )
