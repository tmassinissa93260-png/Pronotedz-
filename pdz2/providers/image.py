"""Port des fournisseurs d'images.

Le moteur d'images procédural existait comme classe concrète : rien ne
permettait d'en brancher un autre. Ce port ouvre la place, sans rien changer
au reste — le renderer local le satisfait déjà par sa signature.

    ImageSpec  →  ImageProvider  →  fichiers PNG + RenderArtifact

Un `ImageSpec` n'est pas un prompt. C'est une description structurée : sujet,
calques, palette, ancres de continuité. Sa traduction en prompt appartient à
l'adaptateur, et **ne remonte jamais** : le prompt est une compilation
secondaire, jamais une source de vérité.

Comme pour la vidéo, un adaptateur déclare sa capacité — mesurée et datée,
jamais annoncée — et une capacité non joignable écarte le fournisseur au lieu
de faire échouer la production : le moteur procédural local reste le repli
garanti.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pdz2.contracts.capability import ProviderCapability
from pdz2.contracts.visual import ImageSpec, VisualBible

__all__ = ["ImageProvider", "ImageProviderUnavailable", "NO_IMAGE_PROVIDERS"]


class ImageProviderUnavailable(RuntimeError):
    """Aucun fournisseur d'images joignable pour cette demande."""


@runtime_checkable
class ImageProvider(Protocol):
    """Interface commune des moteurs d'images."""

    name: str

    def get_capabilities(self) -> ProviderCapability:
        """Sonde réellement le moteur. Ne jamais deviner son état."""

    def render(
        self,
        *,
        specs: list[ImageSpec],
        visual_bible: VisualBible,
        into: Path,
    ):
        """Produit les images, ou lève `ImageProviderUnavailable`.

        Même signature que le moteur procédural local, à dessein : le repli
        est un appel identique sur un autre objet.
        """


NO_IMAGE_PROVIDERS: tuple[ImageProvider, ...] = ()
"""Aucun adaptateur d'images distant n'est actif par défaut.

Les adaptateurs de `pdz2.providers.fal` s'ajoutent ici quand leur clé est
présente — voir `pdz2.providers.registry`. Sans clé, la liste reste vide et le
moteur procédural local produit seul.
"""
