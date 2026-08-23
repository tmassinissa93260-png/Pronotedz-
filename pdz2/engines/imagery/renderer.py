"""Moteur d'image déterministe.

Il exécute une `ImageSpec` et produit un vrai fichier PNG. Ce n'est pas un
générateur photoréaliste et cela ne prétend pas l'être : c'est un **moteur
schématique**, qui compose des aplats, des dégradés, des formes et des repères
à partir de la palette et du cadrage décidés dans la `VisualBible`.

Pourquoi ce choix plutôt qu'un adaptateur de fournisseur : aucun service
d'image n'est joignable depuis cet environnement (politique réseau), et écrire
un client qu'on ne peut pas exécuter reviendrait à livrer une capacité
fictive. Ce moteur, lui, tourne. Il produit des images mesurables, calquées,
reproductibles — de quoi faire fonctionner le 2.5D, l'observation et le
montage pour de bon.

Trois propriétés qui comptent davantage que le réalisme à ce stade :

* **déterministe** — même `ImageSpec`, même octets ; la graine vient du plan ;
* **calqué** — un fichier par calque, ce dont le parallaxe a besoin ;
* **conforme à la bible** — palette, densité, typographie, zone de sécurité.

Un adaptateur de fournisseur s'ajoutera derrière le même port sans que rien en
aval ne bouge.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from pdz2.contracts.common import Resolution
from pdz2.contracts.enums import ArtifactKind, Framing, ScreenPosition
from pdz2.contracts.render import RenderArtifact
from pdz2.contracts.visual import ImageSpec, LayerRole, LayerSpec, VisualBible

__all__ = [
    "ProceduralImageRenderer",
    "RenderedImage",
    "ImageRenderOutcome",
    "ImageRenderFailed",
    "RENDERER_VERSION",
]

RENDERER_VERSION = "1.0.0"

_SUBJECT_ANCHOR = {
    ScreenPosition.CENTER: (0.50, 0.50),
    ScreenPosition.LEFT: (0.32, 0.50),
    ScreenPosition.RIGHT: (0.68, 0.50),
    ScreenPosition.TOP: (0.50, 0.25),
    ScreenPosition.UPPER_THIRD: (0.50, 0.34),
    ScreenPosition.LOWER_THIRD: (0.50, 0.66),
    ScreenPosition.BOTTOM: (0.50, 0.75),
}

_FRAMING_SCALE = {
    Framing.EXTREME_WIDE: 0.22,
    Framing.WIDE: 0.34,
    Framing.MEDIUM_WIDE: 0.46,
    Framing.MEDIUM: 0.58,
    Framing.MEDIUM_CLOSE: 0.68,
    Framing.CLOSE: 0.80,
    Framing.EXTREME_CLOSE: 0.95,
    Framing.MACRO: 1.10,
    Framing.CUTAWAY_DIAGRAM: 0.72,
}
"""Part de la plus petite dimension du cadre occupée par le sujet."""


class ImageRenderFailed(RuntimeError):
    """Le moteur n'a pas pu produire l'image demandée."""


@dataclass(frozen=True)
class RenderedImage:
    spec_id: str
    shot_id: str
    composite_path: Path
    layer_paths: dict[LayerRole, Path]
    resolution: Resolution
    seed: int

    @property
    def layer_count(self) -> int:
        return len(self.layer_paths)


@dataclass
class ImageRenderOutcome:
    images: list[RenderedImage]
    artifacts: list[RenderArtifact]
    notes: list[str] = field(default_factory=list)

    def for_shot(self, shot_id: str) -> RenderedImage:
        for image in self.images:
            if image.shot_id == shot_id:
                return image
        raise KeyError(shot_id)


def _hex_to_rgb(colour: str) -> tuple[int, int, int]:
    value = colour.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def _mix(first: tuple[int, int, int], second: tuple[int, int, int], ratio: float):
    return tuple(
        int(round(a + (b - a) * ratio)) for a, b in zip(first, second, strict=True)
    )


@dataclass
class ProceduralImageRenderer:
    """Compose des images schématiques conformes à la bible visuelle."""

    name = "procedural-image"

    def render(
        self,
        *,
        specs: list[ImageSpec],
        visual_bible: VisualBible,
        into: Path,
    ) -> ImageRenderOutcome:
        directory = Path(into)
        directory.mkdir(parents=True, exist_ok=True)
        palette = [_hex_to_rgb(colour) for colour in visual_bible.color.palette]
        if len(palette) < 2:
            raise ImageRenderFailed("palette de moins de deux couleurs")

        images: list[RenderedImage] = []
        artifacts: list[RenderArtifact] = []

        for spec in specs:
            if spec.visual_bible_id != visual_bible.id:
                raise ImageRenderFailed(
                    f"{spec.shot_id} : l'image ne descend pas de cette bible"
                )
            rendered, produced = self._render_one(spec, visual_bible, palette, directory)
            images.append(rendered)
            artifacts.extend(produced)

        return ImageRenderOutcome(
            images=images,
            artifacts=artifacts,
            notes=[
                f"{len(images)} images composées par {self.name} {RENDERER_VERSION}",
                f"{sum(i.layer_count for i in images)} calques écrits",
                f"{images[0].resolution.width}×{images[0].resolution.height}"
                if images
                else "aucune image",
            ],
        )

    # ------------------------------------------------------------------ rendu

    def _render_one(
        self,
        spec: ImageSpec,
        bible: VisualBible,
        palette: list[tuple[int, int, int]],
        directory: Path,
    ) -> tuple[RenderedImage, list[RenderArtifact]]:
        width, height = spec.resolution.width, spec.resolution.height
        rng = random.Random(spec.seed)
        composite = Image.new("RGBA", (width, height), (*palette[0], 255))
        layer_paths: dict[LayerRole, Path] = {}
        artifacts: list[RenderArtifact] = []

        for layer in spec.layers:
            canvas = self._draw_layer(layer, spec, bible, palette, rng, width, height)
            path = directory / f"{spec.shot_id}-{layer.role.value}.png"
            canvas.save(path, "PNG", optimize=True)
            layer_paths[layer.role] = path
            composite = Image.alpha_composite(composite, canvas)
            artifacts.append(self._artifact(spec, path, spec.resolution))

        composite_path = directory / f"{spec.shot_id}.png"
        composite.convert("RGB").save(composite_path, "PNG", optimize=True)
        artifacts.append(self._artifact(spec, composite_path, spec.resolution))

        return (
            RenderedImage(
                spec_id=spec.id,
                shot_id=spec.shot_id,
                composite_path=composite_path,
                layer_paths=layer_paths,
                resolution=spec.resolution,
                seed=spec.seed,
            ),
            artifacts,
        )

    def _draw_layer(
        self,
        layer: LayerSpec,
        spec: ImageSpec,
        bible: VisualBible,
        palette: list[tuple[int, int, int]],
        rng: random.Random,
        width: int,
        height: int,
    ) -> Image.Image:
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        depth = layer.depth
        # Plus un calque est lointain, plus il se fond dans la dominante.
        base = _mix(palette[0], palette[min(1, len(palette) - 1)], depth)
        accent = palette[min(2, len(palette) - 1)]

        if layer.role in {LayerRole.SKY, LayerRole.BACKGROUND}:
            self._gradient(draw, width, height, base, palette[0], depth)
        elif layer.role is LayerRole.MIDGROUND:
            self._bands(draw, width, height, base, rng, bible.visual_density)
        elif layer.role is LayerRole.SUBJECT:
            self._subject(draw, spec, base, accent, width, height, bible)
        elif layer.role is LayerRole.FOREGROUND:
            self._foreground(draw, width, height, palette[0], rng, bible.visual_density)
        else:
            self._gradient(draw, width, height, base, palette[0], depth)

        if layer.role in {LayerRole.SKY, LayerRole.BACKGROUND}:
            # Le lointain est moins net : c'est ce qui crée la profondeur.
            canvas = canvas.filter(ImageFilter.GaussianBlur(radius=2 + 6 * (1 - depth)))
        return canvas

    @staticmethod
    def _gradient(draw, width, height, top, bottom, depth) -> None:
        for row in range(height):
            ratio = row / max(1, height - 1)
            draw.line(
                [(0, row), (width, row)],
                fill=(*_mix(top, bottom, ratio * (0.4 + 0.6 * depth)), 255),
            )

    @staticmethod
    def _bands(draw, width, height, colour, rng, density) -> None:
        count = 3 + int(6 * density)
        for index in range(count):
            top = int(height * (0.35 + 0.6 * index / count))
            thickness = max(2, int(height * 0.004 * (1 + density)))
            alpha = 70 + rng.randrange(0, 60)
            draw.rectangle(
                [(0, top), (width, top + thickness)], fill=(*colour, alpha)
            )

    @staticmethod
    def _subject(draw, spec: ImageSpec, base, accent, width, height, bible) -> None:
        """Le sujet : une forme centrée sur l'ancre de composition.

        Un moteur schématique ne dessine pas un moteur électrique. Il dessine
        *où* le sujet se trouve, *quelle place* il occupe, et *comment* il est
        éclairé — ce que le cadrage et la bible ont décidé. Le reste viendra
        d'un générateur, derrière le même port.
        """
        anchor_x, anchor_y = _SUBJECT_ANCHOR[spec.composition.subject_position]
        scale = _FRAMING_SCALE[spec.composition.framing]
        radius = int(min(width, height) * scale / 2)
        centre = (int(width * anchor_x), int(height * anchor_y))
        box = [
            centre[0] - radius,
            centre[1] - radius,
            centre[0] + radius,
            centre[1] + radius,
        ]
        draw.ellipse(box, fill=(*base, 235))

        # Repères : plus la densité visuelle est haute, plus il y en a.
        spokes = 6 + int(10 * bible.visual_density)
        for index in range(spokes):
            angle = 2 * math.pi * index / spokes
            outer = (
                centre[0] + int(radius * 0.92 * math.cos(angle)),
                centre[1] + int(radius * 0.92 * math.sin(angle)),
            )
            inner = (
                centre[0] + int(radius * 0.42 * math.cos(angle)),
                centre[1] + int(radius * 0.42 * math.sin(angle)),
            )
            draw.line([inner, outer], fill=(*accent, 220), width=max(2, radius // 60))
        draw.ellipse(
            [
                centre[0] - radius // 4,
                centre[1] - radius // 4,
                centre[0] + radius // 4,
                centre[1] + radius // 4,
            ],
            outline=(*accent, 255),
            width=max(2, radius // 40),
        )

    @staticmethod
    def _foreground(draw, width, height, colour, rng, density) -> None:
        count = 8 + int(24 * density)
        for _ in range(count):
            x = rng.randrange(0, width)
            y = rng.randrange(int(height * 0.55), height)
            size = rng.randrange(2, max(4, int(width * 0.008)))
            draw.ellipse(
                [x, y, x + size, y + size], fill=(*colour, 90 + rng.randrange(0, 60))
            )

    @staticmethod
    def _artifact(spec: ImageSpec, path: Path, resolution: Resolution) -> RenderArtifact:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return RenderArtifact(
            kind=ArtifactKind.IMAGE,
            path=path.name,
            sha256=digest,
            size_bytes=path.stat().st_size,
            resolution=resolution,
            provider=None,
            model=f"procedural-image {RENDERER_VERSION}",
            source_contract_id=spec.id,
            shot_id=spec.shot_id,
            seed=spec.seed,
            parent_id=spec.id,
        )
