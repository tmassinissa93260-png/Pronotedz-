"""Schémas exportés et ligne de commande."""

from __future__ import annotations

import json
from pathlib import Path

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

    def test_create_stops_at_the_human_decision(self, tmp_path, capsys, monkeypatch) -> None:
        """`create` sans brief ni raisonneur prépare le gabarit et rend la main.

        C'est le seul arrêt volontaire de la chaîne : la thèse, le ton et le
        public sont des décisions qu'aucune mesure de ce système ne prend.
        """
        from pdz2.providers.registry import ANTHROPIC_KEY_ENV

        monkeypatch.delenv(ANTHROPIC_KEY_ENV, raising=False)
        corpus = Path(__file__).parent / "fixtures" / "corpus"
        code = main(
            [
                "create",
                "--episode", str(tmp_path / "ep"),
                "--topic", "Comment fonctionne une voiture électrique ?",
                "--corpus", str(corpus),
            ]
        )
        assert code == 3
        captured = capsys.readouterr()
        assert "aucun raisonneur n'est branché pour les décider" in captured.err
        assert (tmp_path / "ep" / "brief.json").is_file()

    def test_phases_reports_the_real_state_of_the_build(self, capsys) -> None:
        assert main(["phases"]) == 0
        out = capsys.readouterr().out
        # Une assertion sur « Phase 1 » seule passerait sur « Phase 11 » :
        # les douze lignes sont donc vérifiées entières.
        for number in range(13):
            assert f"[x] Phase {number} —" in out
        assert "[ ]" not in out

    def test_phases_still_declares_what_is_missing(self, capsys, monkeypatch) -> None:
        """Les phases faites ne veulent pas dire que tout est branché."""
        from pdz2.providers.registry import CREDENTIAL_ENV

        for name in CREDENTIAL_ENV.values():
            monkeypatch.delenv(name, raising=False)
        assert main(["phases"]) == 0
        out = capsys.readouterr().out
        assert "vidéo : aucun fournisseur génératif" in out
        assert "raisonneur : aucun" in out
        assert "sons : aucune bibliothèque implémentée" in out

    def test_phases_says_the_opposite_once_the_keys_are_there(
        self, capsys, monkeypatch
    ) -> None:
        """La même commande doit changer d'avis quand l'environnement change.

        Sans ce test jumeau, « rien n'est branché » pourrait rester une
        constante recopiée : la commande dirait toujours la même chose, vraie
        par hasard dans un dépôt nu et fausse partout ailleurs.
        """
        from pdz2.providers.registry import CREDENTIAL_ENV

        for name in CREDENTIAL_ENV.values():
            monkeypatch.setenv(name, "clé-de-test")
        assert main(["phases"]) == 0
        out = capsys.readouterr().out
        assert "vidéo : un fournisseur génératif" in out
        assert "raisonneur : branché" in out
        # Ce qui n'a pas d'adaptateur ne change jamais d'avis, clé ou pas.
        assert "sons : aucune bibliothèque implémentée" in out

    def test_capabilities_probes_the_real_environment(self, capsys) -> None:
        assert main(["capabilities"]) == 0
        out = capsys.readouterr().out
        assert "ffmpeg/libx264" in out
        assert "espeak-ng/fr" in out
        assert "n'en invente pas" in out

    def test_capabilities_writes_the_matrix_when_asked(self, tmp_path) -> None:
        from pdz2.storage import EpisodeStore

        assert main(["capabilities", "--episode", str(tmp_path / "ep")]) == 0
        # Les matrices s'accumulent : un instantané qu'on écrase n'en est plus un.
        assert EpisodeStore(tmp_path / "ep").latest("capability_matrix") is not None

    def test_costs_refuses_an_unmeasured_spend(self, tmp_path, capsys) -> None:
        from pdz2.contracts import Stage
        from pdz2.state import EpisodeStateMachine
        from pdz2.storage import EpisodeStore

        store = EpisodeStore(tmp_path / "ep")
        store.initialise()
        machine = EpisodeStateMachine.create(
            episode_id="ep-1", topic_request_id="topic_request-1", budget_cap_usd=2.0
        )
        machine.start(Stage.RESEARCH)
        machine.complete(Stage.RESEARCH)
        store.save_snapshot(machine.snapshot)

        assert main(["costs", "--episode", str(tmp_path / "ep")]) == 0
        assert store.exists("cost_ledger")

        code = main(
            [
                "costs",
                "--episode", str(tmp_path / "ep"),
                "--authorize", "5.0",
                "--stage", "render",
            ]
        )
        assert code == 1
        assert "REFUSÉ [would_exceed]" in capsys.readouterr().err

    def test_costs_reports_a_missing_episode(self, tmp_path, capsys) -> None:
        assert main(["costs", "--episode", str(tmp_path / "vide")]) == 1
        assert "aucun épisode" in capsys.readouterr().err

    def test_create_skips_a_stage_already_done(self, tmp_path, capsys) -> None:
        """Reprendre `create` après avoir rempli le brief ne rejoue rien.

        La machine à états refuse — à juste titre — de rejouer une étape faite
        sans rembobinage explicite. L'orchestrateur la saute donc, au lieu de
        buter dessus, et le dit à l'écran.
        """
        corpus = Path(__file__).parent / "fixtures" / "corpus"
        episode = tmp_path / "ep"
        arguments = [
            "create",
            "--episode", str(episode),
            "--topic", "Comment fonctionne une voiture électrique ?",
            "--corpus", str(corpus),
        ]
        assert main(arguments) == 3
        capsys.readouterr()
        # Deuxième passage, toujours sans brief rempli : la recherche est faite.
        assert main(arguments) == 3
        out = capsys.readouterr().out
        assert "pdz2 research — déjà fait, sauté" in out

    def test_the_orchestrator_covers_every_stage_of_the_graph(self) -> None:
        """Aucune étape du graphe ne peut être oubliée par `create`."""
        from pdz2.cli.orchestrate import STAGE_OF, STEPS
        from pdz2.contracts.pipeline import Stage

        commands = {"research", "direct"} | {name for name, _ in STEPS}
        covered = {STAGE_OF[name] for name in commands if name in STAGE_OF}
        # FINAL_QA et REPAIR sont franchies par `deliver` et par la boucle de
        # réparation, qui ne se déclenche que sur diagnostic.
        assert set(Stage) - covered == {Stage.FINAL_QA, Stage.REPAIR}

    def test_journal_refuses_an_episode_without_a_request(self, tmp_path, capsys) -> None:
        from pdz2.state import EpisodeStateMachine
        from pdz2.storage import EpisodeStore

        store = EpisodeStore(tmp_path / "ep")
        store.initialise()
        store.save_snapshot(
            EpisodeStateMachine.create(
                episode_id="ep-1", topic_request_id="topic_request-1"
            ).snapshot
        )
        assert main(["journal", "--episode", str(tmp_path / "ep")]) == 1
        assert "rien à raconter" in capsys.readouterr().err

    def test_a_missing_subcommand_is_an_error(self) -> None:
        with pytest.raises(SystemExit):
            build_parser().parse_args([])
