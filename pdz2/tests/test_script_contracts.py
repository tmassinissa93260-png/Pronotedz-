"""Script, et la règle VOICE FIRST."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pdz2.contracts import ScriptState, VoiceSegment, VoiceTimeline, WordTiming
from pdz2.contracts.script import TimingSource
from pdz2.tests import factories


class TestScriptLine:
    def test_emphasis_words_must_appear_in_the_text(self) -> None:
        with pytest.raises(ValidationError, match="absents du texte"):
            factories.script_line(emphasis_words=["turbine"])

    def test_emphasis_matching_ignores_case(self) -> None:
        line = factories.script_line(emphasis_words=["ROTOR"])
        assert line.emphasis_words == ["ROTOR"]

    def test_estimated_duration_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            factories.script_line(estimated_duration_s=0.0)


class TestScriptState:
    def test_lines_must_be_contiguous(self) -> None:
        with pytest.raises(ValidationError, match="non contiguës"):
            ScriptState(
                director_state_id="director_state-x",
                lines=[factories.script_line(0), factories.script_line(2)],
            )

    def test_estimated_total_is_only_a_sum_of_estimates(self) -> None:
        script = factories.script_state(lines=3)
        assert script.estimated_total_s == pytest.approx(12.0)


class TestVoiceFirst:
    def test_an_estimated_timeline_is_refused(self) -> None:
        script = factories.script_state()
        with pytest.raises(ValidationError, match="VOICE FIRST"):
            factories.voice_timeline(script, timing_source=TimingSource.ESTIMATED)

    def test_a_measured_timeline_is_accepted(self) -> None:
        timeline = factories.voice_timeline()
        assert timeline.timing_source in {
            TimingSource.MEASURED_TTS,
            TimingSource.MEASURED_FILE,
        }
        assert timeline.speech_duration_s > 0

    def test_measured_file_is_also_accepted(self) -> None:
        timeline = factories.voice_timeline(timing_source=TimingSource.MEASURED_FILE)
        assert timeline.timing_source is TimingSource.MEASURED_FILE


class TestVoiceTimelineGeometry:
    def test_segments_cannot_overlap(self) -> None:
        script = factories.script_state()
        segments = [
            VoiceSegment(line_id=script.lines[0].id, line_index=0, start_s=0.0, end_s=4.0),
            VoiceSegment(line_id=script.lines[1].id, line_index=1, start_s=3.0, end_s=6.0),
        ]
        with pytest.raises(ValidationError, match="chevauche"):
            VoiceTimeline(
                script_state_id=script.id,
                audio_path="voice.wav",
                sample_rate=48000,
                total_duration_s=6.0,
                timing_source=TimingSource.MEASURED_TTS,
                segments=segments,
            )

    def test_a_segment_cannot_exceed_the_total_duration(self) -> None:
        script = factories.script_state(lines=1)
        with pytest.raises(ValidationError, match="dépasse la durée totale"):
            VoiceTimeline(
                script_state_id=script.id,
                audio_path="voice.wav",
                sample_rate=48000,
                total_duration_s=2.0,
                timing_source=TimingSource.MEASURED_TTS,
                segments=[
                    VoiceSegment(
                        line_id=script.lines[0].id, line_index=0, start_s=0.0, end_s=5.0
                    )
                ],
            )

    def test_a_word_cannot_fall_outside_its_segment(self) -> None:
        with pytest.raises(ValidationError, match="hors du segment"):
            VoiceSegment(
                line_id="script_line-1",
                line_index=0,
                start_s=1.0,
                end_s=2.0,
                words=[WordTiming(word="rotor", start_s=0.2, end_s=0.5)],
            )

    def test_segment_lookup_by_line(self) -> None:
        timeline = factories.voice_timeline()
        assert timeline.segment_for_line(1).line_index == 1
        with pytest.raises(KeyError):
            timeline.segment_for_line(99)

    def test_backwards_segment_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="fin avant début"):
            VoiceSegment(line_id="l", line_index=0, start_s=3.0, end_s=1.0)
