"""Programmes de mouvement et de caméra.

Le MotionProgram est la source de vérité du mouvement. Le prompt vidéo n'en
est qu'une compilation secondaire, produite par un adaptateur.

Grammaire de mouvement (§17) : chaque primitive est nommée et paramétrée
numériquement. Aucune intention de mouvement ne repose sur une formulation
linguistique du type « la caméra avance dramatiquement ». L'évaluateur
mathématique des trajectoires arrive avec les moteurs d'exécution
(phases 6-7) ; la phase 0 en fige la représentation.
"""

from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import Field, model_validator

from pdz2.contracts.base import Contract, Element, contract
from pdz2.contracts.common import Vec3

__all__ = [
    "CameraMove",
    "MotionPrimitive",
    "Easing",
    "Trajectory",
    "DepthOfField",
    "CameraProgram",
    "MotionDescriptor",
    "PerceptualTarget",
    "MotionProgram",
]


class CameraMove(str, Enum):
    LOCK = "lock"
    PAN = "pan"
    TILT = "tilt"
    DOLLY = "dolly"
    PUSH_IN = "push_in"
    PULL_OUT = "pull_out"
    TRACK = "track"
    ORBIT = "orbit"
    PARALLAX = "parallax"
    HANDHELD = "handheld"


STATIC_CAMERA_MOVES = frozenset({CameraMove.LOCK})


class MotionPrimitive(str, Enum):
    """Primitives de la grammaire de mouvement, chacune paramétrable."""

    STATIC = "static"
    LINEAR = "linear"
    ARC = "arc"
    ORBIT = "orbit"
    OSCILLATE = "oscillate"
    SPIRAL = "spiral"
    ROTATE = "rotate"
    SCALE = "scale"
    FLOW = "flow"
    """Champ de vitesse continu : fumée, courant, fluide."""

    JITTER = "jitter"
    """Bruit borné : caméra à l'épaule."""


class Easing(str, Enum):
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    SPRING = "spring"


class Trajectory(Element):
    """Trajectoire paramétrée. Représentation numérique, pas textuelle."""

    primitive: MotionPrimitive = MotionPrimitive.STATIC
    control_points: list[Vec3] = Field(default_factory=list)
    easing: Easing = Easing.LINEAR
    amplitude: float = Field(default=0.0, ge=0.0)
    """Unité dépendante de la primitive : mètres, degrés, ou fraction de cadre."""

    frequency_hz: float = Field(default=0.0, ge=0.0)
    axis: Vec3 = Field(default_factory=Vec3)
    loop: bool = False

    @model_validator(mode="after")
    def _primitive_is_fully_parameterised(self) -> Self:
        if self.primitive is MotionPrimitive.STATIC:
            if self.amplitude != 0.0 or self.control_points:
                raise ValueError("primitive 'static' avec un mouvement paramétré")
            return self
        if self.primitive is MotionPrimitive.LINEAR and len(self.control_points) < 2:
            raise ValueError("primitive 'linear' : deux points de contrôle attendus")
        if self.primitive in {MotionPrimitive.ARC, MotionPrimitive.SPIRAL} and (
            len(self.control_points) < 3
        ):
            raise ValueError(
                f"primitive '{self.primitive.value}' : trois points de contrôle attendus"
            )
        if self.primitive in {MotionPrimitive.OSCILLATE, MotionPrimitive.JITTER} and (
            self.frequency_hz <= 0.0
        ):
            raise ValueError(
                f"primitive '{self.primitive.value}' : fréquence strictement positive attendue"
            )
        if self.primitive in {
            MotionPrimitive.ORBIT,
            MotionPrimitive.ROTATE,
            MotionPrimitive.SPIRAL,
        } and self.axis == Vec3():
            raise ValueError(
                f"primitive '{self.primitive.value}' : axe de rotation non renseigné"
            )
        if self.primitive is not MotionPrimitive.STATIC and self.amplitude <= 0.0:
            raise ValueError(
                f"primitive '{self.primitive.value}' : amplitude strictement positive attendue"
            )
        return self


class DepthOfField(Element):
    focus_distance_m: float = Field(gt=0.0)
    f_stop: float = Field(gt=0.0)
    focus_pull: bool = False
    focus_target_m: float | None = Field(default=None, gt=0.0)

    @model_validator(mode="after")
    def _pull_has_a_target(self) -> Self:
        if self.focus_pull and self.focus_target_m is None:
            raise ValueError("un point de bascule exige une distance cible")
        if not self.focus_pull and self.focus_target_m is not None:
            raise ValueError("distance cible renseignée sans bascule de mise au point")
        return self


@contract("camera_program", "1.0.0")
class CameraProgram(Contract):
    """Programme caméra indépendant du moteur de rendu."""

    move: CameraMove = CameraMove.LOCK
    locked: bool = False
    position: Vec3 = Field(default_factory=Vec3)
    rotation: Vec3 = Field(default_factory=Vec3)
    target: Vec3 = Field(default_factory=Vec3)
    focal_length_mm: float = Field(default=35.0, gt=0.0)
    trajectory: Trajectory = Field(default_factory=Trajectory)
    velocity: float = Field(default=0.0, ge=0.0)
    acceleration: float = Field(default=0.0)
    depth_of_field: DepthOfField | None = None

    @model_validator(mode="after")
    def _no_contradiction(self) -> Self:
        # L'exemple de contradiction du cahier des charges : caméra verrouillée
        # et mouvement demandé en même temps.
        if self.locked and self.move not in STATIC_CAMERA_MOVES:
            raise ValueError(
                f"contradiction : locked=true et move={self.move.value}"
            )
        if self.locked and self.velocity != 0.0:
            raise ValueError("contradiction : locked=true et velocity != 0")
        if self.locked and self.trajectory.primitive is not MotionPrimitive.STATIC:
            raise ValueError(
                f"contradiction : locked=true et trajectoire "
                f"{self.trajectory.primitive.value}"
            )
        if self.move not in STATIC_CAMERA_MOVES and self.velocity <= 0.0:
            raise ValueError(
                f"mouvement {self.move.value} déclaré sans vitesse : "
                "un mouvement caméra se chiffre"
            )
        if self.move is CameraMove.ORBIT and self.trajectory.primitive not in {
            MotionPrimitive.ORBIT,
            MotionPrimitive.SPIRAL,
        }:
            raise ValueError("un orbit exige une trajectoire 'orbit' ou 'spiral'")
        return self


class MotionDescriptor(Element):
    """Mouvement d'un sujet ou d'un environnement."""

    primitive: MotionPrimitive = MotionPrimitive.STATIC
    direction: Vec3 = Field(default_factory=Vec3)
    magnitude: float = Field(default=0.0, ge=0.0)
    trajectory: Trajectory = Field(default_factory=Trajectory)
    description: str = ""
    """Glose humaine, jamais la source de vérité."""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.primitive is MotionPrimitive.STATIC and self.magnitude != 0.0:
            raise ValueError("mouvement 'static' avec une magnitude non nulle")
        if self.primitive is not MotionPrimitive.STATIC and self.magnitude <= 0.0:
            raise ValueError(f"mouvement '{self.primitive.value}' sans magnitude")
        if self.trajectory.primitive is not self.primitive:
            raise ValueError(
                f"primitive {self.primitive.value} et trajectoire "
                f"{self.trajectory.primitive.value} divergentes"
            )
        return self


class PerceptualTarget(Element):
    """Ce que le mouvement doit produire chez le spectateur, mesurable."""

    motion_energy: float = Field(ge=0.0, le=1.0)
    visual_novelty: float = Field(ge=0.0, le=1.0)
    readability: float = Field(ge=0.0, le=1.0)
    tolerance: float = Field(default=0.2, gt=0.0, le=1.0)


@contract("motion_program", "1.0.0")
class MotionProgram(Contract):
    """Source de vérité du mouvement d'un plan."""

    shot_id: str = Field(min_length=1)
    camera_program_id: str = Field(min_length=1)

    subject_motion: MotionDescriptor = Field(default_factory=MotionDescriptor)
    camera_motion: MotionDescriptor = Field(default_factory=MotionDescriptor)
    environment_motion: MotionDescriptor = Field(default_factory=MotionDescriptor)

    trajectory: Trajectory = Field(default_factory=Trajectory)
    """Trajectoire dominante du plan, celle que l'observateur doit retrouver."""

    velocity: float = Field(default=0.0, ge=0.0)
    acceleration: float = Field(default=0.0)
    intensity: float = Field(default=0.0, ge=0.0, le=1.0)

    must_preserve: list[str] = Field(default_factory=list)
    may_change: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    perceptual_target: PerceptualTarget

    @model_validator(mode="after")
    def _sets_are_disjoint(self) -> Self:
        preserve = set(self.must_preserve)
        change = set(self.may_change)
        forbid = set(self.forbidden)
        clashes = {
            "must_preserve/may_change": preserve & change,
            "must_preserve/forbidden": preserve & forbid,
            "may_change/forbidden": change & forbid,
        }
        for label, overlap in clashes.items():
            if overlap:
                raise ValueError(f"contradiction {label} : {sorted(overlap)}")
        return self

    @model_validator(mode="after")
    def _movement_is_quantified(self) -> Self:
        moving = any(
            descriptor.primitive is not MotionPrimitive.STATIC
            for descriptor in (
                self.subject_motion,
                self.camera_motion,
                self.environment_motion,
            )
        )
        if moving and self.intensity <= 0.0:
            raise ValueError("plan en mouvement déclaré avec une intensité nulle")
        if not moving and self.intensity > 0.0:
            raise ValueError("plan intégralement statique avec une intensité non nulle")
        if not moving and self.velocity > 0.0:
            raise ValueError("plan intégralement statique avec une vitesse non nulle")
        return self
