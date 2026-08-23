"""MotionProgram : la source de vérité du mouvement.

Le `ShotSpec` porte déjà des descripteurs de mouvement et un identifiant de
programme caméra. Le `MotionProgram` les rassemble en **un seul contrat qui
fait autorité**, avec ce qu'aucun descripteur ne dit : ce qui doit être
préservé, ce qui peut changer, ce qui est interdit, et la cible perceptive à
atteindre.

Le prompt vidéo, plus tard, ne sera qu'une compilation secondaire de ce
contrat. C'est ici que le mouvement est décidé, pas dans une phrase envoyée à
un moteur.

Cette étape est tirée en avant depuis la phase 6 : le graphe d'étapes place
`MOTION` avant `RENDER_SPEC`, et `RenderSpecRequested.motion_program_id` est
obligatoire. Sans elle, aucune demande de rendu ne peut exister.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pdz2.contracts.direction import DirectorState
from pdz2.contracts.motion import (
    CameraProgram,
    MotionPrimitive,
    MotionProgram,
    PerceptualTarget,
)
from pdz2.contracts.shots import ShotGraph
from pdz2.contracts.temporal import TemporalPlan
from pdz2.contracts.visual import VisualBible

__all__ = ["MotionCompiler", "MotionOutcome", "MotionRejected"]


class MotionRejected(ValueError):
    """Le plan ne permet pas de composer un programme de mouvement."""


@dataclass
class MotionOutcome:
    programs: list[MotionProgram]
    notes: list[str] = field(default_factory=list)

    def for_shot(self, shot_id: str) -> MotionProgram:
        for program in self.programs:
            if program.shot_id == shot_id:
                return program
        raise KeyError(shot_id)


@dataclass
class MotionCompiler:
    def compile(
        self,
        *,
        shot_graph: ShotGraph,
        temporal_plan: TemporalPlan,
        camera_programs: list[CameraProgram],
        director_state: DirectorState,
        visual_bible: VisualBible,
    ) -> MotionOutcome:
        cameras = {program.id: program for program in camera_programs}
        anchors = {anchor.id: anchor for anchor in director_state.continuity_anchors}
        programs: list[MotionProgram] = []

        for shot in shot_graph.shots:
            camera = cameras.get(shot.camera_program_id)
            if camera is None:
                raise MotionRejected(
                    f"{shot.shot_id} : programme caméra {shot.camera_program_id} "
                    "introuvable"
                )
            targets = temporal_plan.targets_for(shot.shot_id)
            preserve = self._must_preserve(shot, anchors)
            forbidden = self._forbidden(visual_bible, preserve)
            may_change = self._may_change(preserve, forbidden)

            camera_descriptor = self._camera_descriptor(camera)
            moving = any(
                descriptor.primitive is not MotionPrimitive.STATIC
                for descriptor in (
                    shot.subject_motion,
                    camera_descriptor,
                    shot.environment_motion,
                )
            )
            programs.append(
                MotionProgram(
                    shot_id=shot.shot_id,
                    camera_program_id=camera.id,
                    subject_motion=shot.subject_motion.model_copy(deep=True),
                    camera_motion=camera_descriptor,
                    environment_motion=shot.environment_motion.model_copy(deep=True),
                    trajectory=self._dominant_trajectory(shot, camera),
                    velocity=round(camera.velocity, 4),
                    acceleration=round(camera.acceleration, 4),
                    intensity=round(targets["motion"], 4) if moving else 0.0,
                    must_preserve=preserve,
                    may_change=may_change,
                    forbidden=forbidden,
                    perceptual_target=PerceptualTarget(
                        motion_energy=round(targets["motion"], 4),
                        visual_novelty=round(targets["visual_novelty"], 4),
                        # Une parole dense exige une image lisible : la cible de
                        # lisibilité est le complément de la densité.
                        readability=round(1.0 - targets["information"], 4),
                    ),
                    parent_id=shot.id,
                )
            )

        return MotionOutcome(
            programs=programs,
            notes=[
                f"{len(programs)} programmes de mouvement",
                f"{sum(1 for p in programs if p.intensity > 0)} plans en mouvement",
            ],
        )

    # ------------------------------------------------------------------ règles

    @staticmethod
    def _camera_descriptor(camera: CameraProgram):
        from pdz2.contracts.motion import MotionDescriptor

        if camera.locked:
            return MotionDescriptor()
        return MotionDescriptor(
            primitive=camera.trajectory.primitive,
            direction=camera.target,
            magnitude=round(max(1e-4, camera.velocity), 4),
            trajectory=camera.trajectory.model_copy(deep=True),
            description=f"caméra {camera.move.value}",
        )

    @staticmethod
    def _dominant_trajectory(shot, camera: CameraProgram):
        """La trajectoire que l'observateur devra retrouver dans le rendu.

        Celle de la caméra si elle bouge : c'est elle que l'œil suit. Sinon
        celle du sujet.
        """
        if not camera.locked:
            return camera.trajectory.model_copy(deep=True)
        return shot.subject_motion.trajectory.model_copy(deep=True)

    @staticmethod
    def _must_preserve(shot, anchors) -> list[str]:
        """Ce qui ne doit pas bouger : l'identité, trait par trait."""
        preserve: list[str] = []
        for anchor_id in shot.continuity_dependencies:
            anchor = anchors.get(anchor_id)
            if anchor is None:
                raise MotionRejected(
                    f"{shot.shot_id} : ancre inconnue {anchor_id}"
                )
            for attribute in anchor.fixed_attributes():
                entry = f"{anchor.name}.{attribute.name} = {attribute.value}"
                if entry not in preserve:
                    preserve.append(entry)
        return preserve

    @staticmethod
    def _forbidden(visual_bible: VisualBible, preserve: list[str]) -> list[str]:
        forbidden = [item for item in visual_bible.forbidden if item not in preserve]
        return forbidden

    @staticmethod
    def _may_change(preserve: list[str], forbidden: list[str]) -> list[str]:
        """Ce qui a le droit de varier, sans recouper les deux autres listes."""
        candidates = [
            "intensité de la lumière",
            "angle de vue",
            "profondeur de champ",
            "arrière-plan",
        ]
        blocked = set(preserve) | set(forbidden)
        return [item for item in candidates if item not in blocked]
