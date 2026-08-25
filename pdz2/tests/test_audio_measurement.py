"""Mesure du WAV : c'est ici que naît l'autorité temporelle."""

from __future__ import annotations

import wave
from array import array
from math import pi, sin

import pytest

from pdz2.audio import (
    AudioCorrupt,
    AudioFormat,
    AudioFormatMismatch,
    AudioSilent,
    PcmAudio,
    concatenate,
    measure_wav,
    read_wav,
    require_audible,
    silence,
    write_wav,
)
from pdz2.audio.wave_io import SILENCE_RMS_FLOOR

FORMAT = AudioFormat(sample_rate=22050, channels=1, sample_width=2)


def tone(duration_s: float, amplitude: float = 0.5, fmt: AudioFormat = FORMAT) -> PcmAudio:
    """Sinusoïde de durée exacte : un signal réel, pas une simulation."""
    frames = round(duration_s * fmt.sample_rate)
    scale = fmt.full_scale - 1
    samples = array(
        "h",
        [
            int(amplitude * scale * sin(2 * pi * 440 * index / fmt.sample_rate))
            for index in range(frames)
        ]
        * fmt.channels,
    )
    return PcmAudio(format=fmt, samples=samples)


class TestDurationComesFromFrames:
    @pytest.mark.parametrize("duration", [0.1, 0.5, 1.0, 3.7])
    def test_measured_duration_matches_the_written_one(self, tmp_path, duration):
        path = write_wav(tone(duration), tmp_path / "t.wav")
        measured = measure_wav(path)
        assert measured.duration_s == pytest.approx(duration, abs=1e-4)

    def test_duration_is_frames_over_rate_not_bytes(self, tmp_path):
        path = write_wav(tone(1.0), tmp_path / "t.wav")
        measured = measure_wav(path)
        assert measured.frame_count == 22050
        assert measured.duration_s == pytest.approx(measured.frame_count / 22050)

    def test_the_text_plays_no_part(self, tmp_path):
        """Deux textes de longueurs opposées, même audio → même durée."""
        path = write_wav(tone(2.0), tmp_path / "t.wav")
        assert measure_wav(path).duration_s == pytest.approx(2.0, abs=1e-4)


class TestCorruptionIsRefused:
    def test_a_missing_file_is_refused(self, tmp_path):
        with pytest.raises(AudioCorrupt, match="absent"):
            measure_wav(tmp_path / "rien.wav")

    def test_a_non_wav_file_is_refused(self, tmp_path):
        path = tmp_path / "faux.wav"
        path.write_bytes(b"ce n'est pas du RIFF")
        with pytest.raises(AudioCorrupt, match="illisible"):
            measure_wav(path)

    def test_a_truncated_wav_is_refused(self, tmp_path):
        path = write_wav(tone(1.0), tmp_path / "t.wav")
        data = path.read_bytes()
        path.write_bytes(data[:20])
        with pytest.raises(AudioCorrupt):
            measure_wav(path)

    def test_a_wav_without_frames_is_refused(self, tmp_path):
        path = tmp_path / "vide.wav"
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(22050)
            handle.writeframes(b"")
        with pytest.raises(AudioCorrupt, match="aucune trame"):
            measure_wav(path)


class TestSilenceIsRefused:
    def test_a_silent_file_is_detected(self, tmp_path):
        path = write_wav(silence(FORMAT, 1.0), tmp_path / "mute.wav")
        assert measure_wav(path).is_silent

    def test_require_audible_refuses_it(self, tmp_path):
        path = write_wav(silence(FORMAT, 1.0), tmp_path / "mute.wav")
        with pytest.raises(AudioSilent, match="rien produit d'audible"):
            require_audible(measure_wav(path), "réplique 0")

    def test_a_real_tone_passes(self, tmp_path):
        path = write_wav(tone(1.0), tmp_path / "t.wav")
        measurement = require_audible(measure_wav(path), "réplique 0")
        assert measurement.rms > SILENCE_RMS_FLOOR
        assert measurement.peak > 0.4

    def test_a_nearly_silent_file_is_still_silent(self, tmp_path):
        path = write_wav(tone(1.0, amplitude=1e-5), tmp_path / "faible.wav")
        assert measure_wav(path).is_silent


class TestEdgeSilences:
    def test_leading_and_trailing_silence_are_located(self, tmp_path):
        audio = concatenate([silence(FORMAT, 0.5), tone(1.0), silence(FORMAT, 0.25)])
        path = write_wav(audio, tmp_path / "t.wav")
        measured = measure_wav(path)
        assert measured.leading_silence_s == pytest.approx(0.5, abs=0.02)
        assert measured.trailing_silence_s == pytest.approx(0.25, abs=0.02)
        assert measured.speech_duration_s == pytest.approx(1.0, abs=0.05)


class TestAssembly:
    def test_concatenation_adds_durations_exactly(self, tmp_path):
        merged = concatenate([tone(1.0), silence(FORMAT, 0.3), tone(0.5)])
        path = write_wav(merged, tmp_path / "m.wav")
        assert measure_wav(path).duration_s == pytest.approx(1.8, abs=1e-4)

    def test_mixing_formats_is_refused(self):
        other = AudioFormat(sample_rate=44100, channels=1, sample_width=2)
        with pytest.raises(AudioFormatMismatch, match="assemblage impossible"):
            concatenate([tone(0.5), tone(0.5, fmt=other)])

    def test_an_empty_assembly_is_refused(self):
        with pytest.raises(ValueError, match="aucun fragment"):
            concatenate([])

    def test_a_written_file_reads_back_identically(self, tmp_path):
        original = tone(0.4)
        path = write_wav(original, tmp_path / "t.wav")
        reloaded = read_wav(path)
        assert reloaded.format == original.format
        assert reloaded.samples == original.samples

    def test_silence_has_an_exact_frame_count(self):
        assert silence(FORMAT, 0.5).frame_count == 11025
        with pytest.raises(ValueError, match="négative"):
            silence(FORMAT, -1.0)
