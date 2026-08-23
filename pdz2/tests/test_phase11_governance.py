"""Phase 11 : capacités mesurées, dépenses gouvernées.

Deux disciplines s'y jouent, et elles se ressemblent : ne jamais confondre ce
qu'on a vérifié avec ce qu'on nous a dit, et ne jamais constater une dépense
qu'on aurait dû refuser.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from pdz2.contracts.capacity import (
    DEFAULT_FRESHNESS_DAYS,
    CapabilityEntry,
    CapabilityMatrix,
    CapacityValue,
    CostLedger,
    Provenance,
    SpendRecord,
)
from pdz2.contracts.pipeline import Stage
from pdz2.contracts.render import RenderStrategy
from pdz2.engines.governance import (
    COST_PER_SECOND,
    CapabilityProbe,
    CostGovernor,
    CostRefused,
    Refusal,
    tool_versions,
)
from pdz2.engines.governance.matrix import ENCODE_FPS, SPEECH_REALTIME_RATIO
from pdz2.renderers import ffmpeg_capability

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)

needs_ffmpeg = pytest.mark.skipif(
    not ffmpeg_capability().usable, reason="binaire ffmpeg absent"
)


def measured(name: str, value: float, *, at: datetime = NOW) -> CapacityValue:
    return CapacityValue(
        name=name,
        value=value,
        unit="USD/s",
        provenance=Provenance.MEASURED,
        measured_at=at,
        method="mesure de test, rejouable",
    )


# --------------------------------------------------------------- provenance


def test_a_measurement_without_a_date_is_refused():
    with pytest.raises(ValidationError, match="sans date"):
        CapacityValue(
            name=COST_PER_SECOND,
            value=0.4,
            provenance=Provenance.MEASURED,
            method="au doigt mouillé",
        )


def test_a_measurement_without_a_method_is_refused():
    with pytest.raises(ValidationError, match="sans méthode"):
        CapacityValue(
            name=COST_PER_SECOND,
            value=0.4,
            provenance=Provenance.MEASURED,
            measured_at=NOW,
        )


def test_an_unknown_capacity_carries_no_number():
    with pytest.raises(ValidationError, match="on ne chiffre pas"):
        CapacityValue(name=COST_PER_SECOND, value=0.4, provenance=Provenance.UNKNOWN)


def test_an_announced_capacity_is_never_trustworthy():
    announced = CapacityValue(
        name=COST_PER_SECOND, value=0.4, provenance=Provenance.ANNOUNCED
    )
    assert not announced.trustworthy(now=NOW)


def test_a_measurement_expires():
    old = measured(COST_PER_SECOND, 0.4, at=NOW - timedelta(days=DEFAULT_FRESHNESS_DAYS + 1))
    fresh = measured(COST_PER_SECOND, 0.4, at=NOW - timedelta(days=1))
    assert old.is_stale(now=NOW)
    assert not old.trustworthy(now=NOW)
    assert fresh.trustworthy(now=NOW)


def test_the_matrix_lists_what_has_expired():
    matrix = CapabilityMatrix(
        entries=[
            CapabilityEntry(
                provider="p",
                model="m",
                values=[measured(COST_PER_SECOND, 0.4, at=NOW - timedelta(days=90))],
            )
        ]
    )
    assert matrix.stale_values(now=NOW) == [("p", "m", COST_PER_SECOND)]


def test_the_matrix_refuses_two_entries_for_the_same_pair():
    entry = CapabilityEntry(provider="p", model="m")
    with pytest.raises(ValidationError, match="deux entrées"):
        CapabilityMatrix(entries=[entry, CapabilityEntry(provider="p", model="m")])
    assert CapabilityMatrix(entries=[entry]).entry("p", "m") is entry


# ------------------------------------------------------------ autorisation


def ledger(cap: float | None = 10.0, spent: float = 0.0) -> CostLedger:
    records = (
        [SpendRecord(stage="render", amount_usd=spent, at=NOW)] if spent else []
    )
    return CostLedger(episode_id="e", budget_cap_usd=cap, records=records)


def test_a_spend_under_the_cap_is_authorised():
    governor = CostGovernor(ledger=ledger(cap=10.0, spent=4.0))
    decision = governor.may_spend(2.0, stage=Stage.RENDER)
    assert decision.allowed
    assert decision.remaining_usd == pytest.approx(6.0)


def test_a_spend_over_the_remainder_is_refused_before_it_happens():
    governor = CostGovernor(ledger=ledger(cap=10.0, spent=9.0))
    decision = governor.may_spend(2.0, stage=Stage.RENDER)
    assert not decision.allowed
    assert decision.reason is Refusal.WOULD_EXCEED
    assert governor.ledger.spent_usd == pytest.approx(9.0)


def test_an_exhausted_budget_refuses_everything():
    governor = CostGovernor(ledger=ledger(cap=10.0, spent=10.0))
    decision = governor.may_spend(0.01, stage=Stage.RENDER)
    assert decision.reason is Refusal.BUDGET_EXHAUSTED


def test_a_cost_nobody_measured_is_refused_even_with_budget_left():
    matrix = CapabilityMatrix(
        entries=[
            CapabilityEntry(
                provider="atelier",
                model="v1",
                values=[
                    CapacityValue(
                        name=COST_PER_SECOND, value=0.4, provenance=Provenance.ANNOUNCED
                    )
                ],
            )
        ]
    )
    governor = CostGovernor(ledger=ledger(cap=1000.0), matrix=matrix)
    decision = governor.may_spend(
        1.0, stage=Stage.RENDER, provider="atelier", model="v1"
    )
    assert not decision.allowed
    assert decision.reason is Refusal.UNMEASURED_COST
    assert "brochure" in decision.detail


def test_an_absent_provider_is_refused_rather_than_guessed():
    governor = CostGovernor(ledger=ledger(), matrix=CapabilityMatrix())
    decision = governor.may_spend(
        1.0, stage=Stage.RENDER, provider="inconnu", model="v1"
    )
    assert decision.reason is Refusal.UNMEASURED_COST
    assert "absent de la matrice" in decision.detail


def test_an_expired_measurement_stops_the_spend():
    matrix = CapabilityMatrix(
        entries=[
            CapabilityEntry(
                provider="atelier",
                model="v1",
                values=[
                    measured(COST_PER_SECOND, 0.4, at=datetime.now(UTC) - timedelta(days=90))
                ],
            )
        ]
    )
    governor = CostGovernor(ledger=ledger(), matrix=matrix)
    decision = governor.may_spend(
        1.0, stage=Stage.RENDER, provider="atelier", model="v1"
    )
    assert decision.reason is Refusal.UNMEASURED_COST
    assert "périmé" in decision.detail


def test_spending_records_the_amount_and_refusing_records_nothing():
    governor = CostGovernor(ledger=ledger(cap=10.0))
    record = governor.spend(3.0, stage=Stage.RENDER, shot_id="S00", detail="essai")
    assert record.shot_id == "S00"
    assert governor.ledger.spent_usd == pytest.approx(3.0)
    with pytest.raises(CostRefused) as refused:
        governor.spend(50.0, stage=Stage.RENDER)
    assert refused.value.reason is Refusal.WOULD_EXCEED
    assert governor.ledger.spent_usd == pytest.approx(3.0)
    assert len(governor.ledger.records) == 1


def test_without_a_cap_nothing_is_refused_for_budget_reasons():
    governor = CostGovernor(ledger=ledger(cap=None))
    assert governor.may_spend(10_000.0, stage=Stage.RENDER).allowed


def test_a_ledger_above_its_own_cap_is_an_impossible_contract():
    with pytest.raises(ValidationError, match="aurait dû être refusée"):
        CostLedger(
            episode_id="e",
            budget_cap_usd=1.0,
            records=[SpendRecord(stage="render", amount_usd=2.0, at=NOW)],
        )


def test_an_estimate_only_exists_when_the_cost_was_measured():
    announced = CapabilityMatrix(
        entries=[
            CapabilityEntry(
                provider="atelier",
                model="v1",
                values=[
                    CapacityValue(
                        name=COST_PER_SECOND, value=0.4, provenance=Provenance.ANNOUNCED
                    )
                ],
            )
        ]
    )
    assert (
        CostGovernor(ledger=ledger(), matrix=announced).estimate(
            provider="atelier", model="v1", seconds=5.0
        )
        is None
    )
    verified = CapabilityMatrix(
        entries=[
            CapabilityEntry(
                provider="atelier",
                model="v1",
                values=[measured(COST_PER_SECOND, 0.4, at=datetime.now(UTC))],
            )
        ]
    )
    assert CostGovernor(ledger=ledger(), matrix=verified).estimate(
        provider="atelier", model="v1", seconds=5.0
    ) == pytest.approx(2.0)


def test_by_stage_totals_add_up():
    book = CostLedger(
        episode_id="e",
        records=[
            SpendRecord(stage="render", amount_usd=1.0, at=NOW),
            SpendRecord(stage="render", amount_usd=2.0, at=NOW),
            SpendRecord(stage="voice", amount_usd=0.5, at=NOW),
        ],
    )
    assert book.by_stage() == {"render": 3.0, "voice": 0.5}
    assert book.spent_usd == pytest.approx(3.5)


# -------------------------------------------------------------------- sonde


def test_the_probe_reads_the_real_environment():
    outcome = CapabilityProbe().run()
    providers = {entry.provider for entry in outcome.matrix.entries}
    assert providers == {"ffmpeg", "espeak-ng"}
    for capability in outcome.capabilities:
        # Une capacité rendue par la sonde a été vérifiée à l'instant : elle
        # porte une date et une méthode, ou elle n'a pas le droit d'exister.
        assert capability.measured_at is not None
        assert capability.measurement_method


def test_an_unmeasured_capacity_carries_no_value():
    outcome = CapabilityProbe(measure=False).run()
    entry = outcome.matrix.entry("ffmpeg", "libx264")
    assert entry is not None
    speed = entry.value(ENCODE_FPS)
    assert speed is not None
    assert speed.provenance is Provenance.UNKNOWN
    assert speed.value is None


@needs_ffmpeg
def test_measuring_produces_a_real_dated_number():
    outcome = CapabilityProbe(measure=True).run()
    entry = outcome.matrix.entry("ffmpeg", "libx264")
    assert entry is not None
    speed = entry.value(ENCODE_FPS)
    assert speed is not None and speed.provenance is Provenance.MEASURED
    assert speed.value > 0
    assert speed.trustworthy()
    assert "ffprobe" in speed.method

    speech = outcome.matrix.entry("espeak-ng", "fr")
    assert speech is not None
    ratio = speech.value(SPEECH_REALTIME_RATIO)
    assert ratio is not None
    if ratio.provenance is Provenance.MEASURED:
        assert ratio.value > 0


def test_the_probe_declares_only_the_strategies_really_implemented():
    entry = CapabilityProbe().run().matrix.entry("ffmpeg", "libx264")
    assert entry is not None
    assert RenderStrategy.KEN_BURNS in entry.strategies
    # Aucun chemin de ce dépôt ne sait produire ces stratégies : les annoncer
    # ferait croire le routeur capable de ce qu'il ne sait pas faire.
    assert RenderStrategy.DIRECT_I2V not in entry.strategies
    assert RenderStrategy.THREE_D not in entry.strategies


def test_the_probe_invents_no_video_provider():
    outcome = CapabilityProbe().run()
    assert not any(
        entry.provider not in {"ffmpeg", "espeak-ng"} for entry in outcome.matrix.entries
    )
    assert any("n'en invente pas" in note for note in outcome.notes)


def test_local_tools_cost_nothing_and_say_why():
    entry = CapabilityProbe().run().matrix.entry("ffmpeg", "libx264")
    assert entry is not None
    cost = entry.value(COST_PER_SECOND)
    assert cost is not None
    if cost.provenance is Provenance.MEASURED:
        assert cost.value == 0.0
        assert "facturation" in cost.method


def test_tool_versions_are_read_not_assumed():
    versions = tool_versions()
    assert len(versions) == 2
    assert all(":" in line for line in versions)


# ------------------------------------------------------- registre et épisode


def test_the_ledger_mirrors_the_state_machine_and_opens_no_second_accounting():
    from pdz2.cli.phase11 import ledger_from_snapshot
    from pdz2.state import EpisodeStateMachine

    machine = EpisodeStateMachine.create(
        episode_id="ep", topic_request_id="topic_request-1", budget_cap_usd=5.0
    )
    machine.start(Stage.RESEARCH, reason="essai")
    machine.complete(Stage.RESEARCH, cost_usd=1.5)
    book = ledger_from_snapshot(machine.snapshot)
    assert book.spent_usd == pytest.approx(machine.snapshot.spent_usd)
    assert book.budget_cap_usd == 5.0
    assert book.by_stage() == {"research": 1.5}
