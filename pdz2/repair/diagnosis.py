"""Diagnostic : expliquer un échec, mesures à l'appui.

    DIAGNOSTICS EXPLAIN.

Le diagnostic ne re-mesure rien : il lit le rapport d'observation et traduit
des contrôles en échec en causes nommées. Chaque constat **cite les mesures**
qui l'étayent — le contrat `FailureFinding` refuse un constat sans preuve, et
`FailureDiagnosis` refuse une cause racine absente des constats.

Le système n'a pas le droit de « penser » qu'un plan est raté. Il doit le
montrer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pdz2.contracts.enums import Severity
from pdz2.contracts.observation import (
    FailureDiagnosis,
    FailureFinding,
    FailureKind,
    ObservationReport,
)
from pdz2.contracts.render import RenderSpecExecutable

__all__ = ["FailureDiagnoser", "DiagnosisOutcome", "CHECK_TO_FAILURE"]

CHECK_TO_FAILURE: dict[str, tuple[FailureKind, tuple[str, ...]]] = {
    "motion_present": (
        FailureKind.NO_MOTION,
        ("motion_first_to_last", "motion_mean_abs_diff"),
    ),
    "not_frozen": (FailureKind.NO_MOTION, ("frozen_frame_ratio",)),
    "stillness": (FailureKind.EXCESSIVE_MOTION, ("motion_first_to_last",)),
    "duration": (FailureKind.DURATION_MISMATCH, ("duration_s", "frame_count")),
    "resolution": (FailureKind.PROVIDER_ERROR, ("frame_count",)),
    "fps": (FailureKind.TEMPORAL_DRIFT, ("fps", "frame_count")),
    "not_black": (FailureKind.BLACK_FRAMES, ("black_frame_ratio",)),
    "not_blank": (FailureKind.ARTIFACTING, ("sharpness",)),
    "palette": (FailureKind.STYLE_DRIFT, ("palette_distance",)),
}
"""Traduction d'un contrôle en échec vers une cause nommée et ses preuves.

Une table plutôt qu'une cascade de conditions : elle se lit, elle se complète,
et un contrôle sans traduction se voit immédiatement.
"""

_SEVERITY_CONFIDENCE = {
    Severity.BLOCKING: 0.95,
    Severity.MAJOR: 0.8,
    Severity.MINOR: 0.5,
    Severity.INFO: 0.3,
}

_ROOT_PRIORITY = (
    FailureKind.PROVIDER_ERROR,
    FailureKind.BLACK_FRAMES,
    FailureKind.ARTIFACTING,
    FailureKind.NO_MOTION,
    FailureKind.EXCESSIVE_MOTION,
    FailureKind.DURATION_MISMATCH,
    FailureKind.TEMPORAL_DRIFT,
    FailureKind.STYLE_DRIFT,
)
"""Ordre de priorité des causes racines.

Une image noire explique l'absence de mouvement ; l'inverse est faux. La
racine est la cause la plus en amont, pas la plus visible.
"""

_UNRECOVERABLE = frozenset({FailureKind.PROVIDER_ERROR})


@dataclass
class DiagnosisOutcome:
    diagnoses: list[FailureDiagnosis]
    notes: list[str] = field(default_factory=list)

    def for_shot(self, shot_id: str) -> FailureDiagnosis:
        for diagnosis in self.diagnoses:
            if diagnosis.shot_id == shot_id:
                return diagnosis
        raise KeyError(shot_id)


@dataclass
class FailureDiagnoser:
    """Traduit des mesures en causes, sans jamais en inventer."""

    def diagnose(
        self,
        *,
        reports: list[ObservationReport],
        executables: list[RenderSpecExecutable],
    ) -> DiagnosisOutcome:
        by_shot = {executable.shot_id: executable for executable in executables}
        diagnoses: list[FailureDiagnosis] = []

        for report in reports:
            if report.passed:
                continue
            findings = self._findings(report)
            if not findings:
                # Un rapport en échec sans contrôle traduisible signale un trou
                # dans la table, pas un plan sain : on le dit.
                findings = [
                    FailureFinding(
                        kind=FailureKind.PROVIDER_ERROR,
                        explanation=(
                            "rapport non conforme dont aucun contrôle en échec "
                            "n'a de traduction connue — la table de diagnostic "
                            "est incomplète"
                        ),
                        evidence_measurements=[
                            report.measurements[0].name
                        ]
                        if report.measurements
                        else ["aucune"],
                        failed_check_ids=[
                            check.check_id for check in report.checks if not check.passed
                        ],
                        confidence=0.4,
                        severity=Severity.MAJOR,
                    )
                ]
            root = self._root_cause(findings)
            executable = by_shot.get(report.shot_id or "")
            diagnoses.append(
                FailureDiagnosis(
                    observation_id=report.id,
                    shot_id=report.shot_id,
                    findings=findings,
                    root_cause=root,
                    recoverable=root not in _UNRECOVERABLE,
                    explanation=self._explain(report, findings, root, executable),
                    parent_id=report.id,
                )
            )

        return DiagnosisOutcome(
            diagnoses=diagnoses,
            notes=[
                f"{len(diagnoses)} plan(s) diagnostiqué(s) sur "
                f"{len(reports)} observé(s)",
                "chaque constat cite les mesures qui l'étayent",
            ],
        )

    # ------------------------------------------------------------------ règles

    @staticmethod
    def _findings(report: ObservationReport) -> list[FailureFinding]:
        available = {measurement.name for measurement in report.measurements}
        findings: list[FailureFinding] = []
        for check in report.checks:
            if check.passed:
                continue
            entry = CHECK_TO_FAILURE.get(check.check_id)
            if entry is None:
                continue
            kind, evidence = entry
            cited = [name for name in evidence if name in available]
            if not cited:
                continue
            findings.append(
                FailureFinding(
                    kind=kind,
                    explanation=(
                        f"contrôle « {check.name} » en échec : observé "
                        f"{check.observed}, attendu {check.expected}"
                        + (f" ± {check.tolerance}" if check.tolerance else "")
                        + (f" — {check.detail}" if check.detail else "")
                    ),
                    evidence_measurements=cited,
                    failed_check_ids=[check.check_id],
                    confidence=_SEVERITY_CONFIDENCE[check.severity],
                    severity=check.severity,
                )
            )
        return findings

    @staticmethod
    def _root_cause(findings: list[FailureFinding]) -> FailureKind:
        kinds = {finding.kind for finding in findings}
        for candidate in _ROOT_PRIORITY:
            if candidate in kinds:
                return candidate
        return findings[0].kind

    @staticmethod
    def _explain(report, findings, root, executable) -> str:
        strategy = executable.strategy.value if executable else "inconnue"
        blocking = sum(
            1 for finding in findings if finding.severity is Severity.BLOCKING
        )
        return (
            f"plan {report.shot_id} rendu par « {strategy} » : "
            f"{len(findings)} constat(s) dont {blocking} bloquant(s), "
            f"cause racine « {root.value} »"
        )
