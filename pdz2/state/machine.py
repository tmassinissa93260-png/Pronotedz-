"""Machine à états d'un épisode.

Reprenable : tout l'état tient dans un `EpisodeSnapshot` sérialisable.
Observable : chaque changement produit une `StateTransition` horodatée et
motivée. Bornée : les cycles de réparation et le budget sont plafonnés.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from pdz2.contracts.pipeline import (
    TERMINAL_STAGE_STATUSES,
    EpisodeSnapshot,
    EpisodeStatus,
    Stage,
    StageState,
    StageStatus,
    StateTransition,
)
from pdz2.state.stages import COST_GATE, STAGE_ORDER, definition, transitive_dependents

__all__ = ["TransitionRefused", "BudgetExceeded", "EpisodeStateMachine"]


class TransitionRefused(RuntimeError):
    """Transition interdite par les règles de la machine."""


class BudgetExceeded(TransitionRefused):
    """La dépense franchirait le plafond déclaré."""


_TERMINAL_EPISODE_STATUSES = frozenset(
    {EpisodeStatus.DELIVERED, EpisodeStatus.FAILED, EpisodeStatus.ABANDONED}
)


class EpisodeStateMachine:
    """Pilote l'avancement d'un épisode et refuse les enchaînements invalides."""

    def __init__(self, snapshot: EpisodeSnapshot) -> None:
        self._snapshot = snapshot

    # ------------------------------------------------------------- construction

    @classmethod
    def create(
        cls,
        *,
        episode_id: str,
        topic_request_id: str,
        budget_cap_usd: float | None = None,
        max_repair_cycles: int = 3,
    ) -> EpisodeStateMachine:
        snapshot = EpisodeSnapshot(
            episode_id=episode_id,
            topic_request_id=topic_request_id,
            budget_cap_usd=budget_cap_usd,
            max_repair_cycles=max_repair_cycles,
            stages=[StageState(stage=stage) for stage in STAGE_ORDER],
        )
        return cls(snapshot)

    @classmethod
    def resume(cls, snapshot: EpisodeSnapshot) -> EpisodeStateMachine:
        """Reprend un épisode interrompu, sans rejouer ce qui est fait."""
        return cls(snapshot.model_copy(deep=True))

    # ------------------------------------------------------------------ lecture

    @property
    def snapshot(self) -> EpisodeSnapshot:
        return self._snapshot

    @property
    def episode_status(self) -> EpisodeStatus:
        return self._snapshot.episode_status

    @property
    def spent_usd(self) -> float:
        return self._snapshot.spent_usd

    @property
    def transitions(self) -> list[StateTransition]:
        return list(self._snapshot.transitions)

    def status(self, stage: Stage) -> StageStatus:
        return self._snapshot.state(stage).status

    def state(self, stage: Stage) -> StageState:
        return self._snapshot.state(stage)

    def is_ready(self, stage: Stage) -> bool:
        """Vrai si `stage` peut démarrer maintenant."""
        try:
            self._check_can_start(stage)
        except TransitionRefused:
            return False
        return True

    def ready_stages(self) -> list[Stage]:
        return [stage for stage in STAGE_ORDER if self.is_ready(stage)]

    def blocking_reasons(self, stage: Stage) -> list[str]:
        """Ce qui empêche `stage` de démarrer. Vide si elle est prête."""
        try:
            self._check_can_start(stage)
        except TransitionRefused as refusal:
            return [str(refusal)]
        return []

    def is_complete(self) -> bool:
        return self.status(Stage.DELIVERY) is StageStatus.DONE

    # --------------------------------------------------------------- transitions

    def start(
        self,
        stage: Stage,
        *,
        reason: str = "démarrage",
        actor: str = "system",
    ) -> StageState:
        self._check_can_start(stage)
        state = self._snapshot.state(stage)
        previous = state.status
        state.status = StageStatus.RUNNING
        state.attempts += 1
        state.started_at = _now()
        state.ended_at = None
        state.detail = ""
        self._record(stage, previous, StageStatus.RUNNING, reason, actor)
        if self._snapshot.episode_status is EpisodeStatus.CREATED:
            self._snapshot.episode_status = EpisodeStatus.RUNNING
        return state

    def complete(
        self,
        stage: Stage,
        *,
        artifact_ids: Iterable[str] = (),
        cost_usd: float = 0.0,
        reason: str = "terminée",
        actor: str = "system",
    ) -> StageState:
        state = self._snapshot.state(stage)
        if state.status is not StageStatus.RUNNING:
            raise TransitionRefused(
                f"{stage.value} : on ne termine que ce qui tourne "
                f"(état actuel {state.status.value})"
            )
        if cost_usd < 0.0:
            raise TransitionRefused("un coût négatif n'existe pas")
        if cost_usd > 0.0 and not definition(stage).incurs_cost:
            raise TransitionRefused(
                f"{stage.value} est déclarée sans coût mais rapporte {cost_usd} USD"
            )
        self._check_budget(cost_usd)

        state.status = StageStatus.DONE
        state.ended_at = _now()
        state.artifact_ids = list(artifact_ids)
        state.cost_usd += cost_usd
        state.detail = ""
        self._snapshot.spent_usd += cost_usd
        self._record(stage, StageStatus.RUNNING, StageStatus.DONE, reason, actor, cost_usd)
        if stage is Stage.DELIVERY:
            self._snapshot.episode_status = EpisodeStatus.DELIVERED
        return state

    def fail(
        self,
        stage: Stage,
        *,
        reason: str,
        cost_usd: float = 0.0,
        terminal: bool = False,
        actor: str = "system",
    ) -> StageState:
        if not reason.strip():
            raise TransitionRefused("un échec sans motif n'est pas diagnosticable")
        state = self._snapshot.state(stage)
        if state.status is not StageStatus.RUNNING:
            raise TransitionRefused(
                f"{stage.value} : on n'échoue que ce qui tourne "
                f"(état actuel {state.status.value})"
            )
        self._check_budget(cost_usd)
        state.detail = reason
        state.status = StageStatus.FAILED
        state.ended_at = _now()
        state.cost_usd += cost_usd
        self._snapshot.spent_usd += cost_usd
        self._record(stage, StageStatus.RUNNING, StageStatus.FAILED, reason, actor, cost_usd)
        self._snapshot.episode_status = (
            EpisodeStatus.FAILED if terminal else EpisodeStatus.BLOCKED
        )
        return state

    def skip(
        self,
        stage: Stage,
        *,
        reason: str,
        actor: str = "system",
    ) -> StageState:
        if not definition(stage).optional:
            raise TransitionRefused(f"{stage.value} n'est pas sautable")
        if not reason.strip():
            raise TransitionRefused(f"{stage.value} : un saut exige un motif")
        state = self._snapshot.state(stage)
        if state.status not in {StageStatus.PENDING, StageStatus.FAILED}:
            raise TransitionRefused(
                f"{stage.value} : saut impossible depuis {state.status.value}"
            )
        previous = state.status
        state.detail = reason
        state.status = StageStatus.SKIPPED
        state.ended_at = _now()
        self._record(stage, previous, StageStatus.SKIPPED, reason, actor)
        return state

    def rewind(
        self,
        stage: Stage,
        *,
        reason: str,
        actor: str = "repair",
        count_as_repair_cycle: bool = True,
    ) -> list[Stage]:
        """Remet `stage` et tout son aval en attente.

        Utilisé par le Repair Compiler : réparer un plan invalide tout ce qui
        en dérivait. Les cycles sont plafonnés pour que la boucle termine.
        """
        if not reason.strip():
            raise TransitionRefused("un rembobinage exige un motif")
        if count_as_repair_cycle:
            if self._snapshot.repair_cycles >= self._snapshot.max_repair_cycles:
                raise TransitionRefused(
                    f"plafond de réparation atteint "
                    f"({self._snapshot.max_repair_cycles} cycles) : "
                    "passer au repli garanti"
                )
            self._snapshot.repair_cycles += 1

        affected = [stage, *transitive_dependents(stage)]
        rewound: list[Stage] = []
        for target in affected:
            state = self._snapshot.state(target)
            if state.status is StageStatus.PENDING:
                continue
            previous = state.status
            state.artifact_ids = []
            state.status = StageStatus.PENDING
            state.started_at = None
            state.ended_at = None
            state.detail = ""
            self._record(target, previous, StageStatus.PENDING, reason, actor)
            rewound.append(target)
        if self._snapshot.episode_status in {EpisodeStatus.BLOCKED, EpisodeStatus.FAILED}:
            self._snapshot.episode_status = EpisodeStatus.RUNNING
        return rewound

    def abandon(self, *, reason: str, actor: str = "human") -> None:
        if not reason.strip():
            raise TransitionRefused("un abandon exige un motif")
        for stage in STAGE_ORDER:
            state = self._snapshot.state(stage)
            if state.status is StageStatus.RUNNING:
                state.detail = reason
                state.status = StageStatus.FAILED
                state.ended_at = _now()
                self._record(stage, StageStatus.RUNNING, StageStatus.FAILED, reason, actor)
        self._snapshot.episode_status = EpisodeStatus.ABANDONED

    # ------------------------------------------------------------------- règles

    def _check_can_start(self, stage: Stage) -> None:
        if self._snapshot.episode_status in _TERMINAL_EPISODE_STATUSES:
            raise TransitionRefused(
                f"épisode {self._snapshot.episode_status.value} : plus rien ne démarre"
            )
        state = self._snapshot.state(stage)
        if state.status is StageStatus.RUNNING:
            raise TransitionRefused(f"{stage.value} tourne déjà")
        if state.status in TERMINAL_STAGE_STATUSES:
            raise TransitionRefused(
                f"{stage.value} est déjà {state.status.value} : "
                "rembobiner avant de relancer"
            )

        spec = definition(stage)
        if spec.gated_by_validation and self.status(COST_GATE) is not StageStatus.DONE:
            raise TransitionRefused(
                f"{stage.value} : dépense interdite tant que "
                f"{COST_GATE.value} n'est pas franchie"
            )
        unmet = [
            dependency.value
            for dependency in spec.depends_on
            if self.status(dependency) not in TERMINAL_STAGE_STATUSES
        ]
        if unmet:
            raise TransitionRefused(
                f"{stage.value} : étapes amont non abouties → {', '.join(unmet)}"
            )
        if self._snapshot.budget_cap_usd is not None and spec.incurs_cost:
            if self._snapshot.spent_usd >= self._snapshot.budget_cap_usd:
                raise BudgetExceeded(
                    f"{stage.value} : budget épuisé "
                    f"({self._snapshot.spent_usd} / {self._snapshot.budget_cap_usd} USD)"
                )

    def _check_budget(self, cost_usd: float) -> None:
        cap = self._snapshot.budget_cap_usd
        if cap is None or cost_usd <= 0.0:
            return
        if self._snapshot.spent_usd + cost_usd > cap + 1e-9:
            raise BudgetExceeded(
                f"dépense refusée : {self._snapshot.spent_usd} + {cost_usd} "
                f"dépasserait le plafond {cap} USD"
            )

    def _record(
        self,
        stage: Stage,
        from_status: StageStatus,
        to_status: StageStatus,
        reason: str,
        actor: str,
        cost_usd: float = 0.0,
    ) -> None:
        self._snapshot.transitions.append(
            StateTransition(
                episode_id=self._snapshot.episode_id,
                stage=stage,
                from_status=from_status,
                to_status=to_status,
                at=_now(),
                reason=reason or "sans motif",
                actor=actor,
                cost_usd=cost_usd,
            )
        )


def _now() -> datetime:
    return datetime.now(UTC)
