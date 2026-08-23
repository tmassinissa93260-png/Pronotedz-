"""Phase 12 : le journal de production, relu depuis les contrats.

Ce qui est vérifié ici n'est pas que le journal soit joli : c'est qu'il ne
puisse rien raconter qui ne soit sur le disque, et qu'il ne puisse rien taire
de ce qui y est. Une dégradation ajoutée à un contrat apparaît au journal ; un
contrat retiré la fait disparaître. C'est la propriété qui rend un journal
utile six mois plus tard.
"""

from __future__ import annotations

import pytest

from pdz2.contracts.journal import (
    JournalEntry,
    JournalEntryKind,
    ProductionJournal,
)
from pdz2.contracts.pipeline import EpisodeStatus, Stage
from pdz2.engines.journal import JournalBuilder
from pdz2.state import EpisodeStateMachine
from pdz2.storage import EpisodeStore
from pdz2.tests import pipeline


@pytest.fixture(scope="module")
def episode(tmp_path_factory):
    return pipeline.build_episode(
        tmp_path_factory.mktemp("phase12"),
        through_render_spec=True,
        resolution=pipeline.SMALL,
    )


@pytest.fixture
def store(tmp_path, episode) -> EpisodeStore:
    """Un dossier d'épisode réel, mené jusqu'au routage."""
    from pdz2.engines.routing import RenderRouter

    store = EpisodeStore(tmp_path / "ep")
    store.initialise()
    for item in (
        episode.request,
        episode.research,
        episode.brief,
        episode.director_state,
        episode.script,
        episode.timeline,
        episode.bible,
        episode.temporal_plan,
        episode.graph,
        episode.validation,
    ):
        store.save(item)
    for spec in episode.render_specs:
        store.save(spec)
    executables = RenderRouter().route(
        episode_id="ep",
        requested=episode.render_specs,
        motion_programs=episode.motion_programs,
        image_specs=episode.image_specs,
    ).executables
    for executable in executables:
        store.save(executable)

    machine = EpisodeStateMachine.create(
        episode_id="ep", topic_request_id=episode.request.id
    )
    for stage in (
        Stage.RESEARCH,
        Stage.DIRECTION,
        Stage.SCRIPT,
        Stage.VOICE,
        Stage.TIMELINE,
        Stage.VISUAL_BIBLE,
        Stage.SHOT_GRAPH,
    ):
        machine.start(stage, reason="essai")
        machine.complete(stage)
    store.save_snapshot(machine.snapshot)
    return store


def build(store: EpisodeStore) -> ProductionJournal:
    return JournalBuilder().build(store=store).journal


# ------------------------------------------------------------- reconstruction


def test_the_journal_is_rebuilt_from_the_episode_folder(store, episode):
    journal = build(store)
    assert journal.episode_id == "ep"
    assert journal.topic == episode.request.topic
    assert journal.entries
    assert journal.transitions


def test_every_declared_degradation_reaches_the_journal(store):
    declared = [
        (executable.shot_id, degradation.field)
        for executable in store.load_collection("render_spec_executable")
        for degradation in executable.degradations
    ]
    journal = build(store)
    reported = [
        (entry.subject_id, entry.summary)
        for entry in journal.of_kind(JournalEntryKind.DEGRADATION)
    ]
    assert len(reported) == len(declared)
    for shot_id, field in declared:
        assert any(
            shot_id == subject and field in summary for subject, summary in reported
        )


def test_removing_a_contract_removes_its_entries(store):
    before = len(build(store).of_kind(JournalEntryKind.DEGRADATION))
    assert before > 0
    for path in (store.root / "render_specs").glob("*.json"):
        import json

        if json.loads(path.read_text())["contract_type"] == "render_spec_executable":
            path.unlink()
    after = len(build(store).of_kind(JournalEntryKind.DEGRADATION))
    assert after == 0


def test_a_failing_check_becomes_an_unresolved_finding(store, episode):
    from pdz2.contracts.common import QaCheck
    from pdz2.contracts.enums import Severity
    from pdz2.contracts.observation import Measurement, ObservationReport

    shot_id = episode.graph.shots[0].shot_id
    report = ObservationReport(
        shot_id=shot_id,
        artifact_id="render_artifact-test",
        observer_version="1.0.0",
        passed=False,
        measurements=[
            Measurement(
                name="first_to_last_difference",
                value=0.0,
                unit="ratio",
                method="différence première/dernière image",
            )
        ],
        checks=[
            QaCheck(
                check_id="motion_present",
                name="le plan bouge",
                passed=False,
                severity=Severity.BLOCKING,
                observed=0.0,
                expected=0.002,
                detail="le plan ne bouge pas",
            )
        ],
    )
    store.save(report)
    journal = build(store)
    findings = journal.of_kind(JournalEntryKind.FINDING)
    assert any("motion_present" in entry.summary for entry in findings)
    assert any("motion_present" in entry.summary for entry in journal.unresolved)


def test_a_failed_stage_is_recorded_as_a_refusal(store):
    machine = EpisodeStateMachine.resume(store.load_snapshot())
    machine.start(Stage.MOTION, reason="essai")
    machine.fail(Stage.MOTION, reason="essai de panne")
    store.save_snapshot(machine.snapshot)
    journal = build(store)
    refusals = journal.of_kind(JournalEntryKind.REFUSAL)
    assert any("essai de panne" in entry.detail for entry in refusals)


def test_spending_appears_only_when_something_was_spent(store):
    assert not build(store).of_kind(JournalEntryKind.SPEND)
    machine = EpisodeStateMachine.resume(store.load_snapshot())
    machine.start(Stage.MOTION, reason="essai")
    machine.complete(Stage.MOTION, cost_usd=0.0)
    store.save_snapshot(machine.snapshot)
    assert not build(store).of_kind(JournalEntryKind.SPEND)


def test_the_journal_names_the_contract_versions_it_was_written_under(store):
    journal = build(store)
    assert any(line.startswith("production_journal@") for line in journal.contract_versions)
    assert any(line.startswith("shot_graph@") for line in journal.contract_versions)


def test_the_journal_carries_measured_capabilities_when_they_are_given(store):
    from pdz2.engines.governance import CapabilityProbe, tool_versions

    probed = CapabilityProbe().run()
    outcome = JournalBuilder().build(
        store=store, capabilities=probed.capabilities, tool_versions=tool_versions()
    )
    journal = outcome.journal
    assert len(journal.capabilities) == len(probed.capabilities)
    assert len(journal.of_kind(JournalEntryKind.CAPABILITY)) == len(probed.capabilities)
    assert journal.tool_versions


def test_the_journal_points_at_the_snapshot_it_was_built_from(store):
    journal = build(store)
    assert journal.parent_id == store.load_snapshot().id


def test_unresolved_gathers_findings_degradations_and_limits(store):
    journal = build(store)
    kinds = {entry.kind for entry in journal.unresolved}
    assert kinds <= {
        JournalEntryKind.FINDING,
        JournalEntryKind.DEGRADATION,
        JournalEntryKind.LIMITATION,
    }
    assert JournalEntryKind.DEGRADATION in kinds


# ----------------------------------------------------------------- contrat


def test_entries_out_of_order_are_refused():
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    with pytest.raises(Exception, match="désordre"):
        ProductionJournal(
            episode_id="ep",
            topic="t",
            episode_status=EpisodeStatus.RUNNING,
            started_at=now,
            entries=[
                JournalEntry(kind=JournalEntryKind.DECISION, at=now, summary="deux"),
                JournalEntry(
                    kind=JournalEntryKind.DECISION,
                    at=now - timedelta(seconds=1),
                    summary="un",
                ),
            ],
        )


def test_an_episode_that_ends_before_it_starts_is_refused():
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    with pytest.raises(Exception, match="fin avant début"):
        ProductionJournal(
            episode_id="ep",
            topic="t",
            episode_status=EpisodeStatus.RUNNING,
            started_at=now,
            ended_at=now - timedelta(seconds=1),
        )


def test_an_entry_without_a_timezone_is_refused():
    from datetime import datetime

    with pytest.raises(Exception, match="fuseau"):
        JournalEntry(
            kind=JournalEntryKind.DECISION, at=datetime(2026, 1, 1), summary="x"
        )
