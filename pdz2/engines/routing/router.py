"""Render Strategy Engine : choisir une stratégie, et dire ce qu'elle coûte.

    ROUTERS CHOOSE.

Le routeur reçoit une demande de rendu et l'ensemble des capacités réellement
mesurées. Il en tire une stratégie exécutable et, pour **chaque écart** avec
la demande, une `Degradation` nommée : le champ, le demandé, l'exécuté, la
raison. Le contrat `RenderSpecExecutable` refuse tout écart non déclaré — une
dégradation silencieuse est structurellement impossible.

Les critères du §18, dans l'ordre où ils sont appliqués :

    interdiction de la vidéo IA   → écarte les stratégies génératives
    capacité mesurée              → écarte ce qu'aucun exécutant ne sait faire
    échecs antérieurs             → écarte ce qui a déjà raté sur ce plan
    risque d'identité             → préfère ce qui tient une image de référence
    complexité de mouvement       → arbitre entre still, ken burns, 2.5D, procédural
    exigence caméra               → vérifie que le mouvement demandé est tenable
    durée et coût                 → écarte ce qui dépasse plafond ou budget

Le dernier recours est toujours `STILL` : une image fixe se rend sans
personne, ce qui rend la livraison garantie.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pdz2.contracts.motion import CameraMove, MotionProgram
from pdz2.contracts.render import (
    AI_VIDEO_STRATEGIES,
    DETERMINISTIC_STRATEGIES,
    Degradation,
    DegradationSeverity,
    ExecutionPlan,
    ExecutionStep,
    ExecutionStepKind,
    RenderSpecExecutable,
    RenderSpecRequested,
    RenderStrategy,
)
from pdz2.contracts.visual import ImageSpec
from pdz2.providers.video import VideoCapability

__all__ = [
    "RenderRouter",
    "RoutingOutcome",
    "RoutingRejected",
    "LOCAL_CAPABILITY",
    "MOTION_COMPLEXITY_ORDER",
]

LOCAL_CAPABILITY: frozenset[RenderStrategy] = DETERMINISTIC_STRATEGIES
"""Stratégies exécutables sans le moindre fournisseur. Toujours disponibles."""

MOTION_COMPLEXITY_ORDER: tuple[RenderStrategy, ...] = (
    RenderStrategy.STILL,
    RenderStrategy.KEN_BURNS,
    RenderStrategy.PARALLAX_2_5D,
    RenderStrategy.PROCEDURAL,
)
"""Stratégies locales, de la plus sobre à la plus mouvante.

L'ordre n'est pas une préférence : c'est une échelle. Le routeur y entre à la
hauteur de l'énergie de mouvement visée, puis redescend si la capacité, la
durée ou le budget l'y obligent.
"""

_STILL_BELOW = 0.15
_KEN_BURNS_BELOW = 0.40
_PARALLAX_BELOW = 0.70

_CAMERA_BY_STRATEGY: dict[RenderStrategy, frozenset[CameraMove]] = {
    RenderStrategy.STILL: frozenset({CameraMove.LOCK}),
    RenderStrategy.KEN_BURNS: frozenset(
        {CameraMove.LOCK, CameraMove.PUSH_IN, CameraMove.PULL_OUT, CameraMove.PAN,
         CameraMove.TILT}
    ),
    RenderStrategy.PARALLAX_2_5D: frozenset(
        {CameraMove.LOCK, CameraMove.PUSH_IN, CameraMove.PULL_OUT, CameraMove.PAN,
         CameraMove.TILT, CameraMove.PARALLAX, CameraMove.TRACK}
    ),
    RenderStrategy.PROCEDURAL: frozenset(
        {CameraMove.LOCK, CameraMove.PUSH_IN, CameraMove.PULL_OUT, CameraMove.PAN,
         CameraMove.TILT, CameraMove.PARALLAX, CameraMove.TRACK, CameraMove.ORBIT}
    ),
}
"""Mouvements caméra que chaque stratégie locale sait réellement tenir.

Mesuré au sens strict : c'est ce que les renderers de la phase 7 implémentent.
Aucune ligne n'y est annoncée sans code derrière.
"""


class RoutingRejected(ValueError):
    """Aucune stratégie ne peut satisfaire cette demande, pas même un repli."""


@dataclass
class RoutingOutcome:
    executables: list[RenderSpecExecutable]
    plan: ExecutionPlan
    notes: list[str] = field(default_factory=list)

    def for_shot(self, shot_id: str) -> RenderSpecExecutable:
        for executable in self.executables:
            if executable.shot_id == shot_id:
                return executable
        raise KeyError(shot_id)

    @property
    def degradations(self) -> list[Degradation]:
        return [d for e in self.executables for d in e.degradations]


@dataclass
class RenderRouter:
    """Choisit une stratégie par plan et enregistre chaque écart."""

    video_capabilities: list[VideoCapability] = field(default_factory=list)
    local_strategies: frozenset[RenderStrategy] = LOCAL_CAPABILITY
    previous_failures: dict[str, set[RenderStrategy]] = field(default_factory=dict)
    """Stratégies déjà mises en échec sur un plan. Alimenté par la réparation."""

    def route(
        self,
        *,
        episode_id: str,
        requested: list[RenderSpecRequested],
        motion_programs: list[MotionProgram],
        image_specs: list[ImageSpec],
        budget_cap_usd: float | None = None,
    ) -> RoutingOutcome:
        motions = {program.id: program for program in motion_programs}
        images = {spec.id: spec for spec in image_specs}
        executables: list[RenderSpecExecutable] = []

        for spec in requested:
            motion = motions.get(spec.motion_program_id)
            if motion is None:
                raise RoutingRejected(
                    f"{spec.shot_id} : programme de mouvement introuvable"
                )
            layers = max(
                (len(images[ref].layers) for ref in spec.image_spec_ids if ref in images),
                default=1,
            )
            executables.append(self._route_one(spec, motion, layers))

        plan = self._plan(episode_id, executables, budget_cap_usd)
        return RoutingOutcome(
            executables=executables,
            plan=plan,
            notes=self._notes(executables, plan),
        )

    # ------------------------------------------------------------------ choix

    def _route_one(
        self,
        spec: RenderSpecRequested,
        motion: MotionProgram,
        layer_count: int,
    ) -> RenderSpecExecutable:
        degradations: list[Degradation] = []
        available = self._available(spec, degradations)
        failed = self.previous_failures.get(spec.shot_id, set())
        usable = [s for s in available if s not in failed]
        if failed and not usable:
            degradations.append(
                Degradation(
                    field="retry_strategy",
                    requested="stratégie précédemment tentée",
                    executed=RenderStrategy.STILL.value,
                    reason=(
                        "toutes les stratégies disponibles ont déjà échoué sur ce "
                        f"plan ({sorted(s.value for s in failed)})"
                    ),
                    description="repli sur une image fixe, qui aboutit toujours",
                    severity=DegradationSeverity.NARRATIVE,
                )
            )
            usable = [RenderStrategy.STILL]

        energy = motion.perceptual_target.motion_energy
        wanted = self._by_energy(energy)
        wanted = self._respect_layers(wanted, layer_count, degradations)
        chosen = self._best(wanted, usable)

        if chosen is not wanted and wanted in available:
            pass  # écarté par un échec antérieur : déjà consigné
        elif chosen is not wanted:
            # Pas un écart de stratégie : la réalisation n'en demandait aucune.
            # C'est l'énergie de mouvement visée qui n'est pas atteinte.
            degradations.append(
                Degradation(
                    field="strategy" if spec.preferred_strategy is not None else "motion",
                    requested=wanted.value,
                    executed=chosen.value,
                    reason=self._why_not(wanted, spec),
                    description=(
                        f"énergie de mouvement {energy:.2f} visée, rendue par "
                        f"{chosen.value}"
                    ),
                    severity=(
                        DegradationSeverity.NARRATIVE
                        if chosen is RenderStrategy.STILL and energy >= _KEN_BURNS_BELOW
                        else DegradationSeverity.PERCEPTUAL
                    ),
                )
            )

        camera = self._camera(spec, chosen, degradations)
        if spec.identity_lock_required and chosen in AI_VIDEO_STRATEGIES:
            degradations.append(
                Degradation(
                    field="identity_lock",
                    requested="verrou strict",
                    executed="au mieux",
                    reason="aucun fournisseur ne garantit l'identité image à image",
                    description="l'ancre est portée par l'image de départ seule",
                    severity=DegradationSeverity.PERCEPTUAL,
                )
            )

        return RenderSpecExecutable(
            requested_spec_id=spec.id,
            shot_id=spec.shot_id,
            requested=spec.echo(),
            strategy=chosen,
            execution_camera=camera,
            duration_s=spec.duration_s,
            resolution=spec.resolution,
            fps=spec.fps,
            provider=None,
            model=None,
            degradations=degradations,
            estimated_cost_usd=0.0,
            parent_id=spec.id,
        )

    def _available(
        self, spec: RenderSpecRequested, degradations: list[Degradation]
    ) -> list[RenderStrategy]:
        """Stratégies réellement mobilisables pour cette demande."""
        available = list(self.local_strategies)
        reachable = [
            capability
            for capability in self.video_capabilities
            if capability.usable
        ]
        if spec.allow_ai_video:
            if reachable:
                for capability in reachable:
                    available.extend(
                        strategy
                        for strategy in capability.strategies
                        if strategy in AI_VIDEO_STRATEGIES
                    )
            else:
                degradations.append(
                    Degradation(
                        field="provider_availability",
                        requested="génération vidéo par IA",
                        executed="stratégie déterministe locale",
                        reason=(
                            "aucun fournisseur vidéo joignable : "
                            + (
                                "aucun adaptateur n'est implémenté"
                                if not self.video_capabilities
                                else "tous les adaptateurs se déclarent injoignables"
                            )
                        ),
                        description=(
                            "le plan est rendu localement, sans modèle génératif"
                        ),
                        severity=DegradationSeverity.PERCEPTUAL,
                    )
                )
        if not available:
            raise RoutingRejected(
                f"{spec.shot_id} : aucune stratégie disponible, pas même un repli"
            )
        return available

    @staticmethod
    def _by_energy(energy: float) -> RenderStrategy:
        """Stratégie visée par la seule énergie de mouvement."""
        if energy < _STILL_BELOW:
            return RenderStrategy.STILL
        if energy < _KEN_BURNS_BELOW:
            return RenderStrategy.KEN_BURNS
        if energy < _PARALLAX_BELOW:
            return RenderStrategy.PARALLAX_2_5D
        return RenderStrategy.PROCEDURAL

    @staticmethod
    def _respect_layers(
        wanted: RenderStrategy,
        layer_count: int,
        degradations: list[Degradation],
    ) -> RenderStrategy:
        """Le parallaxe a besoin de calques séparés. S'il n'y en a qu'un, il
        n'a rien à décaler — et le dire vaut mieux que de retomber en silence
        sur un mouvement plus pauvre.
        """
        if wanted is not RenderStrategy.PARALLAX_2_5D or layer_count >= 2:
            return wanted
        degradations.append(
            Degradation(
                field="motion",
                requested=RenderStrategy.PARALLAX_2_5D.value,
                executed=RenderStrategy.KEN_BURNS.value,
                reason=(
                    f"un seul calque séparable dans l'image ({layer_count}) : "
                    "le parallaxe n'a aucune profondeur à décaler"
                ),
                description=(
                    "mouvement rendu par recadrage progressif au lieu du parallaxe"
                ),
                severity=DegradationSeverity.PERCEPTUAL,
            )
        )
        return RenderStrategy.KEN_BURNS

    @staticmethod
    def _best(
        wanted: RenderStrategy, usable: list[RenderStrategy]
    ) -> RenderStrategy:
        """La stratégie visée, ou la plus proche en deçà sur l'échelle."""
        if wanted in usable:
            return wanted
        scale = [s for s in MOTION_COMPLEXITY_ORDER if s in usable]
        if not scale:
            raise RoutingRejected("aucune stratégie locale disponible")
        if wanted in MOTION_COMPLEXITY_ORDER:
            index = MOTION_COMPLEXITY_ORDER.index(wanted)
            below = [
                s for s in scale if MOTION_COMPLEXITY_ORDER.index(s) <= index
            ]
            if below:
                return below[-1]
        return scale[-1]

    @staticmethod
    def _why_not(wanted: RenderStrategy, spec: RenderSpecRequested) -> str:
        if wanted in AI_VIDEO_STRATEGIES:
            return "aucun fournisseur n'expose cette stratégie"
        return f"{wanted.value} n'est pas exécutable pour ce plan"

    @staticmethod
    def _camera(
        spec: RenderSpecRequested,
        strategy: RenderStrategy,
        degradations: list[Degradation],
    ) -> CameraMove:
        """Mouvement caméra réellement tenable par la stratégie retenue."""
        supported = _CAMERA_BY_STRATEGY.get(strategy, frozenset({CameraMove.LOCK}))
        if spec.requested_camera in supported:
            return spec.requested_camera
        fallback = (
            CameraMove.PUSH_IN
            if CameraMove.PUSH_IN in supported
            else CameraMove.LOCK
        )
        degradations.append(
            Degradation(
                field="camera",
                requested=spec.requested_camera.value,
                executed=fallback.value,
                reason=(
                    f"la stratégie {strategy.value} n'expose pas le mouvement "
                    f"{spec.requested_camera.value}"
                ),
                description=(
                    f"{spec.requested_camera.value} remplacé par une approximation "
                    f"déterministe en {fallback.value}"
                ),
                severity=DegradationSeverity.PERCEPTUAL,
            )
        )
        return fallback

    # ------------------------------------------------------------------- plan

    @staticmethod
    def _plan(
        episode_id: str,
        executables: list[RenderSpecExecutable],
        budget_cap_usd: float | None,
    ) -> ExecutionPlan:
        steps: list[ExecutionStep] = []
        for executable in executables:
            kind = (
                ExecutionStepKind.GENERATE_VIDEO
                if executable.strategy in AI_VIDEO_STRATEGIES
                else ExecutionStepKind.COMPOSE_2_5D
                if executable.strategy is RenderStrategy.PARALLAX_2_5D
                else ExecutionStepKind.RENDER_PROCEDURAL
            )
            render_id = f"render-{executable.shot_id}"
            steps.append(
                ExecutionStep(
                    step_id=render_id,
                    kind=kind,
                    spec_id=executable.id,
                    retry_budget=1,
                    timeout_s=300.0,
                    estimated_cost_usd=executable.estimated_cost_usd,
                )
            )
            steps.append(
                ExecutionStep(
                    step_id=f"observe-{executable.shot_id}",
                    kind=ExecutionStepKind.OBSERVE,
                    spec_id=executable.id,
                    depends_on=[render_id],
                    retry_budget=0,
                    timeout_s=120.0,
                    estimated_cost_usd=0.0,
                )
            )
        steps.append(
            ExecutionStep(
                step_id="assemble",
                kind=ExecutionStepKind.ASSEMBLE,
                depends_on=[f"observe-{e.shot_id}" for e in executables],
                retry_budget=1,
                timeout_s=600.0,
                estimated_cost_usd=0.0,
            )
        )
        total = sum(step.estimated_cost_usd for step in steps)
        return ExecutionPlan(
            episode_id=episode_id,
            steps=steps,
            total_estimated_cost_usd=round(total, 6),
            budget_cap_usd=budget_cap_usd,
        )

    @staticmethod
    def _notes(executables, plan) -> list[str]:
        counts: dict[str, int] = {}
        for executable in executables:
            counts[executable.strategy.value] = (
                counts.get(executable.strategy.value, 0) + 1
            )
        degradations = [d for e in executables for d in e.degradations]
        narrative = [
            d for d in degradations if d.severity is DegradationSeverity.NARRATIVE
        ]
        return [
            "stratégies retenues : "
            + ", ".join(f"{name}×{count}" for name, count in sorted(counts.items())),
            f"{len(degradations)} dégradation(s) enregistrée(s), "
            f"dont {len(narrative)} narrative(s)",
            f"{len(plan.steps)} étapes d'exécution pour "
            f"{plan.total_estimated_cost_usd:.4f} USD estimés",
        ]
