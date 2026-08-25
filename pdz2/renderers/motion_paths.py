"""Évaluation mathématique des primitives de mouvement.

La phase 0 a figé la représentation : une `Trajectory` porte une primitive,
des points de contrôle, une amplitude, un axe, une fréquence, une courbe
d'accélération. Ce module la **calcule** — c'est ici que la grammaire de
mouvement du §17 cesse d'être une déclaration et devient un déplacement en
pixels.

Aucune formulation linguistique n'intervient : on n'interprète pas « la caméra
avance dramatiquement », on évalue une position à l'instant t.
"""

from __future__ import annotations

import math

from pdz2.contracts.common import Vec3
from pdz2.contracts.motion import Easing, MotionPrimitive, Trajectory

__all__ = ["ease", "sample_trajectory", "SUPPORTED_PRIMITIVES"]

SUPPORTED_PRIMITIVES = frozenset(
    {
        MotionPrimitive.STATIC,
        MotionPrimitive.LINEAR,
        MotionPrimitive.ARC,
        MotionPrimitive.ORBIT,
        MotionPrimitive.OSCILLATE,
        MotionPrimitive.ROTATE,
        MotionPrimitive.SCALE,
        MotionPrimitive.FLOW,
        MotionPrimitive.JITTER,
        MotionPrimitive.SPIRAL,
    }
)
"""Primitives que cet évaluateur sait réellement calculer.

Toutes celles du contrat. Si une primitive s'ajoutait sans être calculée ici,
un test d'architecture le signalerait.
"""


def ease(kind: Easing, t: float) -> float:
    """Courbe d'accélération, de [0,1] vers [0,1]."""
    t = max(0.0, min(1.0, t))
    if kind is Easing.LINEAR:
        return t
    if kind is Easing.EASE_IN:
        return t * t
    if kind is Easing.EASE_OUT:
        return 1.0 - (1.0 - t) ** 2
    if kind is Easing.EASE_IN_OUT:
        return 3 * t * t - 2 * t * t * t
    if kind is Easing.SPRING:
        # Oscillation amortie qui converge vers 1 : dépasse puis revient.
        return 1.0 - math.exp(-6.0 * t) * math.cos(9.0 * t)
    raise ValueError(f"courbe d'accélération inconnue : {kind}")


def _lerp(start: Vec3, end: Vec3, ratio: float) -> Vec3:
    return Vec3(
        x=start.x + (end.x - start.x) * ratio,
        y=start.y + (end.y - start.y) * ratio,
        z=start.z + (end.z - start.z) * ratio,
    )


def sample_trajectory(trajectory: Trajectory, t: float) -> Vec3:
    """Position sur la trajectoire à l'instant normalisé `t` dans [0, 1].

    Le résultat est un déplacement relatif à l'origine, en unités de la
    trajectoire — c'est le renderer qui décide de leur traduction en pixels.
    """
    if not 0.0 <= t <= 1.0:
        raise ValueError(f"instant hors de [0, 1] : {t}")
    primitive = trajectory.primitive
    if primitive not in SUPPORTED_PRIMITIVES:
        raise ValueError(f"primitive non évaluable : {primitive}")

    progress = ease(trajectory.easing, t)
    points = trajectory.control_points
    amplitude = trajectory.amplitude

    if primitive is MotionPrimitive.STATIC:
        return Vec3()

    if primitive is MotionPrimitive.LINEAR:
        return _lerp(points[0], points[1], progress)

    if primitive is MotionPrimitive.ARC:
        # Bézier quadratique sur les trois points de contrôle.
        first = _lerp(points[0], points[1], progress)
        second = _lerp(points[1], points[2], progress)
        return _lerp(first, second, progress)

    if primitive is MotionPrimitive.SPIRAL:
        angle = math.radians(amplitude) * progress
        radius = _distance(points[0], points[2]) * (1.0 - 0.5 * progress)
        return Vec3(
            x=points[0].x + radius * math.cos(angle),
            y=points[0].y + radius * math.sin(angle),
            z=points[0].z + (points[2].z - points[0].z) * progress,
        )

    if primitive in {MotionPrimitive.ORBIT, MotionPrimitive.ROTATE}:
        angle = math.radians(amplitude) * progress
        axis = trajectory.axis
        # Rotation dans le plan perpendiculaire à l'axe dominant.
        if abs(axis.y) >= abs(axis.x) and abs(axis.y) >= abs(axis.z):
            return Vec3(x=math.sin(angle), y=0.0, z=math.cos(angle) - 1.0)
        if abs(axis.x) >= abs(axis.z):
            return Vec3(x=0.0, y=math.sin(angle), z=math.cos(angle) - 1.0)
        return Vec3(x=math.cos(angle) - 1.0, y=math.sin(angle), z=0.0)

    if primitive is MotionPrimitive.OSCILLATE:
        phase = 2.0 * math.pi * trajectory.frequency_hz * t
        return Vec3(x=amplitude * math.sin(phase))

    if primitive is MotionPrimitive.JITTER:
        # Bruit borné, déterministe : deux rendus donnent le même tremblement.
        phase = 2.0 * math.pi * trajectory.frequency_hz * t
        return Vec3(
            x=amplitude * math.sin(phase * 1.0),
            y=amplitude * math.sin(phase * 1.618 + 1.3),
        )

    if primitive is MotionPrimitive.SCALE:
        return Vec3(z=amplitude * progress)

    # FLOW : dérive continue, sans accélération.
    direction = points[1] if len(points) > 1 else Vec3(x=1.0)
    return Vec3(
        x=direction.x * amplitude * t,
        y=direction.y * amplitude * t,
        z=direction.z * amplitude * t,
    )


def _distance(first: Vec3, second: Vec3) -> float:
    return math.dist((first.x, first.y, first.z), (second.x, second.y, second.z))
