"""Parcours phase 3 en ligne de commande : bible → découpage."""

from __future__ import annotations

import json

import pytest

from pdz2.cli.main import main
from pdz2.contracts.pipeline import Stage, StageStatus
from pdz2.contracts.script import ScriptState, VoiceTimeline
from pdz2.contracts.shots import ShotGraph
from pdz2.contracts.temporal import TemporalPlan
from pdz2.storage import EpisodeStore
from pdz2.tests import pipeline
from pdz2.tests.test_cli_phase1 import _fill, _research


def _episode_on_disk(tmp_path):
    """Épisode réel sur disque, mené jusqu'à la timeline mesurée."""
    from pdz2.contracts.direction import DirectorState
    from pdz2.contracts.research import ResearchState
    from pdz2.engines.script import ScriptCompiler

    episode = tmp_path / "ep"
    _research(episode)
    template = tmp_path / "template.json"
    main(["brief-template", "--episode", str(episode), "--out", str(template),
          "--max-proofs", "3"])
    store = EpisodeStore(episode)
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            _fill(json.loads(template.read_text(encoding="utf-8")),
                  store.load_as(ResearchState)),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    main(["direct", "--episode", str(episode), "--brief", str(brief_path)])

    # Voix et timeline : audio réel, durées choisies, sans dépendance système.
    script = ScriptCompiler().compile(
        director_state=store.load_as(DirectorState)
    ).state
    store.save(script)
    timeline = pipeline.synthesise(script, episode / "audio")
    store.save(timeline)

    machine_snapshot = store.load_snapshot()
    from pdz2.state import EpisodeStateMachine

    machine = EpisodeStateMachine.resume(machine_snapshot)
    for stage, artifact in (
        (Stage.SCRIPT, script.id),
        (Stage.VOICE, timeline.id),
        (Stage.TIMELINE, timeline.id),
    ):
        machine.start(stage)
        machine.complete(stage, artifact_ids=[artifact])
    store.save_snapshot(machine.snapshot)
    return episode, store


class TestBibleCommand:
    def test_it_compiles_and_advances_the_machine(self, tmp_path, capsys):
        episode, store = _episode_on_disk(tmp_path)
        capsys.readouterr()
        assert main(["bible", "--episode", str(episode)]) == 0
        out = capsys.readouterr().out
        assert "palette" in out
        assert store.exists("visual_bible")
        assert store.load_snapshot().state(Stage.VISUAL_BIBLE).status is StageStatus.DONE

    def test_it_says_when_the_style_was_not_decided(self, tmp_path, capsys):
        episode, _ = _episode_on_disk(tmp_path)
        capsys.readouterr()
        main(["bible", "--episode", str(episode)])
        assert "préréglage déclaré" in capsys.readouterr().out

    def test_it_needs_a_director_state(self, tmp_path, capsys):
        episode = tmp_path / "ep"
        _research(episode)
        capsys.readouterr()
        assert main(["bible", "--episode", str(episode)]) == 1
        assert "pas de réalisation" in capsys.readouterr().err


class TestShotsCommand:
    def _ready(self, tmp_path):
        episode, store = _episode_on_disk(tmp_path)
        main(["bible", "--episode", str(episode)])
        return episode, store

    def test_it_produces_the_plan_the_graph_and_the_cameras(self, tmp_path, capsys):
        episode, store = self._ready(tmp_path)
        capsys.readouterr()
        assert main(["shots", "--episode", str(episode)]) == 0
        out = capsys.readouterr().out
        assert "créneaux pavant" in out

        assert store.exists("temporal_plan")
        assert store.exists("shot_graph")
        graph = store.load_as(ShotGraph)
        cameras = store.load_collection("camera_program")
        assert len(cameras) == len(graph.shots)
        assert {shot.camera_program_id for shot in graph.shots} == {
            camera.id for camera in cameras
        }

    def test_the_graph_durations_match_the_measured_audio(self, tmp_path):
        episode, store = self._ready(tmp_path)
        main(["shots", "--episode", str(episode)])
        graph = store.load_as(ShotGraph)
        timeline = store.load_as(VoiceTimeline)
        assert graph.total_duration_s == pytest.approx(
            timeline.total_duration_s, abs=0.01
        )
        assert sum(shot.duration_s for shot in graph.shots) == pytest.approx(
            timeline.total_duration_s, abs=0.02
        )
        assert graph.voice_timeline_id == timeline.id

    def test_the_temporal_plan_carries_the_five_curves(self, tmp_path):
        episode, store = self._ready(tmp_path)
        main(["shots", "--episode", str(episode)])
        plan = store.load_as(TemporalPlan)
        for name in (
            "emotional_curve",
            "attention_curve",
            "information_curve",
            "motion_curve",
            "visual_novelty_curve",
        ):
            assert getattr(plan, name).points

    def test_every_shot_reloads_through_the_registry(self, tmp_path):
        episode, store = self._ready(tmp_path)
        main(["shots", "--episode", str(episode)])
        graph = store.load_as(ShotGraph)
        script = store.load_as(ScriptState)
        assert len(graph.shots) >= len(script.lines)
        for shot in graph.shots:
            assert shot.visual_subject

    def test_shots_before_the_bible_is_refused_by_the_graph(self, tmp_path, capsys):
        episode, _ = _episode_on_disk(tmp_path)
        capsys.readouterr()
        assert main(["shots", "--episode", str(episode)]) == 1
        assert "pas de visual_bible" in capsys.readouterr().err

    def test_a_broken_lineage_fails_the_stage_with_a_reason(self, tmp_path, capsys):
        """Une bible venue d'ailleurs est refusée, et le motif est journalisé."""
        episode, store = self._ready(tmp_path)
        stranger = pipeline.build_episode(tmp_path / "stranger")
        store.save(stranger.bible)
        capsys.readouterr()
        assert main(["shots", "--episode", str(episode)]) == 1
        assert "découpage refusé" in capsys.readouterr().err
        state = store.load_snapshot().state(Stage.SHOT_GRAPH)
        assert state.status is StageStatus.FAILED
        assert "bible visuelle" in state.detail


class TestPhasesReportsPhase3:
    def test_phase_3_is_marked_done(self, capsys):
        assert main(["phases"]) == 0
        out = capsys.readouterr().out
        assert "[x] Phase 3" in out
        assert "aucun fournisseur nommé" in out
