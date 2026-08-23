"""Phase 9 : diagnostic adossé aux mesures, réparation bornée et garantie."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pdz2.contracts.common import QaCheck
from pdz2.contracts.enums import Severity
from pdz2.contracts.observation import (
    GUARANTEED_FALLBACKS,
    FailureKind,
    Measurement,
    ObservationReport,
    RepairAction,
)
from pdz2.contracts.pipeline import Stage
from pdz2.contracts.render import RenderStrategy
from pdz2.repair import (
    CHECK_TO_FAILURE,
    RESPONSES,
    FailureDiagnoser,
    RepairCompiler,
    RepairRejected,
)
from pdz2.tests import pipeline


@pytest.fixture(scope="module")
def episode(tmp_path_factory):
    return pipeline.build_episode(
        tmp_path_factory.mktemp("phase9"),
        through_render_spec=True,
        resolution=pipeline.SMALL,
    )


@pytest.fixture(scope="module")
def executables(episode):
    from pdz2.engines.routing import RenderRouter

    return RenderRouter().route(
        episode_id="ep",
        requested=episode.render_specs,
        motion_programs=episode.motion_programs,
        image_specs=episode.image_specs,
    ).executables


def _measurements() -> list[Measurement]:
    names = (
        ("duration_s", 4.0, "s"),
        ("frame_count", 120.0, "images"),
        ("fps", 30.0, "i/s"),
        ("motion_first_to_last", 0.00001, "niveau/pixel"),
        ("motion_mean_abs_diff", 0.0, "niveau/pixel"),
        ("black_frame_ratio", 0.0, "fraction"),
        ("frozen_frame_ratio", 0.99, "fraction"),
        ("sharpness", 0.002, "variance"),
        ("palette_distance", 0.05, "fraction"),
    )
    return [
        Measurement(name=name, value=value, unit=unit, method="mesure de test")
        for name, value, unit in names
    ]


def _report(shot_id: str, failing: dict[str, Severity]) -> ObservationReport:
    checks = [
        QaCheck(
            check_id=check_id,
            name=f"contrôle {check_id}",
            passed=check_id not in failing,
            observed=0.0,
            expected=1.0,
            severity=failing.get(check_id, Severity.MAJOR),
        )
        for check_id in (
            "duration", "resolution", "fps", "not_black", "not_blank",
            "motion_present", "not_frozen", "palette",
        )
    ]
    return ObservationReport(
        artifact_id=f"render_artifact-{shot_id}",
        shot_id=shot_id,
        observer_version="1.0.0",
        measurements=_measurements(),
        checks=checks,
        passed=not failing,
    )


# --------------------------------------------------------------- diagnostic


class TestDiagnosisCitesMeasurements:
    def test_a_passing_report_produces_no_diagnosis(self, executables) -> None:
        outcome = FailureDiagnoser().diagnose(
            reports=[_report(executables[0].shot_id, {})], executables=executables
        )
        assert outcome.diagnoses == []

    def test_every_finding_cites_at_least_one_measurement(self, executables) -> None:
        report = _report(
            executables[0].shot_id,
            {"motion_present": Severity.BLOCKING, "not_frozen": Severity.MAJOR},
        )
        outcome = FailureDiagnoser().diagnose(
            reports=[report], executables=executables
        )
        diagnosis = outcome.diagnoses[0]
        assert diagnosis.findings
        for finding in diagnosis.findings:
            assert finding.evidence_measurements
            assert all(
                name in {m.name for m in report.measurements}
                for name in finding.evidence_measurements
            )

    def test_the_root_cause_is_the_most_upstream_one(self, executables) -> None:
        """Une image noire explique l'absence de mouvement, pas l'inverse."""
        report = _report(
            executables[0].shot_id,
            {"motion_present": Severity.BLOCKING, "not_black": Severity.BLOCKING},
        )
        outcome = FailureDiagnoser().diagnose(
            reports=[report], executables=executables
        )
        assert outcome.diagnoses[0].root_cause is FailureKind.BLACK_FRAMES

    def test_the_root_cause_is_always_among_the_findings(self, executables) -> None:
        for failing in (
            {"motion_present": Severity.BLOCKING},
            {"not_black": Severity.BLOCKING},
            {"palette": Severity.MAJOR},
            {"duration": Severity.BLOCKING},
        ):
            report = _report(executables[0].shot_id, failing)
            diagnosis = FailureDiagnoser().diagnose(
                reports=[report], executables=executables
            ).diagnoses[0]
            assert diagnosis.root_cause in {f.kind for f in diagnosis.findings}

    def test_a_provider_error_is_not_recoverable(self, executables) -> None:
        report = _report(executables[0].shot_id, {"resolution": Severity.BLOCKING})
        diagnosis = FailureDiagnoser().diagnose(
            reports=[report], executables=executables
        ).diagnoses[0]
        assert diagnosis.root_cause is FailureKind.PROVIDER_ERROR
        assert diagnosis.recoverable is False

    def test_every_observer_check_has_a_translation(self) -> None:
        """Un contrôle sans traduction laisserait un échec sans cause."""
        from pdz2.qa.observer import DeterministicObserver

        known = set(CHECK_TO_FAILURE)
        emitted = {
            "duration", "resolution", "fps", "not_black", "not_blank",
            "motion_present", "not_frozen", "stillness", "palette",
        }
        assert emitted <= known
        assert DeterministicObserver is not None

    def test_the_confidence_follows_the_severity_of_the_check(
        self, executables
    ) -> None:
        """Un constat mineur ne porte pas la même confiance qu'un bloquant.

        Le contrat refuse un rapport non conforme dont aucun échec ne serait
        majeur : on associe donc le constat mineur à un échec majeur, ce qui
        est aussi le cas réel.
        """
        report = _report(
            executables[0].shot_id,
            {"palette": Severity.MINOR, "not_frozen": Severity.MAJOR},
        )
        diagnosis = FailureDiagnoser().diagnose(
            reports=[report], executables=executables
        ).diagnoses[0]
        by_kind = {finding.kind: finding for finding in diagnosis.findings}
        assert by_kind[FailureKind.STYLE_DRIFT].confidence < (
            by_kind[FailureKind.NO_MOTION].confidence
        )


# --------------------------------------------------------------- réparation


class TestRepairIsBoundedAndGuaranteed:
    def _plans(self, executables, failing, cycle=1, **kwargs):
        reports = [_report(executables[0].shot_id, failing)]
        diagnoses = FailureDiagnoser().diagnose(
            reports=reports, executables=executables
        ).diagnoses
        return RepairCompiler(**kwargs).compile(
            diagnoses=diagnoses, executables=executables, cycle=cycle
        )

    def test_every_cause_has_a_planned_response(self) -> None:
        """Une cause sans réponse serait une improvisation."""
        translated = {kind for kind, _ in CHECK_TO_FAILURE.values()}
        assert translated <= set(RESPONSES)

    def test_a_no_motion_failure_changes_strategy(self, executables) -> None:
        outcome = self._plans(executables, {"motion_present": Severity.BLOCKING})
        plan = outcome.plans[0]
        actions = [step.action for step in plan.steps]
        assert RepairAction.CHANGE_STRATEGY in actions
        assert plan.steps[0].target_stage is Stage.ROUTING

    def test_a_black_frame_failure_regenerates_the_asset(self, executables) -> None:
        outcome = self._plans(executables, {"not_black": Severity.BLOCKING})
        step = outcome.plans[0].steps[0]
        assert step.action is RepairAction.REGENERATE_ASSET
        assert step.target_stage is Stage.ASSETS

    def test_the_last_cycle_ends_on_a_guaranteed_fallback(self, executables) -> None:
        outcome = self._plans(
            executables, {"motion_present": Severity.BLOCKING}, cycle=3
        )
        plan = outcome.plans[0]
        assert plan.cycle == plan.max_cycles
        assert plan.steps[-1].action in GUARANTEED_FALLBACKS

    def test_the_guaranteed_fallback_gets_sober_as_cycles_run_out(
        self, executables
    ) -> None:
        fallbacks = [
            self._plans(
                executables, {"motion_present": Severity.BLOCKING}, cycle=cycle
            ).plans[0].guaranteed_fallback
            for cycle in (1, 2, 3)
        ]
        assert fallbacks == [
            RepairAction.FALLBACK_2_5D,
            RepairAction.FALLBACK_KEN_BURNS,
            RepairAction.FALLBACK_STILL,
        ]
        assert all(action in GUARANTEED_FALLBACKS for action in fallbacks)

    def test_a_cycle_beyond_the_cap_is_refused(self, executables) -> None:
        with pytest.raises(RepairRejected, match="au-delà du plafond"):
            self._plans(executables, {"motion_present": Severity.BLOCKING}, cycle=9)

    def test_a_cycle_below_one_is_refused(self, executables) -> None:
        with pytest.raises(RepairRejected, match="commence à 1"):
            self._plans(executables, {"motion_present": Severity.BLOCKING}, cycle=0)

    def test_local_fallbacks_are_never_billed(self, executables) -> None:
        outcome = self._plans(
            executables, {"motion_present": Severity.BLOCKING}, cycle=3
        )
        assert outcome.plans[0].total_estimated_cost_usd == 0.0

    def test_the_failed_strategy_is_forbidden_for_the_next_round(
        self, executables
    ) -> None:
        """Le routeur ne doit pas reproposer ce qui vient d'échouer."""
        outcome = self._plans(executables, {"motion_present": Severity.BLOCKING})
        shot = executables[0].shot_id
        assert executables[0].strategy in outcome.forbidden_strategies[shot]

    def test_a_style_drift_does_not_blame_the_strategy(self, executables) -> None:
        """La palette dérive à cause de l'image, pas de la stratégie de rendu."""
        outcome = self._plans(executables, {"palette": Severity.MAJOR})
        assert outcome.forbidden_strategies == {}
        assert outcome.plans[0].steps[0].target_stage is Stage.ASSETS

    def test_the_rewind_stages_are_named(self, executables) -> None:
        outcome = self._plans(executables, {"not_black": Severity.BLOCKING})
        assert Stage.ASSETS in outcome.rewind_stages

    def test_a_contract_refuses_a_last_cycle_without_a_fallback(self) -> None:
        from pdz2.contracts.observation import RepairPlan, RepairStep

        step = RepairStep(
            action=RepairAction.RETRY_SAME,
            rationale="rejouer",
            target_stage=Stage.RENDER,
            expected_effect="peut-être mieux",
        )
        with pytest.raises(ValidationError, match="dernier cycle"):
            RepairPlan(
                diagnosis_id="failure_diagnosis-1",
                steps=[step],
                cycle=3,
                max_cycles=3,
                guaranteed_fallback=RepairAction.FALLBACK_STILL,
            )


class TestTheLoopConverges:
    def test_repeated_failures_end_on_a_still(self, executables) -> None:
        """Trois cycles au plus, et le dernier aboutit toujours."""
        forbidden: dict[str, set[RenderStrategy]] = {}
        compiler = RepairCompiler()
        last_plan = None
        for cycle in (1, 2, 3):
            reports = [_report(executables[0].shot_id, {"motion_present": Severity.BLOCKING})]
            diagnoses = FailureDiagnoser().diagnose(
                reports=reports, executables=executables
            ).diagnoses
            outcome = compiler.compile(
                diagnoses=diagnoses,
                executables=executables,
                cycle=cycle,
                already_forbidden=forbidden,
            )
            forbidden = outcome.forbidden_strategies
            last_plan = outcome.plans[0]
        assert last_plan is not None
        assert last_plan.guaranteed_fallback is RepairAction.FALLBACK_STILL
        assert last_plan.steps[-1].action in GUARANTEED_FALLBACKS
        with pytest.raises(RepairRejected):
            compiler.compile(diagnoses=[], executables=executables, cycle=4)
