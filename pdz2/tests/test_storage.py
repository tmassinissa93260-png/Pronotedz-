"""Persistance : disposition, écriture atomique, reprise."""

from __future__ import annotations

import json

import pytest

from pdz2.contracts import Stage
from pdz2.state import EpisodeStateMachine
from pdz2.storage import EpisodeLayout, EpisodeStore
from pdz2.tests import factories


class TestLayout:
    def test_singletons_land_at_the_root(self) -> None:
        assert EpisodeLayout.relative_path("director_state") == "director_state.json"
        assert EpisodeLayout.relative_path("research_state") == "research.json"
        assert EpisodeLayout.relative_path("episode_snapshot") == "state.json"

    def test_collections_land_in_their_directory(self) -> None:
        path = EpisodeLayout.relative_path("motion_program", "motion_program-7")
        assert path == "motion_programs/motion_program-7.json"

    def test_a_collection_without_an_id_is_refused(self) -> None:
        with pytest.raises(ValueError, match="produit en série"):
            EpisodeLayout.relative_path("render_artifact")

    def test_an_unknown_contract_has_no_place(self) -> None:
        with pytest.raises(KeyError):
            EpisodeLayout.relative_path("pas_un_contrat")

    def test_the_expected_directories_are_declared(self) -> None:
        directories = EpisodeLayout.directories()
        for expected in (
            "assets",
            "renders",
            "observations",
            "repairs",
            "subtitles",
            "render_specs",
            "execution_plans",
            "motion_programs",
        ):
            assert expected in directories


class TestEpisodeStore:
    def test_initialise_creates_the_tree(self, tmp_path) -> None:
        store = EpisodeStore(tmp_path / "ep")
        root = store.initialise()
        for name in EpisodeLayout.directories():
            assert (root / name).is_dir()

    def test_save_and_load_a_singleton(self, tmp_path) -> None:
        store = EpisodeStore(tmp_path / "ep")
        store.initialise()
        state = factories.director_state()
        path = store.save(state)
        assert path.name == "director_state.json"
        assert store.load_as(type(state)) == state

    def test_save_and_load_a_collection_item(self, tmp_path) -> None:
        store = EpisodeStore(tmp_path / "ep")
        store.initialise()
        program = factories.motion_program()
        store.save(program)
        assert store.load("motion_program", program.id) == program

    def test_load_collection_filters_by_type(self, tmp_path) -> None:
        store = EpisodeStore(tmp_path / "ep")
        store.initialise()
        program = factories.motion_program()
        camera = factories.camera_program()
        store.save(program)
        store.save(camera)  # même dossier, type différent
        loaded = store.load_collection("motion_program")
        assert [item.id for item in loaded] == [program.id]

    def test_written_json_is_readable_by_hand(self, tmp_path) -> None:
        store = EpisodeStore(tmp_path / "ep")
        store.initialise()
        state = factories.director_state()
        path = store.save(state)
        text = path.read_text(encoding="utf-8")
        assert text.endswith("\n")
        payload = json.loads(text)
        assert payload["contract_type"] == "director_state"
        assert "thèse" not in text  # accents non échappés, mais pas de mojibake
        assert "é" in text or "è" in text

    def test_no_temporary_file_survives_a_write(self, tmp_path) -> None:
        store = EpisodeStore(tmp_path / "ep")
        store.initialise()
        store.save(factories.director_state())
        leftovers = [p.name for p in store.root.iterdir() if p.name.startswith(".")]
        assert leftovers == []

    def test_load_as_refuses_the_wrong_type(self, tmp_path) -> None:
        from pdz2.contracts import ScriptState

        store = EpisodeStore(tmp_path / "ep")
        store.initialise()
        store.save(factories.director_state())
        with pytest.raises(FileNotFoundError):
            store.load_as(ScriptState)


class TestResume:
    def test_an_interrupted_episode_resumes_from_disk(self, tmp_path) -> None:
        store = EpisodeStore(tmp_path / "ep")
        store.initialise()

        machine = EpisodeStateMachine.create(
            episode_id="ep-1", topic_request_id="topic_request-1", budget_cap_usd=5.0
        )
        machine.start(Stage.RESEARCH)
        machine.complete(Stage.RESEARCH, cost_usd=0.3)
        store.save_snapshot(machine.snapshot)

        # Nouveau processus : on ne connaît que le dossier.
        reopened = EpisodeStore(tmp_path / "ep")
        assert reopened.has_snapshot()
        resumed = EpisodeStateMachine.resume(reopened.load_snapshot())
        assert resumed.spent_usd == pytest.approx(0.3)
        assert Stage.DIRECTION in resumed.ready_stages()
        assert len(resumed.transitions) == 2

    def test_missing_snapshot_is_reported(self, tmp_path) -> None:
        store = EpisodeStore(tmp_path / "ep")
        store.initialise()
        assert store.has_snapshot() is False
