"""Phase 8 : l'observateur mesure, il ne devine pas."""

from __future__ import annotations

import numpy as np
import pytest

from pdz2.contracts.enums import Severity
from pdz2.contracts.motion import CameraMove
from pdz2.contracts.render import (
    Degradation,
    DegradationSeverity,
    RenderStrategy,
)
from pdz2.engines.imagery import ProceduralImageRenderer
from pdz2.engines.routing import RenderRouter
from pdz2.qa import (
    DeterministicObserver,
    FrameSequence,
    black_frame_ratio,
    decode_frames,
    first_to_last_difference,
    frozen_frame_ratio,
    mean_absolute_difference,
    sharpness,
)
from pdz2.renderers import DeterministicRenderer, ffmpeg_capability
from pdz2.tests import pipeline

needs_ffmpeg = pytest.mark.skipif(
    not ffmpeg_capability().usable, reason="binaire ffmpeg absent"
)


def _sequence(frames: np.ndarray) -> FrameSequence:
    return FrameSequence(
        frames=frames.astype(np.float32),
        fps=30.0,
        duration_s=frames.shape[0] / 30.0,
        source_width=frames.shape[2],
        source_height=frames.shape[1],
    )


@pytest.fixture(scope="module")
def observed(tmp_path_factory):
    root = tmp_path_factory.mktemp("phase8")
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
    renders = DeterministicRenderer().render(
        executables=routing.executables,
        motion_programs=episode.motion_programs,
        images=images.images,
        into=root / "renders",
    )
    outcome = DeterministicObserver().observe(
        artifacts=renders.artifacts,
        executables=routing.executables,
        motion_programs=episode.motion_programs,
        visual_bible=episode.bible,
        renders_dir=root / "renders",
    )
    return episode, routing, images, renders, outcome, root


# ------------------------------------------------------ mesures élémentaires


class TestMeasuresAreArithmetic:
    def test_identical_frames_have_no_motion(self) -> None:
        frames = np.tile(np.full((8, 8), 0.5), (10, 1, 1))
        sequence = _sequence(frames)
        assert mean_absolute_difference(sequence) == 0.0
        assert first_to_last_difference(sequence) == 0.0
        assert frozen_frame_ratio(sequence) == 1.0

    def test_a_slow_drift_is_seen_end_to_end_not_frame_to_frame(self) -> None:
        """Le défaut trouvé en phase 8 : un mouvement lent n'est pas un gel."""
        frames = np.stack(
            [np.full((8, 8), 0.4 + 0.002 * index) for index in range(100)]
        )
        sequence = _sequence(frames)
        assert mean_absolute_difference(sequence) == pytest.approx(0.002, abs=1e-4)
        assert first_to_last_difference(sequence) == pytest.approx(0.198, abs=1e-3)
        assert first_to_last_difference(sequence) > mean_absolute_difference(sequence)

    def test_black_frames_are_counted(self) -> None:
        frames = np.concatenate(
            [np.zeros((4, 8, 8)), np.full((6, 8, 8), 0.5)]
        )
        assert black_frame_ratio(_sequence(frames)) == pytest.approx(0.4)

    def test_a_flat_image_has_no_sharpness(self) -> None:
        flat = _sequence(np.full((4, 16, 16), 0.5))
        noisy = _sequence(np.random.default_rng(0).random((4, 16, 16)))
        assert sharpness(flat) == pytest.approx(0.0, abs=1e-9)
        assert sharpness(noisy) > sharpness(flat)

    def test_a_single_frame_has_no_motion(self) -> None:
        sequence = _sequence(np.full((1, 8, 8), 0.5))
        assert mean_absolute_difference(sequence) == 0.0
        assert first_to_last_difference(sequence) == 0.0


@needs_ffmpeg
class TestDecoding:
    def test_the_decoder_returns_every_frame(self, observed) -> None:
        _, _, _, renders, _, root = observed
        render = renders.renders[0]
        sequence = decode_frames(render.video_path)
        assert abs(sequence.count - render.frame_count) <= 2
        assert sequence.frames.min() >= 0.0
        assert sequence.frames.max() <= 1.0

    def test_decoding_is_reproducible(self, observed) -> None:
        _, _, _, renders, _, _ = observed
        path = renders.renders[0].video_path
        first, second = decode_frames(path), decode_frames(path)
        assert np.array_equal(first.frames, second.frames)


# --------------------------------------------------------------- observation


@needs_ffmpeg
class TestObservation:
    def test_real_renders_pass(self, observed) -> None:
        *_, outcome, _ = observed
        assert outcome.reports
        for report in outcome.reports:
            failing = [c.check_id for c in report.checks if not c.passed]
            assert report.passed, f"{report.shot_id} : {failing}"

    def test_every_measurement_carries_its_method(self, observed) -> None:
        *_, outcome, _ = observed
        for report in outcome.reports:
            for measurement in report.measurements:
                assert measurement.method.strip()
                assert measurement.unit.strip()

    def test_the_observation_is_deterministic(self, observed) -> None:
        episode, routing, _, renders, outcome, root = observed
        again = DeterministicObserver().observe(
            artifacts=renders.artifacts,
            executables=routing.executables,
            motion_programs=episode.motion_programs,
            visual_bible=episode.bible,
            renders_dir=root / "renders",
        )
        for first, second in zip(outcome.reports, again.reports, strict=True):
            assert [m.value for m in first.measurements] == [
                m.value for m in second.measurements
            ]

    def test_the_verdict_follows_the_checks(self, observed) -> None:
        *_, outcome, _ = observed
        for report in outcome.reports:
            blocking = [
                c for c in report.checks
                if c.severity is Severity.BLOCKING and not c.passed
            ]
            assert report.passed == (not blocking) or not report.passed

    def test_the_duration_is_checked_against_the_request(self, observed) -> None:
        _, routing, _, _, outcome, _ = observed
        for report in outcome.reports:
            executable = routing.for_shot(report.shot_id)
            check = next(c for c in report.checks if c.check_id == "duration")
            assert check.expected == pytest.approx(executable.duration_s, abs=1e-3)


@needs_ffmpeg
class TestTheObserverCatchesRealFailures:
    def _render_frozen(self, observed, tmp_path):
        episode, routing, images, _, _, _ = observed
        original = routing.executables[0]
        degradations = list(original.degradations)
        if original.execution_camera is not CameraMove.LOCK:
            degradations.append(
                Degradation(
                    field="camera",
                    requested=original.requested.camera.value,
                    executed="lock",
                    reason="contre-épreuve d'observation",
                    description="plan volontairement figé",
                    severity=DegradationSeverity.PERCEPTUAL,
                )
            )
        frozen = original.model_copy(
            update={
                "strategy": RenderStrategy.STILL,
                "execution_camera": CameraMove.LOCK,
                "degradations": degradations,
            }
        )
        renders = DeterministicRenderer().render(
            executables=[frozen],
            motion_programs=episode.motion_programs,
            images=images.images,
            into=tmp_path / "frozen",
        )
        return episode, frozen, renders, tmp_path / "frozen"

    def test_a_shot_that_should_move_and_does_not_is_caught(
        self, observed, tmp_path
    ) -> None:
        episode, frozen, renders, directory = self._render_frozen(observed, tmp_path)
        outcome = DeterministicObserver().observe(
            artifacts=renders.artifacts,
            executables=[frozen],
            motion_programs=episode.motion_programs,
            visual_bible=episode.bible,
            renders_dir=directory,
        )
        report = outcome.reports[0]
        assert not report.passed
        failing = {c.check_id for c in report.checks if not c.passed}
        assert "motion_present" in failing
        assert report.measurement("motion_first_to_last").value < 0.002

    def test_a_duration_that_does_not_match_the_file_is_caught(
        self, observed
    ) -> None:
        """Le contrôle porte sur le fichier, pas sur ce qu'on croyait rendre."""
        from pdz2.contracts.render import RenderSpecExecutable

        episode, routing, _, renders, _, root = observed
        original = routing.executables[0]
        payload = original.model_dump()
        payload["duration_s"] = original.duration_s + 3.0
        payload["degradations"] = [
            *payload["degradations"],
            Degradation(
                field="duration_s",
                requested=f"{original.requested.duration_s:.3f}s",
                executed=f"{original.duration_s + 3.0:.3f}s",
                reason="contre-épreuve d'observation",
                description="durée annoncée volontairement fausse",
                severity=DegradationSeverity.NARRATIVE,
            ).model_dump(),
        ]
        stretched = RenderSpecExecutable(**payload)

        artifact = next(
            a for a in renders.artifacts if a.source_contract_id == original.id
        ).model_copy(update={"source_contract_id": stretched.id})
        outcome = DeterministicObserver().observe(
            artifacts=[artifact],
            executables=[stretched],
            motion_programs=episode.motion_programs,
            visual_bible=episode.bible,
            renders_dir=root / "renders",
        )
        report = outcome.reports[0]
        assert not report.passed
        assert "duration" in {c.check_id for c in report.checks if not c.passed}

    def test_a_black_render_is_caught(self, observed, tmp_path) -> None:
        """Un fichier noir passe la durée et la résolution, pas le contenu."""
        import subprocess

        episode, routing, _, renders, _, _ = observed
        executable = routing.executables[0]
        black = tmp_path / "black.mp4"
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi",
                "-i", f"color=c=black:s={executable.resolution.width}x"
                      f"{executable.resolution.height}:r={executable.fps}:"
                      f"d={executable.duration_s}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(black),
            ],
            check=True,
            capture_output=True,
        )
        artifact = renders.artifacts[0].model_copy(
            update={"path": black.name, "source_contract_id": executable.id}
        )
        outcome = DeterministicObserver().observe(
            artifacts=[artifact],
            executables=[executable],
            motion_programs=episode.motion_programs,
            visual_bible=episode.bible,
            renders_dir=tmp_path,
        )
        report = outcome.reports[0]
        assert not report.passed
        failing = {c.check_id for c in report.checks if not c.passed}
        assert "not_black" in failing


class TestWhatTheObserverDoesNotClaim:
    def test_it_measures_nothing_about_beauty_or_recognition(self) -> None:
        """Sans modèle, prétendre le mesurer serait une mesure inventée."""
        from pdz2.qa import observer

        source = observer.__doc__ or ""
        assert "revue humaine" in source
        forbidden = {"beauty", "beau", "recognition", "reconnaissance_objet"}
        names = {
            name
            for name in dir(observer)
            if not name.startswith("_")
        }
        assert not names & forbidden
