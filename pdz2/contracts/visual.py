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
from pdz2.contracts.common import Composition, HexColour, Resolution
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
    palette: list[HexColour] = Field(min_length=2)
    """La première est la dominante. La forme est tenue par le type lui-même."""

    contrast: float = Field(default=0.5, ge=0.0, le=1.0)
    saturation: float = Field(default=0.5, ge=0.0, le=1.0)
    temperature: float = Field(default=0.0, ge=-1.0, le=1.0)
    """-1 froid, +1 chaud."""


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


@contract("image_spec", "1.2.0")
class ImageSpec(Contract):
    """Ce qu'une image doit contenir. Pas le prompt final d'un fournisseur."""

    shot_id: str = Field(min_length=1)
    visual_bible_id: str = Field(min_length=1)
    anchor_ids: list[str] = Field(default_factory=list)

    claim_id: str | None = None
    """Affirmation que cette image doit démontrer. Ajouté en 1.1.0."""

    evidence_required: str | None = None
    """Ce qui doit être visible pour que l'image compte comme preuve.

    Ces deux champs manquaient, et leur absence est une des causes des images
    génériques du run #7. Le `ShotSpec` portait fidèlement `claim_id` et
    `evidence_required`, recopiés du brief — puis le compilateur d'images les
    laissait tomber. Le générateur recevait un **sujet**, jamais une
    **preuve** : on lui demandait de représenter un thème, et il le faisait.

    Une ouverture ou une chute ne démontre rien : les deux champs y valent
    `None`, et c'est une réponse, pas un oubli."""

    subject_matter: str | None = None
    """Le sujet de l'épisode, tel que la demande l'a écrit. Ajouté en 1.2.0.

    Sans lui, aucun élément du prompt ne nommait ce dont l'épisode parle. Le
    run #8 le prouve mot pour mot : pour un épisode « Comment fonctionne une
    voiture électrique ? », la commande envoyée au fournisseur disait
    « Ouverture dans le registre décidé : technical. […] Décor : atelier de
    fabrication et laboratoire. » Le seul substantif concret de la phrase
    était le décor décidé par la bible — et le fournisseur a rendu ce qu'on
    lui demandait : des ateliers, des entrepôts, des garages vides. Ni
    voiture, ni moteur, ni batterie.

    `subject` porte le sujet **du plan**, `evidence_required` ce qu'il doit
    prouver ; ni l'un ni l'autre ne porte le domaine. Un plan peut demander
    « le rotor tourne dans le stator » sans que rien ne dise qu'il s'agit
    d'une voiture. Ce champ le dit."""

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
