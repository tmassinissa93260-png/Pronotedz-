"""Schémas exportés et ligne de commande."""

from __future__ import annotations

import json

import pytest

from pdz2.cli.main import build_parser, main
from pdz2.contracts.versioning import registry
from pdz2.schemas import SCHEMA_DIR, check_up_to_date, export_all, schema_filename, schema_for


class TestSchemas:
    def test_every_contract_has_an_exported_schema(self) -> None:
        for contract_type in registry.types():
            path = SCHEMA_DIR / schema_filename(contract_type)
            assert path.is_file(), f"schéma manquant pour {contract_type.CONTRACT_NAME}"

    def test_the_checked_in_schemas_match_the_code(self) -> None:
        problems = check_up_to_date()
        assert not problems, problems + ["relancer : pdz2 schemas export"]

    def test_a_schema_carries_its_identity(self) -> None:
        contract_type = registry.get("director_state")
        schema = schema_for(contract_type)
        assert schema["$id"] == "pdz2:director_state/1.0.0"

    def test_export_is_idempotent(self, tmp_path) -> None:
        first = export_all(tmp_path)
        digests = {p.name: p.read_bytes() for p in first}
        second = export_all(tmp_path)
        assert {p.name: p.read_bytes() for p in second} == digests

    def test_export_removes_orphan_schemas(self, tmp_path) -> None:
        (tmp_path / "vieux_contrat-0.1.0.json").write_text("{}", encoding="utf-8")
        export_all(tmp_path)
        assert not (tmp_path / "vieux_contrat-0.1.0.json").exists()

    def test_check_reports_a_stale_schema(self, tmp_path) -> None:
        export_all(tmp_path)
        target = next(tmp_path.glob("*.json"))
        target.write_text("{}\n", encoding="utf-8")
        problems = check_up_to_date(tmp_path)
        assert any("périmé" in problem for problem in problems)


class TestCli:
    def test_contracts_list_prints_every_contract(self, capsys) -> None:
        assert main(["contracts", "list"]) == 0
        out = capsys.readouterr().out
        for name in registry.names():
            assert name in out

    def test_contracts_schema_prints_json(self, capsys) -> None:
        assert main(["contracts", "schema", "shot_spec"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["$id"] == "pdz2:shot_spec/1.0.0"

    def test_contracts_schema_reports_an_unknown_name(self, capsys) -> None:
        assert main(["contracts", "schema", "pas_un_contrat"]) == 1
        assert "inconnu" in capsys.readouterr().err

    def test_schemas_check_passes_on_a_clean_tree(self, capsys) -> None:
        assert main(["schemas", "check"]) == 0

    def test_state_graph_lists_the_stages(self, capsys) -> None:
        assert main(["state", "graph"]) == 0
        out = capsys.readouterr().out
        assert "research" in out
        assert "delivery" in out
        assert "barré-validation" in out

    def test_state_show_reads_an_episode(self, tmp_path, capsys) -> None:
        from pdz2.contracts import Stage
        from pdz2.state import EpisodeStateMachine
        from pdz2.storage import EpisodeStore

        store = EpisodeStore(tmp_path / "ep")
        store.initialise()
        machine = EpisodeStateMachine.create(
            episode_id="ep-1", topic_request_id="topic_request-1"
        )
        machine.start(Stage.RESEARCH)
        machine.complete(Stage.RESEARCH)
        store.save_snapshot(machine.snapshot)

        assert main(["state", "show", str(tmp_path / "ep")]) == 0
        out = capsys.readouterr().out
        assert "ep-1" in out
        assert "[x] research" in out
        assert "[.] delivery" in out

    def test_state_show_reports_a_missing_episode(self, tmp_path, capsys) -> None:
        assert main(["state", "show", str(tmp_path / "vide")]) == 1
        assert "aucun état" in capsys.readouterr().err

    def test_create_refuses_instead_of_pretending(self, capsys) -> None:
        code = main(["create", "--topic", "Comment fonctionne une voiture électrique ?"])
        assert code == 2
        assert "ne sait pas encore produire" in capsys.readouterr().err

    def test_phases_reports_the_real_state_of_the_build(self, capsys) -> None:
        assert main(["phases"]) == 0
        out = capsys.readouterr().out
        assert "[x] Phase 0" in out
        assert "[ ] Phase 1" in out

    def test_a_missing_subcommand_is_an_error(self) -> None:
        with pytest.raises(SystemExit):
            build_parser().parse_args([])
