"""Compilateur de réparation.

    REPAIR COMPILERS ADAPT.  FALLBACKS GUARANTEE DELIVERY.

Il transforme un diagnostic en un plan d'actions **borné**, dont la dernière
aboutit toujours. Il ne réessaie pas au hasard : chaque cause a sa réponse, et
chaque réponse dit à quelle étape rembobiner.

Trois garanties, tenues par les contrats autant que par le code :

* **borné** — le cycle ne dépasse jamais son plafond ; au dernier cycle, la
  dernière action doit être un repli garanti, et `RepairPlan` le refuse sinon ;
* **gratuit en dernier recours** — un repli local n'a pas le droit d'être
  chiffré, et le contrat le refuse ;
* **traçable** — la stratégie mise en échec est enregistrée, et le routeur ne
  la reproposera pas au cycle suivant.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pdz2.contracts.observation import (
    GUARANTEED_FALLBACKS,
    FailureDiagnosis,
    FailureKind,
    RepairAction,
    RepairPlan,
    RepairStep,
)
from pdz2.contracts.pipeline import Stage
from pdz2.contracts.render import (
    DETERMINISTIC_STRATEGIES,
    RenderSpecExecutable,
    RenderStrategy,
)

__all__ = ["RepairCompiler", "RepairOutcome", "RepairRejected", "RESPONSES"]


class RepairRejected(ValueError):
    """Le diagnostic ne permet pas de composer un plan de réparation."""


@dataclass(frozen=True)
class Response:
    """Réponse prévue pour une cause. Ni improvisée, ni générique."""

    action: RepairAction
    target_stage: Stage
    rationale: str
    expected_effect: str


RESPONSES: dict[FailureKind, Response] = {
    FailureKind.NO_MOTION: Response(
        action=RepairAction.CHANGE_STRATEGY,
        target_stage=Stage.ROUTING,
        rationale=(
            "la stratégie retenue n'a produit aucun déplacement mesurable : "
            "en changer est plus sûr que la rejouer"
        ),
        expected_effect="le déplacement bout-à-bout repasse au-dessus du plancher",
    ),
    FailureKind.EXCESSIVE_MOTION: Response(
        action=RepairAction.SIMPLIFY_MOTION,
        target_stage=Stage.MOTION,
        rationale="un plan voulu fixe bouge : la cible de mouvement est à baisser",
        expected_effect="le déplacement retombe sous le plafond d'immobilité",
    ),
    FailureKind.BLACK_FRAMES: Response(
        action=RepairAction.REGENERATE_ASSET,
        target_stage=Stage.ASSETS,
        rationale="une image noire vient de l'image de départ, pas du mouvement",
        expected_effect="le plan retrouve une luminance exploitable",
    ),
    FailureKind.ARTIFACTING: Response(
        action=RepairAction.REGENERATE_ASSET,
        target_stage=Stage.ASSETS,
        rationale="une image sans contour est une image vide : la source est en cause",
        expected_effect="le plan retrouve de la matière visible",
    ),
    FailureKind.DURATION_MISMATCH: Response(
        action=RepairAction.RETRY_SAME,
        target_stage=Stage.RENDER,
        rationale=(
            "la durée rendue ne correspond pas à la demande : le rendu a été "
            "tronqué ou allongé, une seconde exécution tranche"
        ),
        expected_effect="la durée retombe dans la tolérance du montage",
    ),
    FailureKind.TEMPORAL_DRIFT: Response(
        action=RepairAction.RETRY_SAME,
        target_stage=Stage.RENDER,
        rationale="la cadence mesurée s'écarte de la demande",
        expected_effect="la cadence redevient celle du plan d'exécution",
    ),
    FailureKind.STYLE_DRIFT: Response(
        action=RepairAction.REGENERATE_ASSET,
        target_stage=Stage.ASSETS,
        rationale="l'image s'éloigne du registre chromatique de la bible",
        expected_effect="la distance à la palette repasse sous le seuil",
    ),
    FailureKind.IDENTITY_DRIFT: Response(
        action=RepairAction.REINFORCE_ANCHOR,
        target_stage=Stage.ASSETS,
        rationale="l'ancre de continuité n'a pas tenu d'un plan à l'autre",
        expected_effect="les traits d'identité fixes redeviennent constants",
    ),
    FailureKind.PROVIDER_ERROR: Response(
        action=RepairAction.CHANGE_STRATEGY,
        target_stage=Stage.ROUTING,
        rationale="l'exécutant a échoué : en changer plutôt que le rappeler",
        expected_effect="un autre exécutant produit le plan",
    ),
}
"""Une réponse par cause. Une cause sans réponse est un trou, pas un cas général."""

_FALLBACK_BY_CYCLE: tuple[RepairAction, ...] = (
    RepairAction.FALLBACK_2_5D,
    RepairAction.FALLBACK_KEN_BURNS,
    RepairAction.FALLBACK_STILL,
)
"""Replis, du plus riche au plus sobre, à mesure que les cycles s'épuisent."""


@dataclass
class RepairOutcome:
    plans: list[RepairPlan]
    forbidden_strategies: dict[str, set[RenderStrategy]] = field(default_factory=dict)
    """Stratégies à ne plus proposer, par plan. À passer au routeur."""

    notes: list[str] = field(default_factory=list)

    def for_shot(self, shot_id: str) -> RepairPlan:
        for plan in self.plans:
            if plan.shot_id == shot_id:
                return plan
        raise KeyError(shot_id)

    @property
    def rewind_stages(self) -> set[Stage]:
        """Étapes à rembobiner pour que la réparation prenne effet."""
        return {step.target_stage for plan in self.plans for step in plan.steps}


@dataclass
class RepairCompiler:
    max_cycles: int = 3

    def compile(
        self,
        *,
        diagnoses: list[FailureDiagnosis],
        executables: list[RenderSpecExecutable],
        cycle: int,
        already_forbidden: dict[str, set[RenderStrategy]] | None = None,
    ) -> RepairOutcome:
        if cycle < 1:
            raise RepairRejected("un cycle de réparation commence à 1")
        if cycle > self.max_cycles:
            raise RepairRejected(
                f"cycle {cycle} au-delà du plafond {self.max_cycles} : "
                "passer au repli garanti"
            )
        by_shot = {executable.shot_id: executable for executable in executables}
        forbidden = {
            shot: set(strategies)
            for shot, strategies in (already_forbidden or {}).items()
        }
        plans: list[RepairPlan] = []

        for diagnosis in diagnoses:
            shot_id = diagnosis.shot_id
            executable = by_shot.get(shot_id or "")
            steps = self._steps(diagnosis, executable, cycle)
            fallback = self._guaranteed_fallback(cycle)
            plans.append(
                RepairPlan(
                    diagnosis_id=diagnosis.id,
                    shot_id=shot_id,
                    steps=steps,
                    cycle=cycle,
                    max_cycles=self.max_cycles,
                    guaranteed_fallback=fallback,
                    parent_id=diagnosis.id,
                )
            )
            if shot_id and executable is not None and self._blames_strategy(diagnosis):
                forbidden.setdefault(shot_id, set()).add(executable.strategy)

        return RepairOutcome(
            plans=plans,
            forbidden_strategies=forbidden,
            notes=[
                f"cycle {cycle}/{self.max_cycles} : {len(plans)} plan(s) à réparer",
                "stratégies écartées : "
                + (
                    ", ".join(
                        f"{shot}→{sorted(s.value for s in strategies)}"
                        for shot, strategies in sorted(forbidden.items())
                    )
                    or "aucune"
                ),
                "étapes à rembobiner : "
                + ", ".join(
                    sorted(
                        stage.value
                        for plan in plans
                        for step in plan.steps
                        for stage in [step.target_stage]
                    )
                )
                or "aucune",
            ],
        )

    # ------------------------------------------------------------------ règles

    def _steps(
        self,
        diagnosis: FailureDiagnosis,
        executable: RenderSpecExecutable | None,
        cycle: int,
    ) -> list[RepairStep]:
        """Une étape par cause distincte, plus le repli au dernier cycle."""
        steps: list[RepairStep] = []
        seen: set[FailureKind] = set()
        ordered = sorted(
            diagnosis.findings, key=lambda finding: -finding.confidence
        )
        for finding in ordered:
            if finding.kind in seen:
                continue
            seen.add(finding.kind)
            response = RESPONSES.get(finding.kind)
            if response is None:
                raise RepairRejected(
                    f"aucune réponse prévue pour « {finding.kind.value} » — "
                    "compléter la table plutôt qu'improviser"
                )
            if (
                response.action is RepairAction.CHANGE_STRATEGY
                and executable is not None
                and not self._has_another_strategy(executable)
            ):
                # Plus rien à changer : autant aller directement au repli.
                continue
            steps.append(
                RepairStep(
                    action=response.action,
                    rationale=response.rationale,
                    target_stage=response.target_stage,
                    estimated_cost_usd=0.0,
                    expected_effect=response.expected_effect,
                )
            )

        if cycle == self.max_cycles or not steps:
            fallback = self._guaranteed_fallback(cycle)
            steps.append(
                RepairStep(
                    action=fallback,
                    rationale=(
                        f"dernier cycle ({cycle}/{self.max_cycles}) : garantir la "
                        "livraison plutôt que perdre le plan"
                        if cycle == self.max_cycles
                        else "aucune adaptation possible : replier tout de suite"
                    ),
                    target_stage=Stage.ROUTING,
                    estimated_cost_usd=0.0,
                    expected_effect=(
                        "le plan est produit par une stratégie qui aboutit toujours"
                    ),
                )
            )
        return steps

    def _guaranteed_fallback(self, cycle: int) -> RepairAction:
        index = min(cycle - 1, len(_FALLBACK_BY_CYCLE) - 1)
        fallback = _FALLBACK_BY_CYCLE[index]
        if fallback not in GUARANTEED_FALLBACKS:  # pragma: no cover - garde
            raise RepairRejected(f"repli non garanti : {fallback}")
        return fallback

    @staticmethod
    def _has_another_strategy(executable: RenderSpecExecutable) -> bool:
        remaining = DETERMINISTIC_STRATEGIES - {executable.strategy}
        return bool(remaining)

    @staticmethod
    def _blames_strategy(diagnosis: FailureDiagnosis) -> bool:
        return diagnosis.root_cause in {
            FailureKind.NO_MOTION,
            FailureKind.EXCESSIVE_MOTION,
            FailureKind.PROVIDER_ERROR,
        }
