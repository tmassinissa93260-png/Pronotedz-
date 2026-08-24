"""Port des fournisseurs vidéo.

Le cœur du système ne connaît aucun moteur vidéo : il connaît ce protocole.
Un adaptateur déclare sa capacité — **mesurée et datée**, jamais annoncée —
et rend un fichier dont l'observateur mesurera ensuite le contenu.

État réel dans ce dépôt : **aucun adaptateur n'est implémenté**. La politique
réseau de cet environnement refuse les hôtes de génération vidéo, et aucun
identifiant n'est disponible. Écrire un client qu'on ne peut ni joindre ni
vérifier reviendrait à livrer une capacité fictive — ce que le cahier des
charges interdit explicitement.

Ce n'est pas une impasse : le §46 exige que le système fonctionne **avec ou
sans génération vidéo IA**. Les stratégies déterministes (phase 7) sont le
chemin réel, et le routeur enregistre chaque dégradation qui en découle.

Quand un adaptateur arrivera, il implémentera ce protocole, se sondera comme
les autres, et rien en aval ne bougera.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import Field

from pdz2.contracts.base import Element
from pdz2.contracts.capability import CapabilityState, ProviderCapability
from pdz2.contracts.motion import CameraMove
from pdz2.contracts.render import RenderSpecExecutable, RenderStrategy

__all__ = [
    "VideoCapability",
    "VideoJob",
    "VideoResult",
    "VideoProvider",
    "ProviderUnavailable",
    "NO_VIDEO_PROVIDERS",
]


class ProviderUnavailable(RuntimeError):
    """Aucun fournisseur vidéo joignable pour cette demande."""


class VideoCapability(Element):
    """Ce qu'un moteur vidéo sait faire — mesuré, pas annoncé.

    Reprend la discipline du §14 : une valeur non mesurée récemment reste
    `UNKNOWN`, et un routeur ne compte jamais sur une capacité `UNKNOWN`.
    """

    capability: ProviderCapability
    model: str = Field(default="", max_length=200)
    """Modèle précis derrière le fournisseur. Le couple (fournisseur, modèle)
    est ce que la matrice de capacités date et ce que le registre de coût
    impute — un fournisseur seul ne suffit pas à savoir ce qu'on exécute."""

    strategies: list[RenderStrategy] = Field(default_factory=list)
    camera_moves: list[CameraMove] = Field(default_factory=list)
    max_duration_s: float | None = Field(default=None, gt=0.0)
    max_width: int | None = Field(default=None, gt=0)
    max_height: int | None = Field(default=None, gt=0)
    supports_image_to_video: bool = False
    supports_reference_images: bool = False
    cost_per_second_usd: float | None = Field(default=None, ge=0.0)
    measured_failure_rate: float | None = Field(default=None, ge=0.0, le=1.0)

    @property
    def usable(self) -> bool:
        return self.capability.state is CapabilityState.AVAILABLE


@dataclass(frozen=True)
class VideoJob:
    """Une exécution demandée à un fournisseur."""

    executable: RenderSpecExecutable
    start_image: Path
    reference_images: tuple[Path, ...] = ()
    prompt: str = ""
    """Compilation secondaire du MotionProgram. Jamais la source de vérité."""


@dataclass(frozen=True)
class VideoResult:
    path: Path
    provider: str
    model: str
    latency_s: float
    cost_usd: float


@runtime_checkable
class VideoProvider(Protocol):
    """Interface commune des moteurs vidéo."""

    name: str

    def get_capabilities(self) -> VideoCapability:
        """Sonde réellement le moteur. Ne jamais deviner l'état."""

    def generate(self, job: VideoJob) -> VideoResult:
        """Produit un fichier vidéo, ou lève `ProviderUnavailable`."""


NO_VIDEO_PROVIDERS: tuple[VideoProvider, ...] = ()
"""Aucun adaptateur vidéo n'est implémenté dans ce dépôt.

Constante explicite plutôt que liste vide anonyme : le routeur la reçoit, la
nomme dans ses dégradations, et le lecteur sait pourquoi.
"""
