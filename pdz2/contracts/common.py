"""Objets de valeur partagés par plusieurs familles de contrats."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from pdz2.contracts.base import Element
from pdz2.contracts.enums import (
    AspectRatio,
    CameraAngle,
    Framing,
    ScreenPosition,
    Severity,
    TransitionKind,
)

__all__ = [
    "Vec3",
    "Resolution",
    "Composition",
    "Transition",
    "TextOverlay",
    "CurvePoint",
    "Curve",
    "CostEstimate",
    "QaCheck",
]


class Vec3(Element):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class Resolution(Element):
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    @property
    def megapixels(self) -> float:
        return self.width * self.height / 1_000_000

    def matches(self, ratio: AspectRatio, tolerance: float = 0.02) -> bool:
        wanted_w, wanted_h = (int(part) for part in ratio.value.split(":"))
        wanted = wanted_w / wanted_h
        return abs(self.width / self.height - wanted) <= tolerance


class Composition(Element):
    """Cadrage d'un plan. Intention de mise en image, pas d'exécution."""

    framing: Framing
    angle: CameraAngle = CameraAngle.EYE
    subject_position: ScreenPosition = ScreenPosition.CENTER
    headroom: float = Field(default=0.1, ge=0.0, le=0.5)
    negative_space: float = Field(default=0.3, ge=0.0, le=1.0)
    safe_area_pct: float = Field(default=0.9, gt=0.0, le=1.0)


class Transition(Element):
    kind: TransitionKind = TransitionKind.CUT
    duration_s: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def _cut_is_instant(self) -> Self:
        if self.kind is TransitionKind.CUT and self.duration_s != 0.0:
            raise ValueError("une coupe franche a une durée nulle")
        if self.kind is not TransitionKind.CUT and self.duration_s <= 0.0:
            raise ValueError(f"la transition {self.kind.value} exige une durée > 0")
        return self


class TextOverlay(Element):
    text: str = Field(min_length=1)
    at_s: float = Field(ge=0.0)
    duration_s: float = Field(gt=0.0)
    position: ScreenPosition = ScreenPosition.LOWER_THIRD
    emphasis: bool = False


class CurvePoint(Element):
    t: float = Field(ge=0.0, le=1.0)
    """Position normalisée dans l'épisode."""

    value: float = Field(ge=0.0, le=1.0)


class Curve(Element):
    """Courbe perceptive normalisée sur [0, 1] x [0, 1]."""

    name: str = Field(min_length=1)
    points: list[CurvePoint] = Field(min_length=2)

    @model_validator(mode="after")
    def _normalised(self) -> Self:
        times = [point.t for point in self.points]
        if times != sorted(times):
            raise ValueError(f"courbe {self.name} : points non ordonnés dans le temps")
        if len(set(times)) != len(times):
            raise ValueError(f"courbe {self.name} : deux points au même instant")
        if times[0] != 0.0 or times[-1] != 1.0:
            raise ValueError(f"courbe {self.name} : doit couvrir t=0 à t=1")
        return self

    def value_at(self, t: float) -> float:
        """Interpolation linéaire entre les points encadrant `t`."""
        if not 0.0 <= t <= 1.0:
            raise ValueError("t doit rester dans [0, 1]")
        previous = self.points[0]
        for point in self.points:
            if point.t >= t:
                if point.t == previous.t:
                    return point.value
                span = point.t - previous.t
                ratio = (t - previous.t) / span
                return previous.value + ratio * (point.value - previous.value)
            previous = point
        return self.points[-1].value


class CostEstimate(Element):
    amount_usd: float = Field(ge=0.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    basis: str = Field(default="unknown", min_length=1)
    """Comment le chiffre a été obtenu : tarif publié, mesure, extrapolation."""


class QaCheck(Element):
    """Résultat d'une vérification déterministe."""

    check_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    passed: bool
    observed: float | None = None
    expected: float | None = None
    tolerance: float | None = Field(default=None, ge=0.0)
    severity: Severity = Severity.MAJOR
    detail: str = ""
