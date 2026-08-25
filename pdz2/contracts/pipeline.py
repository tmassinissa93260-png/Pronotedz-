"""Vocabulaire de la machine à états et instantané d'épisode.

Le compilateur avance étape par étape. Chaque étape a un état, chaque
transition est journalisée, et l'ensemble se sérialise : un épisode
interrompu se reprend sans rejouer ce qui a déjà coûté.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Self

from pydantic import Field, model_validator

from pdz2.contracts.base import Contract, Element, contract

__all__ = [
    "Stage",
    "StageStatus",
    "EpisodeStatus",
    "StageState",
    "StateTransition",
    "EpisodeSnapshot",
]


class Stage(str, Enum):
    """Étapes du compilateur, de l'idée au MP4."""

    RESEARCH = "research"
    DIRECTION = "direction"
    SCRIPT = "script"
    VOICE = "voice"
    TIMELINE = "timeline"
    VISUAL_BIBLE = "visual_bible"
    SHOT_GRAPH = "shot_graph"
    MOTION = "motion"
    RENDER_SPEC = "render_spec"
    STATIC_VALIDATION = "static_validation"
    ROUTING = "routing"
    ASSETS = "assets"
    RENDER = "render"
    OBSERVATION = "observation"
    DIAGNOSIS = "diagnosis"
    REPAIR = "repair"
    EDIT = "edit"
    AUDIO_MASTER = "audio_master"
    SUBTITLES = "subtitles"
    FINAL_QA = "final_qa"
    DELIVERY = "delivery"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


TERMINAL_STAGE_STATUSES = frozenset({StageStatus.DONE, StageStatus.SKIPPED})


class EpisodeStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    BLOCKED = "blocked"
    """Arrêt en attente d'un humain ou d'une ressource."""

    FAILED = "failed"
    DELIVERED = "delivered"
    ABANDONED = "abandoned"


class StageState(Element):
    """État d'une étape. Une liste typée, jamais un dictionnaire libre."""

    stage: Stage
    status: StageStatus = StageStatus.PENDING
    attempts: int = Field(default=0, ge=0)
    artifact_ids: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    detail: str = ""
    """Motif d'échec ou de saut. Obligatoire pour SKIPPED et FAILED."""

    cost_usd: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def _explained(self) -> Self:
        if self.status in {StageStatus.SKIPPED, StageStatus.FAILED} and not self.detail:
            raise ValueError(
                f"étape {self.stage.value} en {self.status.value} sans motif"
            )
        if self.status is StageStatus.PENDING and self.artifact_ids:
            raise ValueError(f"étape {self.stage.value} en attente avec des artefacts")
        return self


@contract("state_transition", "1.0.0")
class StateTransition(Contract):
    """Une ligne du journal d'états. Immuable une fois écrite."""

    episode_id: str = Field(min_length=1)
    stage: Stage
    from_status: StageStatus
    to_status: StageStatus
    at: datetime
    reason: str = Field(min_length=1)
    actor: str = Field(default="system", min_length=1)
    cost_usd: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def _is_a_change(self) -> Self:
        if self.from_status is self.to_status:
            raise ValueError(
                f"transition sans changement sur {self.stage.value} "
                f"({self.from_status.value})"
            )
        if self.at.tzinfo is None:
            raise ValueError("horodatage de transition sans fuseau")
        return self


@contract("episode_snapshot", "1.0.0")
class EpisodeSnapshot(Contract):
    """État complet et reprenable d'un épisode."""

    episode_id: str = Field(min_length=1)
    topic_request_id: str = Field(min_length=1)
    episode_status: EpisodeStatus = EpisodeStatus.CREATED
    stages: list[StageState] = Field(min_length=1)
    repair_cycles: int = Field(default=0, ge=0)
    max_repair_cycles: int = Field(default=3, ge=0, le=20)
    spent_usd: float = Field(default=0.0, ge=0.0)
    budget_cap_usd: float | None = Field(default=None, ge=0.0)
    transitions: list[StateTransition] = Field(default_factory=list)

    @model_validator(mode="after")
    def _covers_every_stage_once(self) -> Self:
        seen = [state.stage for state in self.stages]
        if len(set(seen)) != len(seen):
            raise ValueError("instantané : étape en double")
        missing = [stage for stage in Stage if stage not in set(seen)]
        if missing:
            raise ValueError(
                "instantané incomplet, étapes absentes : "
                + ", ".join(stage.value for stage in missing)
            )
        if self.repair_cycles > self.max_repair_cycles:
            raise ValueError(
                f"{self.repair_cycles} cycles de réparation au-dessus du "
                f"plafond {self.max_repair_cycles}"
            )
        if self.budget_cap_usd is not None and self.spent_usd > self.budget_cap_usd + 1e-9:
            raise ValueError(
                f"dépense {self.spent_usd} USD au-dessus du plafond "
                f"{self.budget_cap_usd} USD"
            )
        return self

    def state(self, stage: Stage) -> StageState:
        for item in self.stages:
            if item.stage is stage:
                return item
        raise KeyError(stage)
