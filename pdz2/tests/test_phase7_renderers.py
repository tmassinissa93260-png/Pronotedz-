"""Phase 7 : les stratégies déterministes produisent de vraies vidéos."""

from __future__ import annotations

import math

import pytest

from pdz2.contracts.common import Vec3
from pdz2.contracts.enums import ArtifactKind
from pdz2.contracts.motion import CameraMove, Easing, MotionPrimitive, Trajectory
from pdz2.contracts.render import RenderStrategy
from pdz2.engines.imagery import ProceduralImageRenderer
from pdz2.engines.routing import RenderRouter
from pdz2.renderers import (
    SUPPORTED_PRIMITIVES,
    DeterministicRenderer,
    RenderFailed,
    ease,
    ffmpeg_capability,
    probe_video,
    sample_trajectory,
)
from pdz2.tests import pipeline

needs_ffmpeg = pytest.mark.skipif(
    not ffmpeg_capability().usable,
    reason="binaire ffmpeg absent : installer le paquet système « ffmpeg »",
)


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    root = tmp_path_factory.mktemp("phase7")
    episode = pipeline.build_episode(
        root, through_render_spec=True, resolution=pipeline.SMALL
    )
    images = ProceduralImageRenderer().render(
        specs=episode.image_specs, visual_bible=episode.bible, into=root / "assets"
    )
    routing = RenderRouter().route(
        episode_id="ep",
        requested=episode.render_specs,
        motion_programs=episode.motion_programs,
        image_specs=episode.image_specs,
    )
    outcome = DeterministicRenderer().render(
        executables=routing.executables,
        motion_programs=episode.motion_programs,
        images=images.images,
        into=root / "renders",
    )
    return episode, routing, images, outcome, root


# ------------------------------------------------- grammaire de mouvement


class TestMotionPathsAreMathematical:
    def test_every_contract_primitive_is_evaluable(self) -> None:
        """Une primitive au contrat sans évaluateur serait une promesse vide."""
        assert set(MotionPrimitive) == set(SUPPORTED_PRIMITIVES)

    def test_a_linear_path_is_linear(self) -> None:
        trajectory = Trajectory(
            primitive=MotionPrimitive.LINEAR,
            control_points=[Vec3(), Vec3(x=1.0)],
            amplitude=1.0,
        )
        assert sample_trajectory(trajectory, 0.0).x == pytest.approx(0.0)
        assert sample_trajectory(trajectory, 0.5).x == pytest.approx(0.5)
        assert sample_trajectory(trajectory, 1.0).x == pytest.approx(1.0)

    def test_a_static_path_never_moves(self) -> None:
        assert sample_trajectory(Trajectory(), 0.5) == Vec3()

    def test_an_orbit_follows_a_circle(self) -> None:
        trajectory = Trajectory(
            primitive=MotionPrimitive.ORBIT, amplitude=360.0, axis=Vec3(y=1.0)
        )
        quarter = sample_trajectory(trajectory, 0.25)
        assert quarter.x == pytest.approx(math.sin(math.pi / 2), abs=1e-6)

    def test_an_oscillation_returns_to_zero(self) -> None:
        trajectory = Trajectory(
            primitive=MotionPrimitive.OSCILLATE, amplitude=0.1, frequency_hz=1.0
        )
        assert sample_trajectory(trajectory, 0.0).x == pytest.approx(0.0, abs=1e-9)
        assert sample_trajectory(trajectory, 0.5).x == pytest.approx(0.0, abs=1e-9)

    def test_jitter_is_deterministic(self) -> None:
        trajectory = Trajectory(
            primitive=MotionPrimitive.JITTER, amplitude=0.02, frequency_hz=8.0
        )
        assert sample_trajectory(trajectory, 0.3) == sample_trajectory(trajectory, 0.3)

    @pytest.mark.parametrize("kind", list(Easing))
    def test_every_easing_starts_at_zero_and_reaches_one(self, kind) -> None:
        assert ease(kind, 0.0) == pytest.approx(0.0, abs=1e-6)
        assert ease(kind, 1.0) == pytest.approx(1.0, abs=0.02)

    def test_an_instant_outside_the_range_is_refused(self) -> None:
        with pytest.raises(ValueError, match="hors de"):
            sample_trajectory(Trajectory(), 1.5)


# ------------------------------------------------------------ vraies vidéos


@needs_ffmpeg
class TestRealVideoFiles:
    def test_one_video_per_shot(self, rendered) -> None:
        _, routing, _, outcome, _ = rendered
        assert len(outcome.renders) == len(routing.executables)
        for render in outcome.renders:
            assert render.video_path.is_file()
            assert render.video_path.stat().st_size > 1000

    def test_the_file_really_contains_what_was_asked(self, rendered) -> None:
        episode, routing, _, outcome, _ = rendered
        for render in outcome.renders:
            executable = routing.for_shot(render.shot_id)
            probe = probe_video(render.video_path)
            assert probe.codec == "h264"
            assert (probe.width, probe.height) == (
                executable.resolution.width,
                executable.resolution.height,
            )
            assert probe.fps == pytest.approx(executable.fps, abs=0.5)
            assert probe.duration_s == pytest.approx(executable.duration_s, abs=0.1)
            assert not probe.has_audio

    def test_the_frame_count_follows_duration_and_fps(self, rendered) -> None:
        _, routing, _, outcome, _ = rendered
        for render in outcome.renders:
            executable = routing.for_shot(render.shot_id)
            expected = round(executable.duration_s * executable.fps)
            assert abs(render.frame_count - expected) <= 2

    def test_an_artifact_records_the_real_file(self, rendered) -> None:
        import hashlib

        _, _, _, outcome, root = rendered
        for artifact in outcome.artifacts:
            assert artifact.kind is ArtifactKind.VIDEO
            path = root / "renders" / artifact.path
            assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact.sha256
            assert artifact.duration_s and artifact.duration_s > 0
            assert artifact.actual_cost_usd == 0.0
            assert artifact.provider is None


@needs_ffmpeg
class TestTheImageActuallyMoves:
    def _frames(self, path, count: int = 3):
        """Décode quelques images du fichier rendu, pour les comparer."""
        import subprocess

        from PIL import Image

        probe = probe_video(path)
        picks = [0, probe.frame_count // 2, max(0, probe.frame_count - 2)][:count]
        frames = []
        for index in picks:
            run = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error",
                    "-i", str(path),
                    "-vf", f"select=eq(n\\,{index})",
                    "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-",
                ],
                capture_output=True,
                check=True,
            )
            import io

            frames.append(Image.open(io.BytesIO(run.stdout)).convert("RGB"))
        return frames

    def _difference(self, first, second) -> float:
        from PIL import ImageChops

        diff = ImageChops.difference(first, second)
        values = diff.tobytes()
        return sum(values) / len(values) / 255.0

    def test_a_moving_strategy_changes_the_image_over_time(self, rendered) -> None:
        _, routing, _, outcome, _ = rendered
        moving = [
            render
            for render in outcome.renders
            if render.strategy is not RenderStrategy.STILL
        ]
        assert moving, "l'épisode de test doit contenir au moins un plan animé"
        for render in moving:
            first, middle, last = self._frames(render.video_path)
            assert self._difference(first, last) > 0.001, render.shot_id
            assert self._difference(first, middle) > 0.0

    def test_a_still_strategy_does_not_move(self, rendered, tmp_path) -> None:
        episode, routing, images, _, _ = rendered
        frozen = [
            executable.model_copy(
                update={
                    "strategy": RenderStrategy.STILL,
                    "execution_camera": CameraMove.LOCK,
                    "degradations": [
                        *executable.degradations,
                        _camera_degradation(executable),
                    ]
                    if executable.execution_camera is not CameraMove.LOCK
                    else executable.degradations,
                }
            )
            for executable in routing.executables[:1]
        ]
        outcome = DeterministicRenderer().render(
            executables=frozen,
            motion_programs=episode.motion_programs,
            images=images.images,
            into=tmp_path / "still",
        )
        first, _, last = self._frames(outcome.renders[0].video_path)
        assert self._difference(first, last) < 0.002


def _camera_degradation(executable):
    from pdz2.contracts.render import Degradation, DegradationSeverity

    return Degradation(
        field="camera",
        requested=executable.requested.camera.value,
        executed=CameraMove.LOCK.value,
        reason="plan figé pour ce test",
        description="image fixe",
        severity=DegradationSeverity.PERCEPTUAL,
    )


@needs_ffmpeg
class TestRefusals:
    def test_a_shot_without_an_image_is_refused(self, rendered, tmp_path) -> None:
        episode, routing, _, _, _ = rendered
        with pytest.raises(RenderFailed, match="aucune image de départ"):
            DeterministicRenderer().render(
                executables=routing.executables,
                motion_programs=episode.motion_programs,
                images=[],
                into=tmp_path / "out",
            )

    def test_a_generative_strategy_is_out_of_scope(self, rendered, tmp_path) -> None:
        episode, routing, images, _, _ = rendered
        generative = routing.executables[0].model_copy(
            update={
                "strategy": RenderStrategy.DIRECT_I2V,
                "provider": "un-adaptateur",
                "degradations": routing.executables[0].degradations,
            }
        )
        with pytest.raises(RenderFailed, match="hors du périmètre"):
            DeterministicRenderer().render(
                executables=[generative],
                motion_programs=episode.motion_programs,
                images=images.images,
                into=tmp_path / "out",
            )


class TestFfmpegIsProbed:
    def test_the_capability_is_measured_and_dated(self) -> None:
        capability = ffmpeg_capability()
        assert capability.measured_at is not None
        assert capability.measurement_method
        assert capability.requires_network is False

    def test_a_missing_binary_is_reported_not_guessed(self) -> None:
        capability = ffmpeg_capability("ffmpeg-qui-n-existe-pas")
        assert not capability.usable
        assert "absent du PATH" in capability.detail
