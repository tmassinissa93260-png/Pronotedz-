"""Spécification et génération d'images.

Phase 4 : `ImageSpecCompiler` — ce qu'une image doit contenir.
Phase 5 : `ProceduralImageRenderer` — un moteur déterministe réel, qui écrit
de vrais PNG calqués. Aucun fournisseur n'est joignable ici ; ce moteur, lui,
tourne, et un adaptateur s'ajoutera derrière le même port.
"""

from pdz2.engines.imagery.renderer import (
    RENDERER_VERSION,
    ImageRenderFailed,
    ImageRenderOutcome,
    ProceduralImageRenderer,
    RenderedImage,
)
from pdz2.engines.imagery.specs import (
    RESOLUTIONS,
    ImageSpecCompiler,
    ImageSpecOutcome,
    layers_for,
)

__all__ = [
    "ImageSpecCompiler",
    "ImageSpecOutcome",
    "RESOLUTIONS",
    "layers_for",
    "ProceduralImageRenderer",
    "RenderedImage",
    "ImageRenderOutcome",
    "ImageRenderFailed",
    "RENDERER_VERSION",
]
