"""Motion graphics déterministes : ce que la machine dessine par-dessus l'image.

Le compilateur de plans décidait déjà ce qui devait s'afficher — une grandeur
chiffrée entendue s'oublie, lue elle reste — et `ShotSpec.text_overlay`
portait cette décision jusqu'au bout de la chaîne. Personne ne la dessinait.
Le contrat était produit, validé, compté dans les notes, puis jeté.

Ce module est le consommateur qui manquait. Il ne décide rien : il reçoit une
incrustation déjà tranchée, une typographie déjà fixée par la bible visuelle,
et un instant. Il rend des pixels.

## Déterminisme

Aucun aléa, aucune horloge, aucune police cherchée « au mieux ». Le même
`TextOverlay` au même instant donne exactement les mêmes octets — c'est ce qui
permet à l'observateur de mesurer un mouvement sans confondre le bruit du
rendu avec le mouvement voulu.

## Ce qui bouge, et pourquoi

Une incrustation qui apparaît d'un coup se lit comme un défaut d'encodage. Un
fondu court la fait exister sans voler l'attention à l'image. Les valeurs sont
posées ici, en clair, plutôt que dispersées dans le compositeur.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from pdz2.contracts.common import TextOverlay
from pdz2.contracts.enums import ScreenPosition
from pdz2.contracts.visual import Typography

__all__ = [
    "draw_text_overlay",
    "overlay_visible_at",
    "overlay_opacity_at",
    "FONT_CANDIDATES",
    "FADE_S",
    "GraphicsUnavailable",
]

FADE_S = 0.25
"""Durée du fondu d'entrée et de sortie d'une incrustation.

Assez court pour ne pas retarder la lecture, assez long pour qu'un œil
enregistre l'apparition plutôt qu'un saut d'image.
"""

_MARGIN_PCT = 0.07
"""Marge au bord du cadre, en fraction de la plus petite dimension."""

_BOX_PADDING_PCT = 0.4
"""Marge intérieure du cartouche, en fraction de la hauteur de texte."""

FONT_CANDIDATES: tuple[str, ...] = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
)
"""Polices cherchées, dans l'ordre, et **par chemin exact**.

Demander « une police grasse » au système donnerait un rendu différent selon
la machine. Un chemin explicite se vérifie, et son absence se déclare au lieu
de se rattraper en silence.
"""


class GraphicsUnavailable(RuntimeError):
    """Aucune police utilisable : l'incrustation ne peut pas être dessinée."""


@lru_cache(maxsize=8)
def _font(size_px: int) -> ImageFont.FreeTypeFont:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size_px)
    raise GraphicsUnavailable(
        "aucune police parmi " + ", ".join(FONT_CANDIDATES) + " : installer "
        "le paquet « fonts-dejavu-core » pour dessiner les incrustations"
    )


def overlay_visible_at(overlay: TextOverlay, t_s: float) -> bool:
    """L'incrustation est-elle à l'écran à cet instant du plan ?"""
    return overlay.at_s <= t_s <= overlay.at_s + overlay.duration_s


def overlay_opacity_at(overlay: TextOverlay, t_s: float) -> float:
    """Opacité dans [0, 1] : fondu d'entrée, plateau, fondu de sortie."""
    if not overlay_visible_at(overlay, t_s):
        return 0.0
    fondu = min(FADE_S, overlay.duration_s / 2)
    if fondu <= 0:
        return 1.0
    depuis = t_s - overlay.at_s
    restant = overlay.at_s + overlay.duration_s - t_s
    return round(min(1.0, depuis / fondu, restant / fondu), 6)


@dataclass(frozen=True)
class _Placement:
    x: int
    y: int
    anchor: str


def _placement(
    position: ScreenPosition, width: int, height: int
) -> _Placement:
    marge = int(min(width, height) * _MARGIN_PCT)
    milieu_x = width // 2
    table = {
        ScreenPosition.TOP: _Placement(milieu_x, marge, "ma"),
        ScreenPosition.UPPER_THIRD: _Placement(milieu_x, height // 3, "mm"),
        ScreenPosition.CENTER: _Placement(milieu_x, height // 2, "mm"),
        ScreenPosition.LOWER_THIRD: _Placement(milieu_x, height * 2 // 3, "mm"),
        ScreenPosition.BOTTOM: _Placement(milieu_x, height - marge, "md"),
        ScreenPosition.LEFT: _Placement(marge, height // 2, "lm"),
        ScreenPosition.RIGHT: _Placement(width - marge, height // 2, "rm"),
    }
    return table[position]


def draw_text_overlay(
    canvas: Image.Image,
    overlay: TextOverlay,
    typography: Typography,
    t_s: float,
    *,
    ink: tuple[int, int, int] = (255, 255, 255),
    box: tuple[int, int, int] = (0, 0, 0),
) -> Image.Image:
    """Dessine l'incrustation sur une copie du cadre, ou rend le cadre tel quel.

    Le cadre d'origine n'est jamais modifié : le compositeur réutilise ses
    calques d'une image à l'autre, et les peindre en place laisserait une
    traînée.
    """
    opacite = overlay_opacity_at(overlay, t_s)
    if opacite <= 0.0:
        return canvas

    largeur, hauteur = canvas.size
    taille = max(14, int(hauteur * 0.045))
    police = _font(taille)
    texte = overlay.text.upper() if typography.uppercase else overlay.text

    calque = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    crayon = ImageDraw.Draw(calque)
    pose = _placement(overlay.position, largeur, hauteur)

    gauche, haut, droite, bas = crayon.textbbox(
        (pose.x, pose.y), texte, font=police, anchor=pose.anchor
    )
    marge = int(taille * _BOX_PADDING_PCT)
    alpha = int(round(255 * opacite))
    # Un cartouche derrière le texte : sans lui, un chiffre blanc sur une
    # image claire devient illisible, ce qui rend l'incrustation inutile.
    crayon.rectangle(
        [gauche - marge, haut - marge, droite + marge, bas + marge],
        fill=(*box, int(alpha * 0.72)),
    )
    crayon.text(
        (pose.x, pose.y),
        texte,
        font=police,
        anchor=pose.anchor,
        fill=(*ink, alpha),
    )
    if overlay.emphasis:
        # Un trait sous le cartouche : la grandeur chiffrée mérite d'être vue
        # comme une affirmation, pas comme un sous-titre de plus.
        epaisseur = max(2, taille // 12)
        crayon.rectangle(
            [gauche - marge, bas + marge, droite + marge, bas + marge + epaisseur],
            fill=(*ink, alpha),
        )

    fusion = canvas.convert("RGBA")
    fusion.alpha_composite(calque)
    return fusion.convert("RGB")
