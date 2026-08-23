"""Parcours phase 2 en ligne de commande : script → voix → timeline."""

from __future__ import annotations

import json

import pytest

from pdz2.audio import EspeakSynthesiser, measure_wav
from pdz2.cli.main import main
from pdz2.contracts.enums import ArtifactKind
from pdz2.contracts.pipeline import Stage, StageStatus
from pdz2.contracts.script import ScriptState, TimingSource, VoiceTimeline
from pdz2.storage import EpisodeStore
from pdz2.tests.test_cli_phase1 import _fill, _research

needs_espeak = pytest.mark.skipif(
    not EspeakSynthesiser().get_capabilities().usable,
    reason="binaire espeak-ng absent : installer le paquet système « espeak-ng »",
)


def _directed(tmp_path):
    """Épisode mené jusqu'au DirectorState."""
    episode = tmp_path / "ep"
    _research(episode)
    template_path = tmp_path / "template.json"
    main(["brief-template", "--episode", str(episode), "--out", str(template_path),
          "--max-proofs", "3"])
    store = EpisodeStore(episode)
    from pdz2.contracts.research import ResearchState

    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            _fill(json.loads(template_path.read_text(encoding="utf-8")),
                  store.load_as(ResearchState)),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    main(["direct", "--episode", str(episode), "--brief", str(brief_path)])
    return episode, store


class TestScriptCommand:
    def test_it_compiles_and_advances_the_machine(self, tmp_path, capsys):
        episode, store = _directed(tmp_path)
        capsys.readouterr()
        assert main(["script", "--episode", str(episode)]) == 0
        out = capsys.readouterr().out
        assert "ESTIMÉE" in out
        assert store.exists("script_state")
        assert store.load_snapshot().state(Stage.SCRIPT).status is StageStatus.DONE

    def test_it_needs_a_director_state(self, tmp_path, capsys):
        episode = tmp_path / "ep"
        _research(episode)
        capsys.readouterr()
        assert main(["script", "--episode", str(episode)]) == 1
        assert "pas de DirectorState" in capsys.readouterr().err

    def test_an_unknown_episode_is_reported(self, tmp_path, capsys):
        assert main(["script", "--episode", str(tmp_path / "vide")]) == 1
        assert "aucun épisode" in capsys.readouterr().err


@needs_espeak
class TestVoiceCommand:
    def _scripted(self, tmp_path):
        episode, store = _directed(tmp_path)
        main(["script", "--episode", str(episode)])
        return episode, store

    def test_it_synthesises_one_file_per_line(self, tmp_path, capsys):
        episode, store = self._scripted(tmp_path)
        capsys.readouterr()
        assert main(["voice", "--episode", str(episode)]) == 0

        script = store.load_as(ScriptState)
        files = sorted((episode / "audio" / "lines").glob("*.wav"))
        assert len(files) == len(script.lines)
        for path in files:
            assert measure_wav(path).duration_s > 0.1

    def test_it_records_one_artifact_per_line(self, tmp_path, capsys):
        episode, store = self._scripted(tmp_path)
        capsys.readouterr()
        main(["voice", "--episode", str(episode)])

        script = store.load_as(ScriptState)
        artifacts = [
            artifact
            for artifact in store.load_collection("render_artifact")
            if artifact.kind is ArtifactKind.AUDIO
        ]
        assert len(artifacts) == len(script.lines)
        line_ids = {line.id for line in script.lines}
        assert {artifact.source_contract_id for artifact in artifacts} == line_ids
        for artifact in artifacts:
            assert artifact.duration_s and artifact.duration_s > 0
            assert len(artifact.sha256) == 64

    def test_the_measured_durations_are_printed_beside_the_estimates(
        self, tmp_path, capsys
    ):
        episode, _ = self._scripted(tmp_path)
        capsys.readouterr()
        main(["voice", "--episode", str(episode)])
        out = capsys.readouterr().out
        assert "durées MESURÉES par réplique" in out
        assert "estimation" in out

    def test_it_needs_a_script(self, tmp_path, capsys):
        episode, _ = _directed(tmp_path)
        capsys.readouterr()
        assert main(["voice", "--episode", str(episode)]) == 1
        assert "pas de script" in capsys.readouterr().err


@needs_espeak
class TestTimelineCommand:
    def _voiced(self, tmp_path, rate: int = 165):
        episode, store = _directed(tmp_path)
        main(["script", "--episode", str(episode)])
        main(["voice", "--episode", str(episode), "--rate", str(rate)])
        return episode, store

    def test_it_builds_the_official_timeline(self, tmp_path, capsys):
        episode, store = self._voiced(tmp_path)
        capsys.readouterr()
        assert main(["timeline", "--episode", str(episode)]) == 0
        out = capsys.readouterr().out
        assert "durée OFFICIELLE" in out

        timeline = store.load_as(VoiceTimeline)
        assert timeline.timing_source is TimingSource.MEASURED_TTS
        assert (episode / "voice.wav").is_file()
        on_disk = measure_wav(episode / "voice.wav")
        assert timeline.total_duration_s == pytest.approx(on_disk.duration_s, abs=1e-3)
        assert store.load_snapshot().state(Stage.TIMELINE).status is StageStatus.DONE

    def test_the_timeline_covers_every_line(self, tmp_path):
        episode, store = self._voiced(tmp_path)
        main(["timeline", "--episode", str(episode)])
        script = store.load_as(ScriptState)
        timeline = store.load_as(VoiceTimeline)
        assert [segment.line_index for segment in timeline.segments] == [
            line.index for line in script.lines
        ]

    def test_a_tampered_audio_file_is_refused_and_journalled(self, tmp_path, capsys):
        """Le fichier fait autorité : s'il change, la timeline le refuse."""
        from pdz2.audio import silence, write_wav
        from pdz2.audio.wave_io import AudioFormat

        episode, store = self._voiced(tmp_path)
        victim = sorted((episode / "audio" / "lines").glob("*.wav"))[1]
        write_wav(
            silence(AudioFormat(sample_rate=22050, channels=1, sample_width=2), 9.0),
            victim,
        )
        capsys.readouterr()
        assert main(["timeline", "--episode", str(episode)]) == 1
        assert "le fichier a changé" in capsys.readouterr().err

        state = store.load_snapshot().state(Stage.TIMELINE)
        assert state.status is StageStatus.FAILED
        assert "le fichier a changé" in state.detail

    def test_a_missing_audio_file_is_refused(self, tmp_path, capsys):
        episode, store = self._voiced(tmp_path)
        sorted((episode / "audio" / "lines").glob("*.wav"))[0].unlink()
        capsys.readouterr()
        assert main(["timeline", "--episode", str(episode)]) == 1
        assert "absent" in capsys.readouterr().err
        assert store.load_snapshot().state(Stage.TIMELINE).status is StageStatus.FAILED

    def test_timeline_without_voice_is_refused_by_the_graph(self, tmp_path, capsys):
        """VOICE FIRST est tenu par le graphe, avant même le code applicatif.

        Il n'y a pas de chemin où une timeline se construirait sans audio :
        l'étape ne démarre pas, donc la question ne se pose jamais.
        """
        episode, _ = _directed(tmp_path)
        main(["script", "--episode", str(episode)])
        capsys.readouterr()
        assert main(["timeline", "--episode", str(episode)]) == 1
        error = capsys.readouterr().err
        assert "étapes amont non abouties" in error
        assert "voice" in error


@needs_espeak
class TestTheEngineDrivesTheOfficialDuration:
    """Le critère de réussite, vu depuis la ligne de commande."""

    def test_two_engine_settings_give_two_timelines(self, tmp_path):
        durations = {}
        for rate in (165, 110):
            root = tmp_path / f"run{rate}"
            root.mkdir()
            episode, store = _directed(root)
            main(["script", "--episode", str(episode)])
            main(["voice", "--episode", str(episode), "--rate", str(rate)])
            main(["timeline", "--episode", str(episode)])
            script = store.load_as(ScriptState)
            durations[rate] = (
                store.load_as(VoiceTimeline).total_duration_s,
                script.estimated_total_s,
            )
        fast_official, fast_estimate = durations[165]
        slow_official, slow_estimate = durations[110]
        # Le script — donc l'estimation — est identique dans les deux passes.
        assert fast_estimate == pytest.approx(slow_estimate)
        # La durée officielle, elle, suit le moteur.
        assert slow_official > fast_official * 1.2


class TestPhasesReportsPhase2:
    def test_phase_2_is_marked_done_with_its_engine(self, capsys):
        assert main(["phases"]) == 0
        out = capsys.readouterr().out
        assert "[x] Phase 2" in out
        assert "mesurées sur l'audio" in out
        assert "[ ] Phase 3" in out
