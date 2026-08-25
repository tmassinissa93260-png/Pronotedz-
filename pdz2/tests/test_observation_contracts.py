"""Observation, diagnostic et réparation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pdz2.contracts import (
    FailureDiagnosis,
    FailureFinding,
    FailureKind,
    Measurement,
    ObservationReport,
    QaCheck,
    RepairAction,
    RepairPlan,
    RepairStep,
    Severity,
    Stage,
)


def _check(passed: bool, severity: Severity = Severity.BLOCKING, check_id: str = "c1") -> QaCheck:
    return QaCheck(
        check_id=check_id,
        name="mouvement mesuré",
        passed=passed,
        observed=0.0 if not passed else 0.4,
        expected=0.4,
        tolerance=0.1,
        severity=severity,
    )


def _measurement(name: str = "optical_flow_mean", deterministic: bool = True) -> Measurement:
    return Measurement(
        name=name,
        value=0.02,
        unit="px/frame",
        method="flux optique dense, moyenne sur la fenêtre conservée au montage",
        deterministic=deterministic,
    )


class TestObservationReport:
    def test_a_blocking_failure_forbids_a_pass_verdict(self) -> None:
        with pytest.raises(ValidationError, match="malgré des blocages"):
            ObservationReport(
                artifact_id="render_artifact-1",
                observer_version="1.0.0",
                checks=[_check(False)],
                passed=True,
            )

    def test_a_fail_verdict_needs_a_real_failure(self) -> None:
        with pytest.raises(ValidationError, match="sans échec majeur ni bloquant"):
            ObservationReport(
                artifact_id="render_artifact-1",
                observer_version="1.0.0",
                checks=[_check(True)],
                passed=False,
            )

    def test_a_major_failure_justifies_a_fail_verdict(self) -> None:
        report = ObservationReport(
            artifact_id="render_artifact-1",
            observer_version="1.0.0",
            checks=[_check(False, Severity.MAJOR)],
            passed=False,
        )
        assert report.passed is False

    def test_duplicate_check_ids_are_refused(self) -> None:
        with pytest.raises(ValidationError, match="check_id en double"):
            ObservationReport(
                artifact_id="a",
                observer_version="1.0.0",
                checks=[_check(True), _check(True)],
                passed=True,
            )

    def test_determinism_is_derived_from_the_measurements(self) -> None:
        report = ObservationReport(
            artifact_id="a",
            observer_version="1.0.0",
            measurements=[_measurement(), _measurement("sharpness", deterministic=False)],
            checks=[_check(True)],
            passed=True,
        )
        assert report.deterministic is False
        assert report.measurement("sharpness").deterministic is False

    def test_unknown_measurement_lookup_raises(self) -> None:
        report = ObservationReport(
            artifact_id="a",
            observer_version="1.0.0",
            measurements=[_measurement()],
            checks=[_check(True)],
            passed=True,
        )
        with pytest.raises(KeyError):
            report.measurement("inexistante")


class TestFailureDiagnosis:
    def _finding(self, **overrides) -> FailureFinding:
        payload = {
            "kind": FailureKind.NO_MOTION,
            "explanation": "Le flux optique reste sous le seuil sur toute la fenêtre.",
            "evidence_measurements": ["optical_flow_mean"],
            "confidence": 0.9,
        }
        return FailureFinding(**(payload | overrides))

    def test_a_finding_must_cite_a_measurement(self) -> None:
        with pytest.raises(ValidationError):
            self._finding(evidence_measurements=[])

    def test_root_cause_must_be_among_the_findings(self) -> None:
        with pytest.raises(ValidationError, match="cause racine"):
            FailureDiagnosis(
                observation_id="observation_report-1",
                findings=[self._finding()],
                root_cause=FailureKind.IDENTITY_DRIFT,
                explanation="incohérent",
            )

    def test_a_coherent_diagnosis_is_accepted(self) -> None:
        diagnosis = FailureDiagnosis(
            observation_id="observation_report-1",
            findings=[self._finding()],
            root_cause=FailureKind.NO_MOTION,
            explanation="Le plan est figé : le fournisseur a ignoré la consigne.",
        )
        assert diagnosis.recoverable is True


class TestRepairPlan:
    def _step(self, **overrides) -> RepairStep:
        payload = {
            "action": RepairAction.RETRY_NEW_SEED,
            "rationale": "Un nouveau tirage suffit souvent sur ce type d'échec.",
            "target_stage": Stage.RENDER,
            "estimated_cost_usd": 0.2,
            "expected_effect": "Le flux optique repasse au-dessus du seuil.",
        }
        return RepairStep(**(payload | overrides))

    def _plan(self, **overrides) -> RepairPlan:
        payload = {
            "diagnosis_id": "failure_diagnosis-1",
            "steps": [self._step()],
            "cycle": 1,
            "max_cycles": 3,
            "guaranteed_fallback": RepairAction.FALLBACK_KEN_BURNS,
        }
        return RepairPlan(**(payload | overrides))

    def test_a_valid_plan_is_accepted(self) -> None:
        plan = self._plan()
        assert plan.total_estimated_cost_usd == pytest.approx(0.2)

    def test_the_guaranteed_fallback_must_not_need_a_provider(self) -> None:
        with pytest.raises(ValidationError, match="repli garanti invalide"):
            self._plan(guaranteed_fallback=RepairAction.RETRY_SAME)

    def test_every_guaranteed_fallback_is_accepted(self) -> None:
        for action in (
            RepairAction.FALLBACK_2_5D,
            RepairAction.FALLBACK_KEN_BURNS,
            RepairAction.FALLBACK_STILL,
            RepairAction.ESCALATE_HUMAN,
        ):
            assert self._plan(guaranteed_fallback=action).guaranteed_fallback is action

    def test_the_cycle_cannot_exceed_the_cap(self) -> None:
        with pytest.raises(ValidationError, match="au-dessus du plafond"):
            self._plan(cycle=4, max_cycles=3)

    def test_the_last_cycle_must_end_on_a_guaranteed_fallback(self) -> None:
        with pytest.raises(ValidationError, match="dernier cycle"):
            self._plan(cycle=3, max_cycles=3)

    def test_the_last_cycle_with_a_fallback_is_accepted(self) -> None:
        plan = self._plan(
            cycle=3,
            max_cycles=3,
            steps=[
                self._step(
                    action=RepairAction.FALLBACK_KEN_BURNS,
                    estimated_cost_usd=0.0,
                    rationale="Dernier cycle : garantir la livraison.",
                    expected_effect="Un mouvement déterministe remplace le plan raté.",
                )
            ],
        )
        assert plan.cycle == plan.max_cycles

    def test_a_local_fallback_cannot_be_billed(self) -> None:
        with pytest.raises(ValidationError, match="repli local"):
            self._step(action=RepairAction.FALLBACK_STILL, estimated_cost_usd=0.5)
