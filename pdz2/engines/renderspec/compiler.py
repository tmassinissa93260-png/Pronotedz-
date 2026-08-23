"""Compilation des demandes de rendu.

`RenderSpecRequested` est la frontière : ce que la réalisation **demande**,
exprimé en termes physiques et mesurables, sans nommer aucun fournisseur ni
aucune stratégie imposée. Le routeur choisira ; le validateur aura d'abord
refusé ce qui n'a pas de sens.

Rien de nouveau n'est décidé ici : durée du créneau mesuré, résolution du
format, caméra du programme caméra, verrou d'identité dès qu'une ancre est en
jeu, plafond de coût des contraintes du plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pdz2.contracts.motion import CameraProgram, MotionProgram
from pdz2.contracts.render import RenderSpecRequested
from pdz2.contracts.research import TopicRequest
from pdz2.contracts.shots import ShotGraph
from pdz2.contracts.visual import ImageSpec

__all__ = ["RenderSpecCompiler", "RenderSpecOutcome", "RenderSpecRejected", "DEFAULT_FPS"]

DEFAULT_FPS = 30
"""Cadence par défaut. 30 i/s tient sur toutes les plateformes visées."""


class RenderSpecRejected(ValueError):
    """Les contrats amont ne permettent pas de formuler une demande de rendu."""


@dataclass
class RenderSpecOutcome:
    specs: list[RenderSpecRequested]
    notes: list[str] = field(default_factory=list)

    def for_shot(self, shot_id: str) -> RenderSpecRequested:
        for spec in self.specs:
            if spec.shot_id == shot_id:
                return spec
        raise KeyError(shot_id)


@dataclass
class RenderSpecCompiler:
    fps: int = DEFAULT_FPS

    def compile(
        self,
        *,
        shot_graph: ShotGraph,
        motion_programs: list[MotionProgram],
        camera_programs: list[CameraProgram],
        image_specs: list[ImageSpec],
        request: TopicRequest,
    ) -> RenderSpecOutcome:
        motions = {program.shot_id: program for program in motion_programs}
        cameras = {program.id: program for program in camera_programs}
        images: dict[str, list[ImageSpec]] = {}
        for spec in image_specs:
            images.setdefault(spec.shot_id, []).append(spec)

        specs: list[RenderSpecRequested] = []
        for shot in shot_graph.shots:
            motion = motions.get(shot.shot_id)
            if motion is None:
                raise RenderSpecRejected(
                    f"{shot.shot_id} : aucun programme de mouvement"
                )
            camera = cameras.get(shot.camera_program_id)
            if camera is None:
                raise RenderSpecRejected(
                    f"{shot.shot_id} : programme caméra introuvable"
                )
            shot_images = images.get(shot.shot_id, [])
            if not shot_images:
                raise RenderSpecRejected(
                    f"{shot.shot_id} : aucune spécification d'image — un plan sans "
                    "image de départ n'est pas rendable"
                )
            resolution = shot_images[0].resolution
            specs.append(
                RenderSpecRequested(
                    shot_id=shot.shot_id,
                    motion_program_id=motion.id,
                    camera_program_id=camera.id,
                    image_spec_ids=[spec.id for spec in shot_images],
                    duration_s=round(shot.duration_s, 6),
                    resolution=resolution,
                    fps=self.fps,
                    requested_camera=camera.move,
                    preferred_strategy=None,
                    identity_lock_required=shot.render_constraints.requires_identity_lock,
                    allow_ai_video=shot.render_constraints.allow_ai_video,
                    max_cost_usd=shot.render_constraints.max_cost_usd,
                    parent_id=shot.id,
                )
            )
        return RenderSpecOutcome(
            specs=specs,
            notes=[
                f"{len(specs)} demandes de rendu à {self.fps} i/s",
                f"{sum(1 for s in specs if s.identity_lock_required)} exigent un "
                "verrou d'identité",
                f"{sum(1 for s in specs if not s.allow_ai_video)} interdisent la "
                "génération vidéo par IA",
            ],
        )
