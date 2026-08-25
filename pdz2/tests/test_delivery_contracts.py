"""Montage, sous-titres et master."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pdz2.contracts import (
    AspectRatio,
    Clip,
    EditTimeline,
    LoudnessMeasurement,
    MasterArtifact,
    Resolution,
    SubtitleCue,
    SubtitleTrack,
    Track,
    TrackKind,
)

SHA = "a" * 64
VERTICAL = Resolution(width=1080, height=1920)


def _clip(start: float, end: float, **overrides) -> Clip:
    payload = {
        "artifact_id": f"render_artifact-{start}",
        "source_in_s": 0.0,
        "source_out_s": end - start,
        "timeline_in_s": start,
        "timeline_out_s": end,
    }
    return Clip(**(payload | overrides))


class TestClip:
    def test_backwards_source_span_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="extrait source à l'envers"):
            Clip(
                artifact_id="a",
                source_in_s=5.0,
                source_out_s=2.0,
                timeline_in_s=0.0,
                timeline_out_s=3.0,
            )

    def test_backwards_timeline_span_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="position montage à l'envers"):
            Clip(
                artifact_id="a",
                source_in_s=0.0,
                source_out_s=3.0,
                timeline_in_s=5.0,
                timeline_out_s=2.0,
            )


class TestTrack:
    def test_clips_cannot_overlap(self) -> None:
        with pytest.raises(ValidationError, match="chevauchement"):
            Track(
                kind=TrackKind.VIDEO,
                name="v1",
                clips=[_clip(0.0, 5.0), _clip(3.0, 8.0)],
            )

    def test_clips_must_be_ordered(self) -> None:
        with pytest.raises(ValidationError, match="désordre"):
            Track(
                kind=TrackKind.VIDEO,
                name="v1",
                clips=[_clip(5.0, 8.0), _clip(0.0, 4.0)],
            )

    def test_track_end_is_the_last_clip(self) -> None:
        track = Track(kind=TrackKind.VIDEO, name="v1", clips=[_clip(0.0, 4.0), _clip(4.0, 9.0)])
        assert track.end_s == 9.0


class TestEditTimeline:
    def _timeline(self, **overrides) -> EditTimeline:
        payload = {
            "episode_id": "ep-1",
            "shot_graph_id": "shot_graph-1",
            "tracks": [
                Track(kind=TrackKind.VIDEO, name="v1", clips=[_clip(0.0, 10.0)]),
                Track(kind=TrackKind.VOICE, name="a1", clips=[_clip(0.0, 9.5)]),
            ],
            "duration_s": 10.0,
            "fps": 30,
            "resolution": VERTICAL,
            "aspect_ratio": AspectRatio.VERTICAL,
        }
        return EditTimeline(**(payload | overrides))

    def test_valid_timeline_is_accepted(self) -> None:
        timeline = self._timeline()
        assert timeline.track("v1").kind is TrackKind.VIDEO

    def test_a_timeline_needs_a_video_track(self) -> None:
        with pytest.raises(ValidationError, match="sans piste vidéo"):
            self._timeline(
                tracks=[Track(kind=TrackKind.VOICE, name="a1", clips=[_clip(0.0, 9.5)])]
            )

    def test_a_track_cannot_outlast_the_timeline(self) -> None:
        with pytest.raises(ValidationError, match="au-delà de la durée déclarée"):
            self._timeline(duration_s=5.0)

    def test_duplicate_track_names_are_refused(self) -> None:
        with pytest.raises(ValidationError, match="deux pistes du même nom"):
            self._timeline(
                tracks=[
                    Track(kind=TrackKind.VIDEO, name="v1", clips=[_clip(0.0, 10.0)]),
                    Track(kind=TrackKind.MUSIC, name="v1", clips=[]),
                ]
            )

    def test_resolution_must_match_the_aspect_ratio(self) -> None:
        with pytest.raises(ValidationError, match="incompatible avec le format"):
            self._timeline(resolution=Resolution(width=1920, height=1080))


class TestSubtitleTrack:
    def test_cues_must_be_contiguous(self) -> None:
        with pytest.raises(ValidationError, match="non contigus"):
            SubtitleTrack(
                voice_timeline_id="voice_timeline-1",
                cues=[
                    SubtitleCue(index=0, text="a", start_s=0.0, end_s=1.0),
                    SubtitleCue(index=2, text="b", start_s=1.0, end_s=2.0),
                ],
            )

    def test_cues_cannot_overlap(self) -> None:
        with pytest.raises(ValidationError, match="chevauche"):
            SubtitleTrack(
                voice_timeline_id="voice_timeline-1",
                cues=[
                    SubtitleCue(index=0, text="a", start_s=0.0, end_s=2.0),
                    SubtitleCue(index=1, text="b", start_s=1.0, end_s=3.0),
                ],
            )


class TestMasterArtifact:
    def _master(self, **overrides) -> MasterArtifact:
        payload = {
            "episode_id": "ep-1",
            "edit_timeline_id": "edit_timeline-1",
            "video_path": "final.mp4",
            "sha256": SHA,
            "size_bytes": 1024,
            "duration_s": 45.0,
            "resolution": VERTICAL,
            "aspect_ratio": AspectRatio.VERTICAL,
            "fps": 30,
            "loudness": LoudnessMeasurement(
                integrated_lufs=-14.0, true_peak_dbtp=-1.2, loudness_range_lu=6.0
            ),
        }
        return MasterArtifact(**(payload | overrides))

    def test_delivery_requires_a_final_qa_report(self) -> None:
        with pytest.raises(ValidationError, match="sans rapport de QA finale"):
            self._master(delivered=True)

    def test_delivery_with_a_report_is_accepted(self) -> None:
        master = self._master(delivered=True, final_qa_report_id="observation_report-9")
        assert master.delivered is True

    def test_resolution_must_match_the_aspect_ratio(self) -> None:
        with pytest.raises(ValidationError, match="incompatible avec le format"):
            self._master(resolution=Resolution(width=1000, height=1000))
