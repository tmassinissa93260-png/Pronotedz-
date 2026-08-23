"""Spécification et génération d'images.

Phase 4 : `ImageSpecCompiler` — ce qu'une image doit contenir.
Phase 5 : moteur de rendu déterministe — ce qu'elle devient réellement.
"""

from pdz2.engines.imagery.specs import (
    RESOLUTIONS,
    ImageSpecCompiler,
    ImageSpecOutcome,
    layers_for,
)

__all__ = ["ImageSpecCompiler", "ImageSpecOutcome", "RESOLUTIONS", "layers_for"]
