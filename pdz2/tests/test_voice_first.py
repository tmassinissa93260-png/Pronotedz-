"""La règle VOICE FIRST, vérifiée là où elle peut se briser.

Critère de réussite de la phase 2 :

    SI LE TTS CHANGE → LA VOICETIMELINE CHANGE → LES DURÉES OFFICIELLES CHANGENT.

Et son corollaire, plus important encore : la durée estimée du script ne doit
jamais pouvoir devenir l'autorité temporelle *par accident*.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from pdz2.audio import (
    AudioSilent,
    EspeakSynthesiser,
    MeasuredLine,
    NarrationRecorder,
    VoiceSpec,
    VoiceTimelineBuilder,
    measure_wav,
    silence,
    write_wav,
)
from pdz2.audio.errors import DurationInconsistent
from pdz2.audio.wave_io import AudioFormat
from pdz2.contracts.enums import NarrativeFunction
from pdz2.contracts.script import (
    ScriptLine,
    ScriptState,
    TimingSource,
    VoiceSegment,
    VoiceTimeline,
)
from pdz2.tests.test_audio_measurement import FORMAT, tone

AUDIO_PACKAGE = Path(__file__).resolve().parents[1] / "audio"

espeak = EspeakSynthesiser()
needs_espeak = pytest.mark.skipif(
    not espeak.get_capabilities().usable,
    reason="binaire espeak-ng absent : installer le paquet système « espeak-ng »",
)


def script(**overrides) -> ScriptState:
    payload = {
        "director_state_id": "director_state-x",
        "lines": [
            ScriptLine(
                index=0,
                text="Une voiture électrique convertit de l'énergie stockée en rotation.",
                function=NarrativeFunction.HOOK,
                visual_requirement="ouverture",
                estimated_duration_s=4.0,
            ),
            ScriptLine(
                index=1,
                text="Le courant de la batterie crée un champ qui met le rotor en rotation.",
                function=NarrativeFunction.MECHANISM,
                visual_requirement="coupe du moteur",
                estimated_duration_s=4.0,
            ),
            ScriptLine(
                index=2,
                text="Le couple est immédiat, sans explosion à attendre.",
                function=NarrativeFunction.PAYOFF,
                visual_requirement="chute",
                estimated_duration_s=3.0,
            ),
        ],
    }
    return ScriptState(**(payload | overrides))


def synthetic_lines(state: ScriptState, durations: list[float], tmp_path: Path):
    """Répliques adossées à de vrais fichiers WAV, de durées choisies."""
    measured = []
    for line, duration in zip(state.lines, durations, strict=True):
        path = write_wav(tone(duration), tmp_path / f"line-{line.index}.wav")
        measured.append(
            MeasuredLine(
                line=line,
                audio_path=path,
                measurement=measure_wav(path),
                engine="test-tone",
                engine_version="1.0",
                voice_fingerprint="tone@1",
            )
        )
    return measured


# ------------------------------------------- le critère de réussite, en entier


@needs_espeak
class TestIfTheTtsChangesTheTimelineChanges:
    def _timeline(self, rate: int, tmp_path: Path) -> VoiceTimeline:
        state = script()
        recorder = NarrationRecorder(espeak, VoiceSpec(voice_id="fr", rate_wpm=rate))
        outcome = recorder.record(script=state, into=tmp_path / f"r{rate}")
        return VoiceTimelineBuilder().build(
            script=state, measured=outcome.lines, out_path=tmp_path / f"v{rate}.wav"
        ).timeline

    def test_a_slower_engine_yields_a_longer_official_duration(self, tmp_path):
        fast = self._timeline(165, tmp_path)
        slow = self._timeline(110, tmp_path)
        assert slow.total_duration_s > fast.total_duration_s * 1.2

    def test_every_segment_moves_with_the_engine(self, tmp_path):
        fast = self._timeline(165, tmp_path)
        slow = self._timeline(110, tmp_path)
        for quick, lazy in zip(fast.segments, slow.segments, strict=True):
            assert lazy.duration_s > quick.duration_s

    def test_the_script_is_untouched_between_the_two(self, tmp_path):
        """Seul le TTS change : le script, lui, est identique."""
        first, second = script(), script()
        assert [line.text for line in first.lines] == [line.text for line in second.lines]
        assert first.estimated_total_s == second.estimated_total_s

    def test_the_official_duration_ignores_the_estimate(self, tmp_path):
        state = script()
        recorder = NarrationRecorder(espeak, VoiceSpec(voice_id="fr", rate_wpm=110))
        outcome = recorder.record(script=state, into=tmp_path / "lines")
        timeline = VoiceTimelineBuilder().build(
            script=state, measured=outcome.lines, out_path=tmp_path / "v.wav"
        ).timeline
        # 11 s estimées, bien davantage une fois dit à 110 mots/minute.
        assert state.estimated_total_s == pytest.approx(11.0)
        assert timeline.total_duration_s > 14.0

    def test_the_same_engine_twice_gives_the_same_timeline(self, tmp_path):
        """Reproductible : même moteur, mêmes réglages, mêmes durées."""
        first = self._timeline(165, tmp_path / "a")
        second = self._timeline(165, tmp_path / "b")
        assert [s.duration_s for s in first.segments] == [
            s.duration_s for s in second.segments
        ]
        assert first.total_duration_s == second.total_duration_s


# ------------------------------------- l'estimation ne peut pas prendre le pouvoir


class TestTheEstimateCanNeverBecomeAuthority:
    def test_no_audio_module_reads_the_estimate(self) -> None:
        """Garde structurelle : la chaîne audio ne *lit* jamais l'estimation.

        L'analyse porte sur l'arbre syntaxique, pas sur le texte : la prose a
        le droit de nommer le champ pour expliquer pourquoi elle l'ignore, le
        code n'a pas le droit d'y toucher — ni par attribut, ni par `getattr`.
        """
        field = "estimated_duration_s"
        offenders: list[str] = []
        for path in sorted(AUDIO_PACKAGE.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr == field:
                    offenders.append(f"{path.name}:{node.lineno} accède à .{field}")
                elif isinstance(node, ast.Constant) and node.value == field:
                    offenders.append(f"{path.name}:{node.lineno} nomme {field!r}")
        assert not offenders, (
            f"la chaîne audio touche à l'estimation : {offenders} — "
            "la durée officielle doit venir de la mesure, et d'elle seule"
        )

    def test_no_audio_module_imports_the_estimation_engine(self) -> None:
        offenders: list[str] = []
        for path in sorted(AUDIO_PACKAGE.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = None
                if isinstance(node, ast.ImportFrom) and node.module:
                    module = node.module
                elif isinstance(node, ast.Import):
                    module = node.names[0].name
                if module and "engines.script" in module:
                    offenders.append(f"{path.name} importe {module}")
        assert not offenders, offenders

    def test_the_builder_cannot_be_handed_an_estimate(self) -> None:
        """`MeasuredLine` n'a pas de champ de durée : seulement une mesure."""
        fields = set(MeasuredLine.__dataclass_fields__)
        assert "duration_s" not in fields
        assert "measurement" in fields

    def test_a_timeline_is_refused_unless_it_is_measured(self) -> None:
        """Une timeline bâtie sur des estimations est refusée par le contrat."""
        state = script()
        segments = [
            VoiceSegment(
                line_id=line.id,
                line_index=line.index,
                start_s=index * 4.0,
                end_s=index * 4.0 + 3.5,
            )
            for index, line in enumerate(state.lines)
        ]
        with pytest.raises(ValidationError, match="VOICE FIRST"):
            VoiceTimeline(
                script_state_id=state.id,
                audio_path="voice.wav",
                sample_rate=22050,
                total_duration_s=11.0,
                timing_source=TimingSource.ESTIMATED,
                segments=segments,
            )

    def test_the_same_timeline_measured_is_accepted(self) -> None:
        """Seule la provenance du timing change : c'est bien elle qui décide."""
        state = script()
        segments = [
            VoiceSegment(
                line_id=line.id,
                line_index=line.index,
                start_s=index * 4.0,
                end_s=index * 4.0 + 3.5,
            )
            for index, line in enumerate(state.lines)
        ]
        timeline = VoiceTimeline(
            script_state_id=state.id,
            audio_path="voice.wav",
            sample_rate=22050,
            total_duration_s=11.5,
            timing_source=TimingSource.MEASURED_TTS,
            segments=segments,
        )
        assert timeline.timing_source is TimingSource.MEASURED_TTS

    def test_the_builder_always_stamps_a_measured_source(self, tmp_path) -> None:
        state = script()
        built = VoiceTimelineBuilder().build(
            script=state,
            measured=synthetic_lines(state, [1.0, 2.0, 1.5], tmp_path),
            out_path=tmp_path / "v.wav",
        )
        assert built.timeline.timing_source is TimingSource.MEASURED_TTS

    def test_segments_follow_the_files_not_the_script(self, tmp_path) -> None:
        """Estimations identiques, fichiers différents → segments différents."""
        state = script()
        short = VoiceTimelineBuilder().build(
            script=state,
            measured=synthetic_lines(state, [0.5, 0.5, 0.5], tmp_path / "s"),
            out_path=tmp_path / "short.wav",
        ).timeline
        long = VoiceTimelineBuilder().build(
            script=state,
            measured=synthetic_lines(state, [3.0, 3.0, 3.0], tmp_path / "l"),
            out_path=tmp_path / "long.wav",
        ).timeline
        assert short.total_duration_s < long.total_duration_s
        assert [s.duration_s for s in short.segments] != [
            s.duration_s for s in long.segments
        ]


# ------------------------------------------------- refus explicites et journalisés


class TestTheBuilderRefusesRatherThanPatch:
    def test_a_partial_coverage_is_refused(self, tmp_path) -> None:
        state = script()
        partial = synthetic_lines(state, [1.0, 1.0, 1.0], tmp_path)[:2]
        with pytest.raises(DurationInconsistent, match="ne couvrent pas le script"):
            VoiceTimelineBuilder().build(
                script=state, measured=partial, out_path=tmp_path / "v.wav"
            )

    def test_no_line_at_all_is_refused(self, tmp_path) -> None:
        with pytest.raises(DurationInconsistent, match="aucune réplique"):
            VoiceTimelineBuilder().build(
                script=script(), measured=[], out_path=tmp_path / "v.wav"
            )

    def test_lines_out_of_order_are_refused(self, tmp_path) -> None:
        state = script()
        measured = synthetic_lines(state, [1.0, 1.0, 1.0], tmp_path)
        with pytest.raises(DurationInconsistent, match="désordre"):
            VoiceTimelineBuilder().build(
                script=state,
                measured=[measured[1], measured[0], measured[2]],
                out_path=tmp_path / "v.wav",
            )

    def test_a_line_from_another_script_is_refused(self, tmp_path) -> None:
        state = script()
        other = script()
        measured = synthetic_lines(state, [1.0, 1.0, 1.0], tmp_path)
        measured[1] = MeasuredLine(
            line=other.lines[1],
            audio_path=measured[1].audio_path,
            measurement=measured[1].measurement,
            engine="test-tone",
            engine_version="1.0",
            voice_fingerprint="tone@1",
        )
        with pytest.raises(DurationInconsistent, match="étrangères à ce script"):
            VoiceTimelineBuilder().build(
                script=state, measured=measured, out_path=tmp_path / "v.wav"
            )

    def test_a_silent_line_is_refused(self, tmp_path) -> None:
        state = script()
        measured = synthetic_lines(state, [1.0, 1.0, 1.0], tmp_path)
        mute = write_wav(silence(FORMAT, 1.0), tmp_path / "mute.wav")
        measured[1] = MeasuredLine(
            line=state.lines[1],
            audio_path=mute,
            measurement=measure_wav(mute),
            engine="test-tone",
            engine_version="1.0",
            voice_fingerprint="tone@1",
        )
        with pytest.raises(AudioSilent, match="réplique 1"):
            VoiceTimelineBuilder().build(
                script=state, measured=measured, out_path=tmp_path / "v.wav"
            )

    def test_two_engines_in_one_timeline_are_refused(self, tmp_path) -> None:
        state = script()
        measured = synthetic_lines(state, [1.0, 1.0, 1.0], tmp_path)
        measured[2] = MeasuredLine(
            line=state.lines[2],
            audio_path=measured[2].audio_path,
            measurement=measured[2].measurement,
            engine="un-autre-moteur",
            engine_version="9.9",
            voice_fingerprint="autre@1",
        )
        with pytest.raises(DurationInconsistent, match="moteurs ou des voix"):
            VoiceTimelineBuilder().build(
                script=state, measured=measured, out_path=tmp_path / "v.wav"
            )

    def test_a_format_change_mid_script_is_refused(self, tmp_path) -> None:
        state = script()
        measured = synthetic_lines(state, [1.0, 1.0, 1.0], tmp_path)
        other = AudioFormat(sample_rate=44100, channels=1, sample_width=2)
        odd = write_wav(tone(1.0, fmt=other), tmp_path / "odd.wav")
        measured[1] = MeasuredLine(
            line=state.lines[1],
            audio_path=odd,
            measurement=measure_wav(odd),
            engine="test-tone",
            engine_version="1.0",
            voice_fingerprint="tone@1",
        )
        with pytest.raises(Exception, match="assemblage impossible"):
            VoiceTimelineBuilder().build(
                script=state, measured=measured, out_path=tmp_path / "v.wav"
            )


class TestTheAssemblyIsVerified:
    def test_the_written_file_is_re_measured(self, tmp_path) -> None:
        state = script()
        built = VoiceTimelineBuilder().build(
            script=state,
            measured=synthetic_lines(state, [1.0, 2.0, 1.5], tmp_path),
            out_path=tmp_path / "v.wav",
        )
        on_disk = measure_wav(tmp_path / "v.wav")
        assert built.timeline.total_duration_s == pytest.approx(
            on_disk.duration_s, abs=1e-4
        )

    def test_the_total_is_the_sum_of_parts_and_pauses(self, tmp_path) -> None:
        state = script()
        built = VoiceTimelineBuilder().build(
            script=state,
            measured=synthetic_lines(state, [1.0, 2.0, 1.5], tmp_path),
            out_path=tmp_path / "v.wav",
        )
        speech = 1.0 + 2.0 + 1.5
        pauses = 0.45 + 0.30  # après l'accroche, après le mécanisme
        tail = 0.35
        assert built.timeline.total_duration_s == pytest.approx(
            speech + pauses + tail, abs=0.003
        )

    def test_segments_never_overlap_and_stay_inside(self, tmp_path) -> None:
        state = script()
        timeline = VoiceTimelineBuilder().build(
            script=state,
            measured=synthetic_lines(state, [1.0, 2.0, 1.5], tmp_path),
            out_path=tmp_path / "v.wav",
        ).timeline
        previous = 0.0
        for segment in timeline.segments:
            assert segment.start_s >= previous - 1e-9
            previous = segment.end_s
        assert previous <= timeline.total_duration_s

    def test_the_payoff_gets_no_trailing_pause(self, tmp_path) -> None:
        state = script()
        timeline = VoiceTimelineBuilder().build(
            script=state,
            measured=synthetic_lines(state, [1.0, 1.0, 1.0], tmp_path),
            out_path=tmp_path / "v.wav",
        ).timeline
        # Le dernier segment finit, puis il ne reste que le silence de queue.
        assert timeline.total_duration_s - timeline.segments[-1].end_s == pytest.approx(
            0.35, abs=0.003
        )
