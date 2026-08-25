"""Observation déterministe, diagnostic et réparation.

OBSERVERS MEASURE. DIAGNOSTICS EXPLAIN. REPAIR COMPILERS ADAPT.
FALLBACKS GUARANTEE DELIVERY.

Un diagnostic sans mesure citée est refusé : le système n'a pas le droit de
« penser » qu'un plan est raté, il doit le montrer.
"""

from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import Field, model_validator

from pdz2.contracts.base import Contract, Element, contract
from pdz2.contracts.common import QaCheck
from pdz2.contracts.enums import Severity
from pdz2.contracts.pipeline import Stage
from pdz2.contracts.render import RenderStrategy

__all__ = [
    "Measurement",
    "ObservationReport",
    "FailureKind",
    "FailureFinding",
    "FailureDiagnosis",
    "RepairAction",
    "RepairStep",
    "RepairPlan",
    "GUARANTEED_FALLBACKS",
]


class Measurement(Element):
    """Une grandeur mesurée sur un artefact, avec sa méthode."""

    name: str = Field(min_length=1)
    value: float
    unit: str = Field(min_length=1)
    method: str = Field(min_length=1)
    """Comment la valeur a été obtenue : le diagnostic doit être rejouable."""

    deterministic: bool = True
    """Faux : la mesure dépend d'un modèle, elle ne bloque jamais seule."""


@contract("observation_report", "1.0.0")
class ObservationReport(Contract):
    """Mesures et vérifications sur un artefact rendu."""

    artifact_id: str = Field(min_length=1)
    shot_id: str | None = None
    observer_version: str = Field(min_length=1)
    measurements: list[Measurement] = Field(default_factory=list)
    checks: list[QaCheck] = Field(min_length=1)
    passed: bool

    @model_validator(mode="after")
    def _verdict_follows_the_checks(self) -> Self:
        check_ids = [check.check_id for check in self.checks]
        if len(set(check_ids)) != len(check_ids):
            raise ValueError("rapport d'observation : check_id en double")
        blocking_failed = [
            check.check_id
            for check in self.checks
            if check.severity is Severity.BLOCKING and not check.passed
        ]
        if self.passed and blocking_failed:
            raise ValueError(
                f"rapport déclaré conforme malgré des blocages : {blocking_failed}"
            )
        if not self.passed and not blocking_failed:
            major_failed = [
                check.check_id
                for check in self.checks
                if check.severity is Severity.MAJOR and not check.passed
            ]
            if not major_failed:
                raise ValueError(
                    "rapport déclaré non conforme sans échec majeur ni bloquant"
                )
        return self

    @property
    def deterministic(self) -> bool:
        """Vrai si toutes les mesures sont reproductibles."""
        return all(measurement.deterministic for measurement in self.measurements)

    def measurement(self, name: str) -> Measurement:
        for measurement in self.measurements:
            if measurement.name == name:
                return measurement
        raise KeyError(name)


class FailureKind(str, Enum):
    NO_MOTION = "no_motion"
    WRONG_MOTION = "wrong_motion"
    EXCESSIVE_MOTION = "excessive_motion"
    IDENTITY_DRIFT = "identity_drift"
    GEOMETRY_BREAK = "geometry_break"
    TEMPORAL_DRIFT = "temporal_drift"
    DURATION_MISMATCH = "duration_mismatch"
    BLACK_FRAMES = "black_frames"
    ARTIFACTING = "artifacting"
    STYLE_DRIFT = "style_drift"
    VISUAL_REPETITION = "visual_repetition"
    AUDIO_DESYNC = "audio_desync"
    LOUDNESS_OUT_OF_RANGE = "loudness_out_of_range"
    SUBTITLE_DESYNC = "subtitle_desync"
    MISSING_VISUAL_PROOF = "missing_visual_proof"
    PROVIDER_ERROR = "provider_error"
    BUDGET_EXCEEDED = "budget_exceeded"
    CAPABILITY_MISSING = "capability_missing"


class FailureFinding(Element):
    kind: FailureKind
    explanation: str = Field(min_length=1)
    evidence_measurements: list[str] = Field(min_length=1)
    """Noms de mesures du rapport d'observation qui étayent le constat."""

    failed_check_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    severity: Severity = Severity.MAJOR


@contract("failure_diagnosis", "1.0.0")
class FailureDiagnosis(Contract):
    """Explication d'un échec, adossée aux mesures."""

    observation_id: str = Field(min_length=1)
    shot_id: str | None = None
    findings: list[FailureFinding] = Field(min_length=1)
    root_cause: FailureKind
    recoverable: bool = True
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def _root_cause_is_among_the_findings(self) -> Self:
        kinds = {finding.kind for finding in self.findings}
        if self.root_cause not in kinds:
            raise ValueError(
                f"cause racine {self.root_cause.value} absente des constats "
                f"{sorted(kind.value for kind in kinds)}"
            )
        return self


class RepairAction(str, Enum):
    RETRY_SAME = "retry_same"
    RETRY_NEW_SEED = "retry_new_seed"
    CHANGE_STRATEGY = "change_strategy"
    SIMPLIFY_MOTION = "simplify_motion"
    REGENERATE_ASSET = "regenerate_asset"
    REINFORCE_ANCHOR = "reinforce_anchor"
    SPLIT_SHOT = "split_shot"
    SHORTEN_SHOT = "shorten_shot"
    FALLBACK_2_5D = "fallback_2_5d"
    FALLBACK_KEN_BURNS = "fallback_ken_burns"
    FALLBACK_STILL = "fallback_still"
    ESCALATE_HUMAN = "escalate_human"


GUARANTEED_FALLBACKS = frozenset(
    {
        RepairAction.FALLBACK_2_5D,
        RepairAction.FALLBACK_KEN_BURNS,
        RepairAction.FALLBACK_STILL,
        RepairAction.ESCALATE_HUMAN,
    }
)
"""Actions terminales : elles n'exigent aucun fournisseur vidéo pour aboutir."""


class RepairStep(Element):
    action: RepairAction
    rationale: str = Field(min_length=1)
    target_stage: Stage
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    expected_effect: str = Field(min_length=1)

    @model_validator(mode="after")
    def _free_fallbacks_stay_free(self) -> Self:
        if (
            self.action in {RepairAction.FALLBACK_STILL, RepairAction.FALLBACK_KEN_BURNS}
            and self.estimated_cost_usd > 0.0
        ):
            raise ValueError(
                f"repli local {self.action.value} chiffré à "
                f"{self.estimated_cost_usd} USD : un repli déterministe est gratuit"
            )
        return self


@contract("repair_plan", "1.1.0")
class RepairPlan(Contract):
    """Suite d'actions bornée, avec un repli qui aboutit toujours."""

    diagnosis_id: str = Field(min_length=1)
    shot_id: str | None = None
    steps: list[RepairStep] = Field(min_length=1)
    cycle: int = Field(ge=1)
    max_cycles: int = Field(default=3, ge=1, le=20)
    guaranteed_fallback: RepairAction
    """Ce qui sera fait si toutes les étapes échouent. Livraison garantie."""

    forbidden_strategies: list[RenderStrategy] = Field(default_factory=list)
    """Stratégies que ce plan interdit désormais sur son plan de tournage.

    Ajouté en 1.1.0, et c'est une correction de frontière, pas un confort. Ce
    que le cycle de réparation suivant doit savoir — « n'essaie plus celle-ci,
    elle a déjà échoué ici » — vivait dans un JSON libre à côté des contrats
    (`repairs/forbidden_strategies.json`). Le `RepairPlan` était produit,
    persisté, puis jamais relu : l'état réel de la boucle était porté par un
    dictionnaire arbitraire, ce que le §4 interdit.

    Absent des documents 1.0.0, où il vaut une liste vide — un épisode
    d'avant cette version n'interdisait rien de façon lisible."""

    @model_validator(mode="after")
    def _bounded_and_guaranteed(self) -> Self:
        if self.cycle > self.max_cycles:
            raise ValueError(
                f"cycle {self.cycle} au-dessus du plafond {self.max_cycles}"
            )
        if self.guaranteed_fallback not in GUARANTEED_FALLBACKS:
            raise ValueError(
                f"repli garanti invalide : {self.guaranteed_fallback.value} "
                "dépend d'un fournisseur, il ne garantit rien"
            )
        if self.cycle == self.max_cycles:
            last = self.steps[-1].action
            if last not in GUARANTEED_FALLBACKS:
                raise ValueError(
                    "dernier cycle de réparation : la dernière étape doit être un "
                    f"repli garanti, pas {last.value}"
                )
        return self

    @property
    def total_estimated_cost_usd(self) -> float:
        return sum(step.estimated_cost_usd for step in self.steps)
