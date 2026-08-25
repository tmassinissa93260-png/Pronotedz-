"""ABI de rendu : ce qui est demandé, ce qui est exécutable, ce qui est exécuté.

`RenderSpecRequested` appartient à la couche SPÉCIFICATION : il exprime ce
que la réalisation demande, sans nommer de fournisseur. `RenderSpecExecutable`
appartient à la couche EXÉCUTION : il dit ce que l'infrastructure fera
réellement, et **toute divergence avec la demande est enregistrée** sous
forme de `Degradation`. Aucune dégradation silencieuse n'est possible : le
contrat la refuse.
"""

from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import Field, model_validator

from pdz2.contracts.base import Contract, Element, contract
from pdz2.contracts.common import Resolution, TextOverlay
from pdz2.contracts.enums import ArtifactKind
from pdz2.contracts.motion import CameraMove

__all__ = [
    "RenderStrategy",
    "DegradationSeverity",
    "Degradation",
    "RequestedEcho",
    "RenderSpecRequested",
    "RenderSpecExecutable",
    "ExecutionStepKind",
    "ExecutionStep",
    "ExecutionPlan",
    "RenderArtifact",
    "AI_VIDEO_STRATEGIES",
    "DETERMINISTIC_STRATEGIES",
]


class RenderStrategy(str, Enum):
    DIRECT_I2V = "direct_i2v"
    CONTROLLED_I2V = "controlled_i2v"
    VIDEO_EDITING = "video_editing"
    VACE_STYLE_CONDITIONING = "vace_style_conditioning"
    PARALLAX_2_5D = "parallax_2_5d"
    PROCEDURAL = "procedural"
    THREE_D = "3d"
    HYBRID = "hybrid"
    KEN_BURNS = "ken_burns"
    STILL = "still"


AI_VIDEO_STRATEGIES = frozenset(
    {
        RenderStrategy.DIRECT_I2V,
        RenderStrategy.CONTROLLED_I2V,
        RenderStrategy.VIDEO_EDITING,
        RenderStrategy.VACE_STYLE_CONDITIONING,
    }
)
"""Stratégies qui exigent un générateur vidéo par IA."""

DETERMINISTIC_STRATEGIES = frozenset(
    {
        RenderStrategy.PARALLAX_2_5D,
        RenderStrategy.PROCEDURAL,
        RenderStrategy.KEN_BURNS,
        RenderStrategy.STILL,
    }
)
"""Stratégies reproductibles, disponibles sans aucun fournisseur vidéo."""


class DegradationSeverity(str, Enum):
    COSMETIC = "cosmetic"
    """Invisible pour le spectateur."""

    PERCEPTUAL = "perceptual"
    """Visible, mais la démonstration tient."""

    NARRATIVE = "narrative"
    """La preuve visuelle est affaiblie : à remonter au diagnostic."""


class Degradation(Element):
    """Trace explicite d'un écart entre la demande et l'exécution."""

    field: str = Field(min_length=1)
    requested: str = Field(min_length=1)
    executed: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    """Pourquoi l'infrastructure ne peut pas faire ce qui est demandé."""

    description: str = Field(min_length=1)
    """Ce qui est fait à la place, en clair."""

    severity: DegradationSeverity = DegradationSeverity.PERCEPTUAL


class RequestedEcho(Element):
    """Copie des champs demandés, pour rendre l'écart vérifiable localement."""

    strategy: RenderStrategy | None = None
    camera: CameraMove
    duration_s: float = Field(gt=0.0)
    resolution: Resolution
    fps: int = Field(gt=0)
    text_overlay: TextOverlay | None = None
    """Incrustation demandée. Ajouté en 1.1.0 ; absente des documents 1.0.0."""


@contract("render_spec_requested", "1.1.0")
class RenderSpecRequested(Contract):
    """Ce que la réalisation demande. Aucun fournisseur, aucun modèle."""

    shot_id: str = Field(min_length=1)
    motion_program_id: str = Field(min_length=1)
    camera_program_id: str = Field(min_length=1)
    image_spec_ids: list[str] = Field(default_factory=list)

    duration_s: float = Field(gt=0.0)
    resolution: Resolution
    fps: int = Field(gt=0, le=120)
    text_overlay: TextOverlay | None = None
    """Incrustation de texte à dessiner sur le plan.

    Recopiée depuis `ShotSpec.text_overlay`, jamais décidée ici : le
    compilateur de plans est seul juge de ce qui s'affiche à l'écran. Ce champ
    la transporte jusqu'à l'exécutant, qui la dessine sans savoir pourquoi
    elle existe."""

    requested_camera: CameraMove = CameraMove.LOCK
    preferred_strategy: RenderStrategy | None = None
    """Préférence, pas décision : le routeur tranche."""

    identity_lock_required: bool = False
    allow_ai_video: bool = True
    max_cost_usd: float | None = Field(default=None, ge=0.0)
    deadline_s: float | None = Field(default=None, gt=0.0)

    @model_validator(mode="after")
    def _preference_respects_the_ban(self) -> Self:
        if (
            not self.allow_ai_video
            and self.preferred_strategy in AI_VIDEO_STRATEGIES
        ):
            raise ValueError(
                f"{self.shot_id} : stratégie {self.preferred_strategy.value} "
                "demandée alors que la génération vidéo IA est interdite"
            )
        return self

    def echo(self) -> RequestedEcho:
        return RequestedEcho(
            strategy=self.preferred_strategy,
            camera=self.requested_camera,
            duration_s=self.duration_s,
            resolution=self.resolution,
            fps=self.fps,
            text_overlay=self.text_overlay,
        )


@contract("render_spec_executable", "1.1.0")
class RenderSpecExecutable(Contract):
    """Ce que l'infrastructure exécutera réellement."""

    requested_spec_id: str = Field(min_length=1)
    shot_id: str = Field(min_length=1)
    requested: RequestedEcho

    strategy: RenderStrategy
    execution_camera: CameraMove
    text_overlay: TextOverlay | None = None
    """Incrustation réellement dessinée. Un écart avec la demande se déclare."""

    duration_s: float = Field(gt=0.0)
    resolution: Resolution
    fps: int = Field(gt=0, le=120)

    provider: str | None = None
    """Nom d'adaptateur. `None` pour un rendu local et déterministe."""

    model: str | None = None
    capability_snapshot_id: str | None = None
    """Mesure de capacité sur laquelle ce choix s'appuie (phase 11)."""

    degradations: list[Degradation] = Field(default_factory=list)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def _every_divergence_is_declared(self) -> Self:
        declared = {degradation.field for degradation in self.degradations}
        divergences: list[str] = []
        if self.execution_camera is not self.requested.camera:
            divergences.append("camera")
        if abs(self.duration_s - self.requested.duration_s) > 1e-6:
            divergences.append("duration_s")
        if self.resolution != self.requested.resolution:
            divergences.append("resolution")
        if self.fps != self.requested.fps:
            divergences.append("fps")
        if (
            self.requested.strategy is not None
            and self.strategy is not self.requested.strategy
        ):
            divergences.append("strategy")
        if self.text_overlay != self.requested.text_overlay:
            divergences.append("text_overlay")

        undeclared = [field for field in divergences if field not in declared]
        if undeclared:
            raise ValueError(
                "dégradation silencieuse interdite, champs non déclarés : "
                + ", ".join(undeclared)
            )
        spurious = [
            field
            for field in declared
            if field not in divergences and field not in _FREE_FORM_DEGRADATION_FIELDS
        ]
        if spurious:
            raise ValueError(
                f"dégradation déclarée sur un champ conforme : {spurious}"
            )
        return self

    @model_validator(mode="after")
    def _local_strategies_have_no_provider(self) -> Self:
        if self.strategy in DETERMINISTIC_STRATEGIES and self.provider is not None:
            raise ValueError(
                f"stratégie déterministe {self.strategy.value} attachée au "
                f"fournisseur {self.provider!r}"
            )
        if self.strategy in AI_VIDEO_STRATEGIES and not self.provider:
            raise ValueError(
                f"stratégie {self.strategy.value} sans fournisseur : "
                "aucune exécution possible"
            )
        return self

    @property
    def narrative_degradations(self) -> list[Degradation]:
        return [
            degradation
            for degradation in self.degradations
            if degradation.severity is DegradationSeverity.NARRATIVE
        ]


_FREE_FORM_DEGRADATION_FIELDS = frozenset(
    {
        "identity_lock",
        "motion",
        "subject_motion",
        "environment_motion",
        "audio",
        "provider_availability",
        "retry_strategy",
    }
)
"""Champs dont l'écart ne se déduit pas de l'écho : déclarés librement.

L'écho ne couvre que ce que la demande chiffrait — caméra, durée, résolution,
cadence, stratégie préférée. Le reste se déclare ici, à condition d'être nommé.

`provider_availability` et `retry_strategy` existent parce qu'ils ne sont
*pas* des écarts de stratégie : quand la réalisation n'a exprimé aucune
préférence, choisir une stratégie n'est pas une dégradation. Constater qu'un
fournisseur autorisé est injoignable, ou qu'un plan a épuisé ses tentatives,
en est une — et elle mérite son propre nom plutôt que de se déguiser en écart
de stratégie."""


class ExecutionStepKind(str, Enum):
    GENERATE_IMAGE = "generate_image"
    GENERATE_VIDEO = "generate_video"
    COMPOSE_2_5D = "compose_2_5d"
    RENDER_PROCEDURAL = "render_procedural"
    SYNTHESISE_VOICE = "synthesise_voice"
    OBSERVE = "observe"
    ASSEMBLE = "assemble"
    MASTER_AUDIO = "master_audio"


class ExecutionStep(Element):
    step_id: str = Field(min_length=1)
    kind: ExecutionStepKind
    spec_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    retry_budget: int = Field(default=1, ge=0, le=10)
    timeout_s: float = Field(default=600.0, gt=0.0)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def _no_self_dependency(self) -> Self:
        if self.step_id in self.depends_on:
            raise ValueError(f"étape {self.step_id} dépend d'elle-même")
        return self


@contract("execution_plan", "1.0.0")
class ExecutionPlan(Contract):
    """Ordonnancement des étapes exécutables et de leur coût."""

    episode_id: str = Field(min_length=1)
    steps: list[ExecutionStep] = Field(min_length=1)
    total_estimated_cost_usd: float = Field(ge=0.0)
    budget_cap_usd: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def _plan_is_executable(self) -> Self:
        ids = [step.step_id for step in self.steps]
        if len(set(ids)) != len(ids):
            raise ValueError("plan d'exécution : step_id en double")
        known = set(ids)
        for step in self.steps:
            unknown = [dep for dep in step.depends_on if dep not in known]
            if unknown:
                raise ValueError(f"étape {step.step_id} : dépendances inconnues {unknown}")
        if self._has_cycle():
            raise ValueError("plan d'exécution : dépendances cycliques")

        total = sum(step.estimated_cost_usd for step in self.steps)
        if abs(total - self.total_estimated_cost_usd) > 1e-6:
            raise ValueError(
                f"coût total déclaré {self.total_estimated_cost_usd} "
                f"contre somme des étapes {total}"
            )
        if self.budget_cap_usd is not None and total > self.budget_cap_usd + 1e-9:
            raise ValueError(
                f"plan à {total} USD au-dessus du plafond {self.budget_cap_usd} USD"
            )
        return self

    def _has_cycle(self) -> bool:
        deps = {step.step_id: list(step.depends_on) for step in self.steps}
        state: dict[str, int] = {}

        def visit(node: str) -> bool:
            mark = state.get(node, 0)
            if mark == 1:
                return True
            if mark == 2:
                return False
            state[node] = 1
            for parent in deps[node]:
                if visit(parent):
                    return True
            state[node] = 2
            return False

        return any(visit(node) for node in deps)

    def topological_order(self) -> list[str]:
        deps = {step.step_id: set(step.depends_on) for step in self.steps}
        order: list[str] = []
        remaining = dict(deps)
        while remaining:
            ready = sorted(node for node, need in remaining.items() if not need)
            if not ready:
                raise ValueError("plan d'exécution : dépendances cycliques")
            for node in ready:
                order.append(node)
                del remaining[node]
            for need in remaining.values():
                need.difference_update(ready)
        return order


@contract("render_artifact", "1.1.0")
class RenderArtifact(Contract):
    """Ce qui est réellement sorti d'une exécution, avec son coût mesuré."""

    executable_spec_id: str | None = None
    shot_id: str | None = None
    source_contract_id: str | None = None
    """Contrat que cet artefact rend : une réplique de script, un plan…

    Générique à dessein : un artefact sait de quoi il est le rendu sans que le
    contrat connaisse toutes les couches. Ajouté en 1.1.0 ; absent des
    documents 1.0.0, où il vaut `None`."""
    kind: ArtifactKind
    path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    size_bytes: int = Field(ge=0)

    duration_s: float | None = Field(default=None, gt=0.0)
    resolution: Resolution | None = None
    fps: int | None = Field(default=None, gt=0)

    provider: str | None = None
    model: str | None = None
    actual_cost_usd: float = Field(default=0.0, ge=0.0)
    latency_s: float = Field(default=0.0, ge=0.0)
    attempt: int = Field(default=1, ge=1)
    seed: int | None = None

    @model_validator(mode="after")
    def _shape_matches_kind(self) -> Self:
        if self.kind in {ArtifactKind.VIDEO} and (
            self.duration_s is None or self.fps is None or self.resolution is None
        ):
            raise ValueError("un artefact vidéo déclare durée, fps et résolution")
        if self.kind is ArtifactKind.IMAGE:
            if self.resolution is None:
                raise ValueError("un artefact image déclare sa résolution")
            if self.duration_s is not None or self.fps is not None:
                raise ValueError("un artefact image n'a ni durée ni fps")
        if self.kind is ArtifactKind.AUDIO and self.duration_s is None:
            raise ValueError("un artefact audio déclare sa durée")
        return self
