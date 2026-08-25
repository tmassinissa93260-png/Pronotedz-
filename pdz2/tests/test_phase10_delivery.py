"""Phase 10 : montage, mastering, sous-titres, QA finale, livraison."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pdz2.audio import AudioMasterer, measure_loudness
from pdz2.audio.mastering import LOUDNESS_TOLERANCE_LU, TARGET_LUFS
from pdz2.contracts.delivery import LoudnessMeasurement, TrackKind
from pdz2.contracts.enums import AspectRatio, Severity
from pdz2.editing import (
    AssemblyFailed,
    EditCompiler,
    EditRejected,
    SubtitleCompiler,
    SubtitleRejected,
    VideoAssembler,
    to_srt,
)
from pdz2.qa import HUMAN_REVIEW_NOTICE, FinalQa
from pdz2.renderers import ffmpeg_capability
from pdz2.tests import pipeline

needs_ffmpeg = pytest.mark.skipif(
    not ffmpeg_capability().usable, reason="binaire ffmpeg absent"
)


@pytest.fixture(scope="module")
def delivered(tmp_path_factory):
    """Chaîne complète jusqu'au MP4, en petite résolution."""
    from pdz2.engines.imagery import ProceduralImageRenderer
    from pdz2.engines.routing import RenderRouter
    from pdz2.renderers import DeterministicRenderer

    root = tmp_path_factory.mktemp("phase10")
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
    edit = EditCompiler().compile(
        episode_id="ep",
        shot_graph=episode.graph,
        temporal_plan=episode.temporal_plan,
        voice_timeline=episode.timeline,
        video_artifacts=renders.artifacts,
        voice_artifact_path="audio_master.wav",
        aspect_ratio=AspectRatio.VERTICAL,
    )
    master = AudioMasterer().master(
        source=root / "audio" / "voice.wav", out_path=root / "audio_master.wav"
    )
    subtitles = SubtitleCompiler().compile(
        script=episode.script,
        voice_timeline=episode.timeline,
        typography=episode.bible.typography,
    )
    srt = root / "subtitles.srt"
    srt.write_text(to_srt(subtitles.track), encoding="utf-8")
    clip_paths = {
        artifact.id: root / "renders" / artifact.path
        for artifact in renders.artifacts
    }
    assembly = VideoAssembler().assemble(
        timeline=edit.timeline,
        clip_paths=clip_paths,
        audio_path=master.path,
        out_path=root / "final.mp4",
        subtitle_path=srt,
    )
    return episode, renders, edit, master, subtitles, assembly, clip_paths, root


# ------------------------------------------------------------------- montage


class TestEditTimeline:
    def test_the_clips_tile_the_measured_audio(self, delivered) -> None:
        episode, _, edit, *_ = delivered
        video = next(
            t for t in edit.timeline.tracks if t.kind is TrackKind.VIDEO
        )
        assert len(video.clips) == len(episode.temporal_plan.slots)
        assert edit.timeline.duration_s == pytest.approx(
            episode.timeline.total_duration_s, abs=0.05
        )

    def test_the_voice_gets_its_own_track(self, delivered) -> None:
        _, _, edit, *_ = delivered
        voice = next(t for t in edit.timeline.tracks if t.kind is TrackKind.VOICE)
        assert len(voice.clips) == 1

    def test_a_shot_without_a_render_is_refused(self, delivered) -> None:
        episode, renders, _, *_ = delivered
        with pytest.raises(EditRejected, match="aucun rendu vidéo"):
            EditCompiler().compile(
                episode_id="ep",
                shot_graph=episode.graph,
                temporal_plan=episode.temporal_plan,
                voice_timeline=episode.timeline,
                video_artifacts=renders.artifacts[:-1],
                voice_artifact_path="audio_master.wav",
                aspect_ratio=AspectRatio.VERTICAL,
            )

    def test_a_render_of_the_wrong_length_is_refused(self, delivered) -> None:
        """Un montage bâti sur deux durées produit un décalage définitif."""
        episode, renders, *_ = delivered
        stretched = [
            artifact.model_copy(update={"duration_s": (artifact.duration_s or 1) + 2})
            if index == 0
            else artifact
            for index, artifact in enumerate(renders.artifacts)
        ]
        with pytest.raises(EditRejected, match="le montage dériverait"):
            EditCompiler().compile(
                episode_id="ep",
                shot_graph=episode.graph,
                temporal_plan=episode.temporal_plan,
                voice_timeline=episode.timeline,
                video_artifacts=stretched,
                voice_artifact_path="audio_master.wav",
                aspect_ratio=AspectRatio.VERTICAL,
            )

    def test_a_foreign_voice_timeline_is_refused(self, delivered, tmp_path) -> None:
        episode, renders, *_ = delivered
        stranger = pipeline.build_episode(tmp_path / "stranger")
        with pytest.raises(EditRejected, match="ne dérive pas"):
            EditCompiler().compile(
                episode_id="ep",
                shot_graph=episode.graph,
                temporal_plan=episode.temporal_plan,
                voice_timeline=stranger.timeline,
                video_artifacts=renders.artifacts,
                voice_artifact_path="audio_master.wav",
                aspect_ratio=AspectRatio.VERTICAL,
            )


# ---------------------------------------------------------------- mastering


@needs_ffmpeg
class TestMastering:
    def test_it_measures_before_and_after(self, delivered) -> None:
        *_, master, _, _, _, _ = delivered
        assert master.path.is_file()
        assert len(master.notes) >= 2
        assert "avant" in master.notes[0]
        assert "après" in master.notes[1]

    def test_the_final_measure_is_taken_on_the_written_file(self, delivered) -> None:
        """On relit ce qui a été écrit, pas ce que le filtre annonce."""
        *_, master, _, _, _, _ = delivered
        independent = measure_loudness(master.path)
        assert independent.integrated_lufs == pytest.approx(
            master.loudness.integrated_lufs, abs=0.2
        )

    def test_it_moves_towards_the_target(self, delivered, tmp_path) -> None:
        *_, master, _, _, _, root = delivered
        before = measure_loudness(root / "audio" / "voice.wav")
        assert abs(master.loudness.integrated_lufs - TARGET_LUFS) < abs(
            before.integrated_lufs - TARGET_LUFS
        )

    def test_the_true_peak_ceiling_is_respected(self, delivered) -> None:
        *_, master, _, _, _, _ = delivered
        assert master.loudness.true_peak_dbtp <= -1.0

    def test_a_missed_target_says_why(self, delivered) -> None:
        """Un écart nu n'apprend rien : la contrainte doit être nommée."""
        *_, master, _, _, _, _ = delivered
        gap = abs(master.loudness.integrated_lufs - TARGET_LUFS)
        if gap > LOUDNESS_TOLERANCE_LU:
            joined = " ".join(master.notes)
            assert "plafond de crête" in joined
            assert "décision de mixage" in joined

    def test_a_missing_source_is_refused(self, tmp_path) -> None:
        from pdz2.audio import MasteringFailed

        with pytest.raises(MasteringFailed, match="absent"):
            AudioMasterer().master(
                source=tmp_path / "rien.wav", out_path=tmp_path / "out.wav"
            )


# --------------------------------------------------------------- sous-titres


class TestSubtitles:
    def test_every_cue_sits_inside_a_measured_segment(self, delivered) -> None:
        episode, _, _, _, subtitles, *_ = delivered
        spans = [
            (segment.start_s, segment.end_s)
            for segment in episode.timeline.segments
        ]
        for cue in subtitles.track.cues:
            assert any(
                start - 0.01 <= cue.start_s and cue.end_s <= end + 0.01
                for start, end in spans
            ), cue.text

    def test_the_cues_never_overlap(self, delivered) -> None:
        _, _, _, _, subtitles, *_ = delivered
        previous = 0.0
        for cue in subtitles.track.cues:
            assert cue.start_s >= previous - 0.02
            previous = cue.end_s

    def test_long_lines_are_split(self, delivered) -> None:
        episode, _, _, _, subtitles, *_ = delivered
        assert len(subtitles.track.cues) >= len(episode.script.lines)

    def test_short_cues_are_reported(self, delivered) -> None:
        _, _, _, _, subtitles, *_ = delivered
        joined = " ".join(subtitles.notes)
        if any(c.end_s - c.start_s < 0.7 for c in subtitles.track.cues):
            assert "à peine lisibles" in joined

    def test_the_srt_is_well_formed(self, delivered) -> None:
        _, _, _, _, subtitles, *_ = delivered
        text = to_srt(subtitles.track)
        assert text.startswith("1\n")
        assert "-->" in text
        assert text.count("-->") == len(subtitles.track.cues)

    def test_a_foreign_script_is_refused(self, delivered, tmp_path) -> None:
        episode, *_ = delivered
        stranger = pipeline.build_episode(tmp_path / "stranger2")
        with pytest.raises(SubtitleRejected, match="ne décrit pas ce script"):
            SubtitleCompiler().compile(
                script=stranger.script,
                voice_timeline=episode.timeline,
                typography=episode.bible.typography,
            )


# --------------------------------------------------------------- assemblage


@needs_ffmpeg
class TestAssemblyAndFinalQa:
    def test_the_master_is_a_real_playable_file(self, delivered) -> None:
        *_, assembly, _, _ = delivered
        assert assembly.path.is_file()
        assert assembly.has_audio
        assert assembly.size_bytes > 10_000
        assert len(assembly.sha256) == 64

    def test_the_master_duration_follows_the_timeline(self, delivered) -> None:
        _, _, edit, _, _, assembly, _, _ = delivered
        assert assembly.duration_s == pytest.approx(edit.timeline.duration_s, abs=0.15)

    def test_final_qa_passes_on_a_sound_master(self, delivered) -> None:
        _, _, edit, master, _, assembly, _, _ = delivered
        outcome = FinalQa().check(
            master_path=assembly.path,
            timeline=edit.timeline,
            loudness=master.loudness,
            aspect_ratio=AspectRatio.VERTICAL,
            master_artifact_id="master_artifact-test",
        )
        failing = [c.check_id for c in outcome.report.checks if not c.passed]
        assert outcome.deliverable, failing

    def test_final_qa_says_what_it_cannot_judge(self, delivered) -> None:
        _, _, edit, master, _, assembly, _, _ = delivered
        outcome = FinalQa().check(
            master_path=assembly.path,
            timeline=edit.timeline,
            loudness=master.loudness,
            aspect_ratio=AspectRatio.VERTICAL,
            master_artifact_id="master_artifact-test",
        )
        assert HUMAN_REVIEW_NOTICE in outcome.notes
        assert "revue humaine" in HUMAN_REVIEW_NOTICE

    def test_final_qa_refuses_a_silent_master(self, delivered, tmp_path) -> None:
        _, _, edit, master, _, assembly, _, _ = delivered
        muted = tmp_path / "muted.mp4"
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-i", str(assembly.path), "-an", "-c:v", "copy", str(muted)],
            check=True, capture_output=True,
        )
        outcome = FinalQa().check(
            master_path=muted,
            timeline=edit.timeline,
            loudness=master.loudness,
            aspect_ratio=AspectRatio.VERTICAL,
            master_artifact_id="master_artifact-test",
        )
        assert not outcome.deliverable
        failing = {c.check_id for c in outcome.report.checks if not c.passed}
        assert "final_has_audio" in failing

    def test_final_qa_refuses_a_wrong_aspect_ratio(self, delivered) -> None:
        _, _, edit, master, _, assembly, _, _ = delivered
        outcome = FinalQa().check(
            master_path=assembly.path,
            timeline=edit.timeline,
            loudness=master.loudness,
            aspect_ratio=AspectRatio.HORIZONTAL,
            master_artifact_id="master_artifact-test",
        )
        assert not outcome.deliverable
        failing = {c.check_id for c in outcome.report.checks if not c.passed}
        assert "final_format" in failing

    def test_loudness_out_of_range_is_only_a_minor_note(self, delivered) -> None:
        """Une plateforme corrigera : ce n'est pas un motif de blocage."""
        _, _, edit, _, _, assembly, _, _ = delivered
        outcome = FinalQa().check(
            master_path=assembly.path,
            timeline=edit.timeline,
            loudness=LoudnessMeasurement(
                integrated_lufs=-25.0, true_peak_dbtp=-3.0, loudness_range_lu=4.0
            ),
            aspect_ratio=AspectRatio.VERTICAL,
            master_artifact_id="master_artifact-test",
        )
        loudness_check = next(
            c for c in outcome.report.checks if c.check_id == "final_loudness"
        )
        assert not loudness_check.passed
        assert loudness_check.severity is Severity.MINOR
        assert outcome.deliverable

    def test_a_missing_clip_is_refused(self, delivered, tmp_path) -> None:
        _, _, edit, master, _, _, _, _ = delivered
        with pytest.raises(AssemblyFailed, match="clips sans fichier"):
            VideoAssembler().assemble(
                timeline=edit.timeline,
                clip_paths={},
                audio_path=master.path,
                out_path=tmp_path / "out.mp4",
            )

    def test_a_missing_audio_is_refused(self, delivered, tmp_path) -> None:
        _, _, edit, _, _, _, clip_paths, _ = delivered
        with pytest.raises(AssemblyFailed, match="audio masterisé absent"):
            VideoAssembler().assemble(
                timeline=edit.timeline,
                clip_paths=clip_paths,
                audio_path=tmp_path / "rien.wav",
                out_path=tmp_path / "out.mp4",
            )


class TestTheOrderedDurationIsChecked:
    """Le livrable tient-il la durée commandée, et le dit-il quand non ?"""

    def _report(self, delivered, target):
        from pdz2.audio.mastering import measure_loudness
        from pdz2.qa import FinalQa

        _, _, edit, master, _, _, _, root = delivered
        return FinalQa().check(
            master_path=root / "final.mp4",
            timeline=edit.timeline,
            loudness=measure_loudness(master.path),
            aspect_ratio=AspectRatio.VERTICAL,
            master_artifact_id="master_artifact-test",
            target_duration_s=target,
        ).report

    def _check(self, report):
        return next(
            c for c in report.checks if c.check_id == "final_duration_target"
        )

    @needs_ffmpeg
    def test_a_deliverable_of_the_ordered_length_passes(self, delivered):
        reel = delivered[2].timeline.duration_s
        assert self._check(self._report(delivered, reel)).passed

    @needs_ffmpeg
    def test_a_deliverable_far_shorter_than_ordered_is_flagged(self, delivered):
        """40 s commandées pour 27 s livrées : le cas réel du vertical slice."""
        commande = delivered[2].timeline.duration_s * 1.5
        check = self._check(self._report(delivered, commande))
        assert not check.passed
        assert check.severity is Severity.MINOR, (
            "un écart éditorial ne doit pas jeter un livrable techniquement bon"
        )

    @needs_ffmpeg
    def test_without_an_order_there_is_nothing_to_hold(self, delivered):
        assert self._check(self._report(delivered, None)).passed


class TestATruncatedMasterIsRefused:
    """Un en-tête intact ne prouve pas un fichier intact.

    `ffprobe` lit la durée et le nombre d'images dans l'en-tête du conteneur.
    Un master tronqué garde donc un en-tête juste et ment : mesuré sur le
    livrable de référence coupé à 58 Kio sur 2 699, l'en-tête annonçait
    toujours 823 images et 27,44 s, et 13 images se décodaient.
    """

    def _tronque(self, source: Path, cible: Path, octets: int = 60_000) -> Path:
        cible.write_bytes(source.read_bytes()[:octets])
        return cible

    @needs_ffmpeg
    def test_the_header_of_a_truncated_master_still_lies(self, delivered, tmp_path):
        """Le défaut d'origine : le contrôle de durée ne voyait rien."""
        from pdz2.renderers.ffmpeg import probe_video

        *_, root = delivered
        abime = self._tronque(root / "final.mp4", tmp_path / "tronque.mp4")
        sain = probe_video(root / "final.mp4")
        menteur = probe_video(abime)
        assert abime.stat().st_size < (root / "final.mp4").stat().st_size / 4
        assert menteur.duration_s == pytest.approx(sain.duration_s, abs=0.1)

    @needs_ffmpeg
    def test_the_completeness_check_catches_it(self, delivered, tmp_path):
        from pdz2.audio.mastering import measure_loudness
        from pdz2.qa import FinalQa

        _, _, edit, master, _, _, _, root = delivered
        abime = self._tronque(root / "final.mp4", tmp_path / "tronque.mp4")
        qa = FinalQa().check(
            master_path=abime,
            timeline=edit.timeline,
            loudness=measure_loudness(master.path),
            aspect_ratio=AspectRatio.VERTICAL,
            master_artifact_id="master_artifact-test",
        )
        complet = next(
            c for c in qa.report.checks if c.check_id == "final_complete"
        )
        assert not complet.passed
        assert complet.severity is Severity.BLOCKING
        assert not qa.deliverable, "un master tronqué ne doit jamais être livrable"

    @needs_ffmpeg
    def test_an_intact_master_passes_the_completeness_check(self, delivered):
        from pdz2.audio.mastering import measure_loudness
        from pdz2.qa import FinalQa

        _, _, edit, master, _, _, _, root = delivered
        qa = FinalQa().check(
            master_path=root / "final.mp4",
            timeline=edit.timeline,
            loudness=measure_loudness(master.path),
            aspect_ratio=AspectRatio.VERTICAL,
            master_artifact_id="master_artifact-test",
        )
        complet = next(
            c for c in qa.report.checks if c.check_id == "final_complete"
        )
        assert complet.passed, f"{complet.observed}/{complet.expected}"
        assert qa.deliverable
