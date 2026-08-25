"""Visual Bible et spécification d'image.

Toutes les générations dérivent de la bible : une `ImageSpec` cite la bible
dont elle hérite, et un plan ne peut pas contredire le registre visuel
décidé une fois pour l'épisode.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Self

from pydantic import Field, model_validator

from pdz2.contracts.base import Contract, Element, contract
from pdz2.contracts.common import Composition, Resolution
from pdz2.contracts.enums import AspectRatio

__all__ = [
    "ColorScheme",
    "Typography",
    "VisualBible",
    "LayerRole",
    "LayerSpec",
    "ImageSpec",
]

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class ColorScheme(Element):
    palette: list[str] = Field(min_length=2)
    """Couleurs en hexadécimal, la première est la dominante."""

    contrast: float = Field(default=0.5, ge=0.0, le=1.0)
    saturation: float = Field(default=0.5, ge=0.0, le=1.0)
    temperature: float = Field(default=0.0, ge=-1.0, le=1.0)
    """-1 froid, +1 chaud."""

    @model_validator(mode="after")
    def _hex_only(self) -> Self:
        bad = [colour for colour in self.palette if not _HEX.match(colour)]
        if bad:
            raise ValueError(f"couleurs non hexadécimales : {bad}")
        return self


class Typography(Element):
    family: str = Field(min_length=1)
    weight: int = Field(default=700, ge=100, le=900)
    uppercase: bool = False
    max_chars_per_line: int = Field(default=28, gt=0)
    safe_area_pct: float = Field(default=0.86, gt=0.0, le=1.0)


@contract("visual_bible", "1.0.0")
class VisualBible(Contract):
    """Registre visuel de l'épisode. Source unique du style."""

    director_state_id: str = Field(min_length=1)

    style: str = Field(min_length=1)
    lighting: str = Field(min_length=1)
    color: ColorScheme
    camera_language: str = Field(min_length=1)
    lens_language: str = Field(min_length=1)
    materials: list[str] = Field(default_factory=list)
    depth_of_field: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    graphics: str = Field(min_length=1)
    typography: Typography
    texture: str = Field(min_length=1)
    visual_density: float = Field(ge=0.0, le=1.0)
    forbidden: list[str] = Field(default_factory=list)
    """Ce que l'épisode ne montre jamais, quel que soit le générateur."""


class LayerRole(str, Enum):
    """Rôle d'un calque, pour le moteur 2.5D."""

    SKY = "sky"
    BACKGROUND = "background"
    MIDGROUND = "midground"
    SUBJECT = "subject"
    FOREGROUND = "foreground"
    OVERLAY = "overlay"


class LayerSpec(Element):
    """Calque d'une image destinée au parallaxe 2.5D."""

    role: LayerRole
    depth: float = Field(ge=0.0, le=1.0)
    """0 = plan le plus lointain, 1 = le plus proche de la caméra."""

    description: str = Field(min_length=1)
    must_be_separable: bool = True


@contract("image_spec", "1.0.0")
class ImageSpec(Contract):
    """Ce qu'une image doit contenir. Pas le prompt final d'un fournisseur."""

    shot_id: str = Field(min_length=1)
    visual_bible_id: str = Field(min_length=1)
    anchor_ids: list[str] = Field(default_factory=list)

    subject: str = Field(min_length=1)
    composition: Composition
    resolution: Resolution
    aspect_ratio: AspectRatio

    intent: str = Field(min_length=1)
    """Description structurée de ce qui doit être visible. Compilée en prompt
    par l'adaptateur, jamais envoyée telle quelle depuis le Director."""

    forbidden: list[str] = Field(default_factory=list)
    layers: list[LayerSpec] = Field(default_factory=list)
    seed: int | None = None

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if not self.resolution.matches(self.aspect_ratio):
            raise ValueError(
                f"résolution {self.resolution.width}x{self.resolution.height} "
                f"incompatible avec le format {self.aspect_ratio.value}"
            )
        depths = [layer.depth for layer in self.layers]
        if len(set(depths)) != len(depths):
            raise ValueError("deux calques à la même profondeur")
        roles = [layer.role for layer in self.layers]
        if len(set(roles)) != len(roles):
            raise ValueError("deux calques pour le même rôle")
        if self.layers and depths != sorted(depths):
            raise ValueError("calques non ordonnés du fond vers l'avant")
        return self
