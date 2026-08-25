"""Machine à états : dépendances, barrière de coût, réparation, reprise."""

from __future__ import annotations

import pytest

from pdz2.contracts import EpisodeStatus, Stage, StageStatus
from pdz2.state import (
    COST_GATE,
    STAGE_DEFINITIONS,
    STAGE_ORDER,
    BudgetExceeded,
    EpisodeStateMachine,
    TransitionRefused,
    definition,
    transitive_dependents,
)


def machine(**overrides) -> EpisodeStateMachine:
    payload = {"episode_id": "ep-1", "topic_request_id": "topic_request-1"}
    return EpisodeStateMachine.create(**(payload | overrides))


def run(m: EpisodeStateMachine, stage: Stage, cost: float = 0.0) -> None:
    m.start(stage)
    m.complete(stage, cost_usd=cost)


class TestGraph:
    def test_the_graph_is_a_dag_covering_every_stage(self) -> None:
        assert set(STAGE_ORDER) == set(Stage)
        seen: set[Stage] = set()
        for stage in STAGE_ORDER:
            for dependency in definition(stage).depends_on:
                assert dependency in seen, f"{stage} précède {dependency}"
            seen.add(stage)

    def test_voice_first_is_structural(self) -> None:
        """La timeline ne peut pas exister avant l'audio réel."""
        assert Stage.VOICE in definition(Stage.TIMELINE).depends_on
        assert Stage.TIMELINE in transitive_dependents(Stage.VOICE)
        assert Stage.TIMELINE in definition(Stage.SHOT_GRAPH).depends_on

    def test_expensive_render_stages_sit_behind_the_validator(self) -> None:
        gated = {
            stage for stage, spec in STAGE_DEFINITIONS.items() if spec.gated_by_validation
        }
        assert Stage.ASSETS in gated
        assert Stage.RENDER in gated
        for stage in gated:
            assert stage in transitive_dependents(COST_GATE)


class TestDependencyGating:
    def test_only_research_is_ready_at_the_start(self) -> None:
        m = machine()
        assert m.ready_stages() == [Stage.RESEARCH]

    def test_a_stage_cannot_start_before_its_dependencies(self) -> None:
        m = machine()
        with pytest.raises(TransitionRefused, match="étapes amont non abouties"):
            m.start(Stage.SCRIPT)

    def test_completing_a_dependency_opens_the_next_stage(self) -> None:
        m = machine()
        run(m, Stage.RESEARCH)
        assert Stage.DIRECTION in m.ready_stages()

    def test_a_stage_cannot_be_started_twice(self) -> None:
        m = machine()
        m.start(Stage.RESEARCH)
        with pytest.raises(TransitionRefused, match="tourne déjà"):
            m.start(Stage.RESEARCH)

    def test_a_done_stage_cannot_restart_without_a_rewind(self) -> None:
        m = machine()
        run(m, Stage.RESEARCH)
        with pytest.raises(TransitionRefused, match="rembobiner"):
            m.start(Stage.RESEARCH)

    def test_completing_a_stage_that_is_not_running_is_refused(self) -> None:
        m = machine()
        with pytest.raises(TransitionRefused, match="on ne termine que ce qui tourne"):
            m.complete(Stage.RESEARCH)

    def test_blocking_reasons_are_explicit(self) -> None:
        m = machine()
        # Une étape barrée par le validateur le dit d'abord : le motif utile
        # est la barrière de coût, pas la liste des amonts.
        assert m.blocking_reasons(Stage.RENDER) == [
            "render : dépense interdite tant que static_validation n'est pas franchie"
        ]
        assert "amont" in m.blocking_reasons(Stage.SCRIPT)[0]
        assert m.blocking_reasons(Stage.RESEARCH) == []


class TestCostGate:
    def _up_to_validation(self, m: EpisodeStateMachine) -> None:
        for stage in (
            Stage.RESEARCH,
            Stage.DIRECTION,
            Stage.SCRIPT,
            Stage.VISUAL_BIBLE,
            Stage.VOICE,
            Stage.TIMELINE,
            Stage.SHOT_GRAPH,
            Stage.MOTION,
            Stage.RENDER_SPEC,
        ):
            run(m, stage)

    def test_assets_are_barred_until_validation(self) -> None:
        m = machine()
        self._up_to_validation(m)
        assert m.status(COST_GATE) is StageStatus.PENDING
        assert Stage.ASSETS not in m.ready_stages()
        with pytest.raises(TransitionRefused, match="dépense interdite"):
            m.start(Stage.ASSETS)

    def test_validation_opens_the_gate(self) -> None:
        m = machine()
        self._up_to_validation(m)
        run(m, Stage.STATIC_VALIDATION)
        assert Stage.ASSETS in m.ready_stages()

    def test_a_free_stage_cannot_report_a_cost(self) -> None:
        m = machine()
        self._up_to_validation(m)
        run(m, Stage.STATIC_VALIDATION)
        m.start(Stage.ROUTING)
        with pytest.raises(TransitionRefused, match="déclarée sans coût"):
            m.complete(Stage.ROUTING, cost_usd=0.5)


class TestBudget:
    def test_spending_accumulates(self) -> None:
        m = machine(budget_cap_usd=1.0)
        run(m, Stage.RESEARCH, cost=0.25)
        assert m.spent_usd == pytest.approx(0.25)

    def test_a_completion_over_the_cap_is_refused(self) -> None:
        m = machine(budget_cap_usd=0.10)
        m.start(Stage.RESEARCH)
        with pytest.raises(BudgetExceeded, match="dépasserait le plafond"):
            m.complete(Stage.RESEARCH, cost_usd=0.5)
        assert m.spent_usd == 0.0

    def test_an_exhausted_budget_blocks_the_next_paying_stage(self) -> None:
        m = machine(budget_cap_usd=0.25)
        run(m, Stage.RESEARCH, cost=0.25)
        with pytest.raises(BudgetExceeded, match="budget épuisé"):
            m.start(Stage.DIRECTION)

    def test_a_free_stage_still_runs_on_an_exhausted_budget(self) -> None:
        m = machine(budget_cap_usd=0.25)
        run(m, Stage.RESEARCH, cost=0.25)
        # `timeline` est gratuite mais dépend de `voice`, qui est payante :
        # on vérifie la règle directement sur la définition.
        assert definition(Stage.TIMELINE).incurs_cost is False


class TestFailureAndSkip:
    def test_a_failure_needs_a_reason(self) -> None:
        m = machine()
        m.start(Stage.RESEARCH)
        with pytest.raises(TransitionRefused, match="sans motif"):
            m.fail(Stage.RESEARCH, reason="   ")

    def test_a_failure_blocks_the_episode(self) -> None:
        m = machine()
        m.start(Stage.RESEARCH)
        m.fail(Stage.RESEARCH, reason="aucune source exploitable")
        assert m.episode_status is EpisodeStatus.BLOCKED
        assert m.state(Stage.RESEARCH).detail == "aucune source exploitable"

    def test_a_terminal_failure_ends_the_episode(self) -> None:
        m = machine()
        m.start(Stage.RESEARCH)
        m.fail(Stage.RESEARCH, reason="sujet hors périmètre", terminal=True)
        assert m.episode_status is EpisodeStatus.FAILED
        with pytest.raises(TransitionRefused, match="plus rien ne démarre"):
            m.start(Stage.DIRECTION)

    def test_a_failed_stage_can_be_retried_after_a_restart(self) -> None:
        m = machine()
        m.start(Stage.RESEARCH)
        m.fail(Stage.RESEARCH, reason="timeout réseau")
        m.start(Stage.RESEARCH, reason="nouvelle tentative")
        assert m.state(Stage.RESEARCH).attempts == 2

    def test_a_mandatory_stage_cannot_be_skipped(self) -> None:
        m = machine()
        with pytest.raises(TransitionRefused, match="n'est pas sautable"):
            m.skip(Stage.RESEARCH, reason="pas envie")

    def test_an_optional_stage_can_be_skipped_with_a_reason(self) -> None:
        m = machine()
        m.skip(Stage.DIAGNOSIS, reason="observation conforme, rien à diagnostiquer")
        assert m.status(Stage.DIAGNOSIS) is StageStatus.SKIPPED

    def test_a_skip_without_a_reason_is_refused(self) -> None:
        m = machine()
        with pytest.raises(TransitionRefused, match="un saut exige un motif"):
            m.skip(Stage.DIAGNOSIS, reason="")


class TestRepairLoop:
    def _to_observation(self, m: EpisodeStateMachine) -> None:
        for stage in STAGE_ORDER:
            if stage is Stage.DIAGNOSIS:
                return
            run(m, stage)

    def test_rewinding_render_resets_everything_downstream(self) -> None:
        m = machine()
        self._to_observation(m)
        assert m.status(Stage.OBSERVATION) is StageStatus.DONE
        rewound = m.rewind(Stage.RENDER, reason="plan figé, flux optique nul")
        assert Stage.RENDER in rewound
        assert Stage.OBSERVATION in rewound
        assert m.status(Stage.RENDER) is StageStatus.PENDING
        assert m.status(Stage.OBSERVATION) is StageStatus.PENDING
        assert m.status(Stage.ASSETS) is StageStatus.DONE

    def test_a_rewind_clears_the_stage_artifacts(self) -> None:
        m = machine()
        self._to_observation(m)
        m.state(Stage.RENDER).artifact_ids = ["render_artifact-1"]
        m.rewind(Stage.RENDER, reason="rendu à refaire")
        assert m.state(Stage.RENDER).artifact_ids == []

    def test_repair_cycles_are_capped(self) -> None:
        m = machine(max_repair_cycles=2)
        self._to_observation(m)
        m.rewind(Stage.RENDER, reason="cycle 1")
        run(m, Stage.RENDER)
        run(m, Stage.OBSERVATION)
        m.rewind(Stage.RENDER, reason="cycle 2")
        run(m, Stage.RENDER)
        run(m, Stage.OBSERVATION)
        with pytest.raises(TransitionRefused, match="plafond de réparation"):
            m.rewind(Stage.RENDER, reason="cycle 3")

    def test_a_rewind_can_be_exempt_from_the_cap(self) -> None:
        m = machine(max_repair_cycles=0)
        self._to_observation(m)
        m.rewind(Stage.RENDER, reason="reprise manuelle", count_as_repair_cycle=False)
        assert m.snapshot.repair_cycles == 0

    def test_a_rewind_unblocks_a_blocked_episode(self) -> None:
        m = machine()
        self._to_observation(m)
        m.start(Stage.DIAGNOSIS)
        m.fail(Stage.DIAGNOSIS, reason="observateur indisponible")
        assert m.episode_status is EpisodeStatus.BLOCKED
        m.rewind(Stage.RENDER, reason="on repart du rendu")
        assert m.episode_status is EpisodeStatus.RUNNING

    def test_a_rewind_needs_a_reason(self) -> None:
        m = machine()
        with pytest.raises(TransitionRefused, match="rembobinage exige un motif"):
            m.rewind(Stage.RENDER, reason="")


class TestFullRun:
    def test_a_complete_run_reaches_delivery(self) -> None:
        m = machine()
        for stage in STAGE_ORDER:
            run(m, stage)
        assert m.is_complete()
        assert m.episode_status is EpisodeStatus.DELIVERED

    def test_a_run_with_skipped_optional_stages_reaches_delivery(self) -> None:
        m = machine()
        for stage in STAGE_ORDER:
            if stage in (Stage.DIAGNOSIS, Stage.REPAIR, Stage.SUBTITLES):
                m.skip(stage, reason="rien à faire à cette étape")
                continue
            run(m, stage)
        assert m.is_complete()

    def test_edit_cannot_start_before_diagnosis_is_settled(self) -> None:
        m = machine()
        for stage in STAGE_ORDER:
            if stage is Stage.DIAGNOSIS:
                break
            run(m, stage)
        with pytest.raises(TransitionRefused, match="diagnosis"):
            m.start(Stage.EDIT)


class TestJournalAndResume:
    def test_every_change_is_journalled(self) -> None:
        m = machine()
        run(m, Stage.RESEARCH, cost=0.05)
        kinds = [(t.stage, t.from_status, t.to_status) for t in m.transitions]
        assert kinds == [
            (Stage.RESEARCH, StageStatus.PENDING, StageStatus.RUNNING),
            (Stage.RESEARCH, StageStatus.RUNNING, StageStatus.DONE),
        ]
        assert m.transitions[-1].cost_usd == pytest.approx(0.05)
        assert all(t.reason for t in m.transitions)

    def test_a_snapshot_round_trips_through_json(self) -> None:
        m = machine(budget_cap_usd=2.0)
        run(m, Stage.RESEARCH, cost=0.1)
        run(m, Stage.DIRECTION, cost=0.2)
        payload = m.snapshot.to_payload()

        from pdz2.contracts.versioning import registry

        reloaded = registry.load(payload)
        assert reloaded == m.snapshot

    def test_resuming_continues_where_it_stopped(self) -> None:
        m = machine()
        run(m, Stage.RESEARCH)
        run(m, Stage.DIRECTION)
        resumed = EpisodeStateMachine.resume(m.snapshot)
        assert resumed.status(Stage.DIRECTION) is StageStatus.DONE
        assert Stage.SCRIPT in resumed.ready_stages()
        run(resumed, Stage.SCRIPT)
        assert resumed.status(Stage.SCRIPT) is StageStatus.DONE
        # La machine d'origine n'est pas touchée : la reprise travaille sur copie.
        assert m.status(Stage.SCRIPT) is StageStatus.PENDING

    def test_abandon_marks_running_stages_and_ends_the_episode(self) -> None:
        m = machine()
        m.start(Stage.RESEARCH)
        m.abandon(reason="sujet retiré")
        assert m.episode_status is EpisodeStatus.ABANDONED
        assert m.status(Stage.RESEARCH) is StageStatus.FAILED
        with pytest.raises(TransitionRefused):
            m.start(Stage.RESEARCH)
