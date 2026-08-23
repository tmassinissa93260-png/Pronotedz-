"""Parcours complet en ligne de commande : recherche → brief → réalisation."""

from __future__ import annotations

import json

from pdz2.cli.main import main
from pdz2.contracts.pipeline import Stage, StageStatus
from pdz2.contracts.research import ResearchState
from pdz2.storage import EpisodeStore
from pdz2.tests.fixtures import CORPUS

TOPIC = "Comment fonctionne une voiture électrique ?"


def _research(episode, duration: float = 45.0) -> int:
    return main(
        [
            "research",
            "--episode", str(episode),
            "--topic", TOPIC,
            "--corpus", str(CORPUS),
            "--duration", str(duration),
        ]
    )


def _fill(template: dict, research: ResearchState) -> dict:
    """Remplit un gabarit comme le ferait un rédacteur."""
    filled = json.loads(json.dumps(template))
    filled["thesis"] = "Une voiture électrique convertit de l'énergie en rotation."
    filled["ending_payoff"] = "Le couple est immédiat, sans explosion à attendre."
    filled["visual_language"]["visual_register"] = "coupe technique transparente"
    filled["anchors"][0].update(
        name="moteur-coupe",
        canonical_description="Moteur synchrone en coupe, carter bleu nuit.",
    )
    filled["anchors"][0]["identity"][0].update(name="carter", value="bleu nuit mat")
    for proof in filled["visual_proofs"]:
        proof.update(
            causal_mechanism="Le courant crée un champ qui met le rotor en rotation.",
            evidence_required="Voir l'énergie entrer et la rotation sortir.",
            visual_proof="Coupe transparente : le courant circule, puis l'arbre tourne.",
            anchor_names=["moteur-coupe"],
            acknowledged_dispute=True,
        )
    return filled


class TestResearchCommand:
    def test_it_creates_the_episode_and_advances_the_machine(self, tmp_path, capsys):
        episode = tmp_path / "ep"
        assert _research(episode) == 0
        out = capsys.readouterr().out
        assert "local_corpus : available" in out
        assert "couverture du sujet" in out

        store = EpisodeStore(episode)
        assert store.exists("topic_request")
        assert store.exists("research_state")
        snapshot = store.load_snapshot()
        assert snapshot.state(Stage.RESEARCH).status is StageStatus.DONE
        assert snapshot.state(Stage.RESEARCH).artifact_ids

    def test_the_written_state_reloads_through_the_registry(self, tmp_path):
        episode = tmp_path / "ep"
        _research(episode)
        research = EpisodeStore(episode).load_as(ResearchState)
        assert research.claims and research.fact_graph.edges

    def test_an_empty_corpus_fails_the_stage_with_a_reason(self, tmp_path, capsys):
        episode = tmp_path / "ep"
        code = main(
            [
                "research",
                "--episode", str(episode),
                "--topic", TOPIC,
                "--corpus", str(tmp_path / "vide"),
            ]
        )
        assert code == 1
        assert "recherche impossible" in capsys.readouterr().err
        snapshot = EpisodeStore(episode).load_snapshot()
        state = snapshot.state(Stage.RESEARCH)
        assert state.status is StageStatus.FAILED
        assert "introuvable" in state.detail

    def test_rerunning_a_done_stage_is_refused(self, tmp_path, capsys):
        episode = tmp_path / "ep"
        _research(episode)
        capsys.readouterr()
        assert _research(episode) == 1
        assert "rembobiner" in capsys.readouterr().err


class TestBriefTemplateCommand:
    def test_it_writes_a_template_to_fill(self, tmp_path, capsys):
        episode = tmp_path / "ep"
        _research(episode)
        target = tmp_path / "brief.json"
        assert main(
            ["brief-template", "--episode", str(episode), "--out", str(target)]
        ) == 0
        template = json.loads(target.read_text(encoding="utf-8"))
        assert template["thesis"] == ""
        assert template["visual_proofs"]
        assert all("_claim_text" in proof for proof in template["visual_proofs"])

    def test_it_needs_a_research_state(self, tmp_path, capsys):
        assert main(["brief-template", "--episode", str(tmp_path / "vide")]) == 1
        assert "pas de recherche" in capsys.readouterr().err


class TestDirectCommand:
    def _prepared(self, tmp_path) -> tuple:
        episode = tmp_path / "ep"
        _research(episode)
        template_path = tmp_path / "template.json"
        main(["brief-template", "--episode", str(episode), "--out", str(template_path),
              "--max-proofs", "3"])
        store = EpisodeStore(episode)
        template = json.loads(template_path.read_text(encoding="utf-8"))
        brief_path = tmp_path / "brief.json"
        brief_path.write_text(
            json.dumps(_fill(template, store.load_as(ResearchState)), ensure_ascii=False),
            encoding="utf-8",
        )
        return episode, brief_path, store

    def test_it_compiles_a_filled_brief(self, tmp_path, capsys):
        episode, brief_path, store = self._prepared(tmp_path)
        capsys.readouterr()
        assert main(["direct", "--episode", str(episode), "--brief", str(brief_path)]) == 0
        out = capsys.readouterr().out
        assert "plans" in out

        assert store.exists("director_brief")
        assert store.exists("director_state")
        snapshot = store.load_snapshot()
        assert snapshot.state(Stage.DIRECTION).status is StageStatus.DONE

    def test_the_director_state_descends_from_the_brief(self, tmp_path):
        from pdz2.contracts.direction import DirectorState
        from pdz2.engines.direction import DirectorBrief

        episode, brief_path, store = self._prepared(tmp_path)
        main(["direct", "--episode", str(episode), "--brief", str(brief_path)])
        state = store.load_as(DirectorState)
        brief = store.load_as(DirectorBrief)
        assert state.parent_id == brief.id

    def test_an_unfilled_template_is_refused(self, tmp_path, capsys):
        episode = tmp_path / "ep"
        _research(episode)
        template_path = tmp_path / "template.json"
        main(["brief-template", "--episode", str(episode), "--out", str(template_path)])
        capsys.readouterr()
        assert main(
            ["direct", "--episode", str(episode), "--brief", str(template_path)]
        ) == 1
        error = capsys.readouterr().err
        assert "brief invalide" in error
        assert "gabarit non rempli est refusé" in error

    def test_it_needs_a_research_state(self, tmp_path, capsys):
        assert main(
            ["direct", "--episode", str(tmp_path / "vide"), "--brief", "x.json"]
        ) == 1
        assert "pas de recherche" in capsys.readouterr().err


class TestCreateStillRefuses:
    def test_create_names_the_commands_that_do_work(self, capsys):
        assert main(["create", "--topic", TOPIC]) == 2
        error = capsys.readouterr().err
        assert "pdz2 research" in error
        assert "pdz2 direct" in error


class TestPhasesReportsReality:
    def test_phase_1_is_marked_done_with_its_limit(self, capsys):
        assert main(["phases"]) == 0
        out = capsys.readouterr().out
        assert "[x] Phase 1" in out
        assert "aucun raisonneur branché" in out
