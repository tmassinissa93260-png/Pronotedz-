"""Un fournisseur vidéo réel, mais local — réservé aux tests.

Ce module **n'est pas** un adaptateur : il ne prétend joindre aucun service.
Il implémente le port `VideoProvider` avec un moteur qui existe réellement
ici — ffmpeg — pour que le chemin « stratégie générative → fournisseur →
artefact » soit exécuté pour de vrai par la suite de tests, au lieu de rester
du code mort en attendant qu'un adaptateur arrive.

La distinction compte, et elle est tenue par la structure :

* il vit dans `pdz2/tests/`, jamais dans `pdz2/providers/` ;
* `NO_VIDEO_PROVIDERS` reste vide, donc la chaîne réelle ne le voit pas ;
* `pdz2 capabilities` ne le sonde pas et continue de dire qu'aucun
  fournisseur vidéo n'est joignable.

Ce qu'il prouve n'est donc pas « PDZ 2 sait générer de la vidéo par IA » — il
ne le sait pas. Il prouve que le jour où un adaptateur arrivera, la couche qui
l'appelle, mesure son résultat et déclare ses échecs est déjà écrite et
vérifiée.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pdz2.contracts.capability import CapabilityState, ProviderCapability
from pdz2.contracts.motion import CameraMove
from pdz2.contracts.render import RenderStrategy
from pdz2.providers.video import (
    ProviderUnavailable,
    VideoCapability,
    VideoJob,
    VideoResult,
)
from pdz2.renderers.ffmpeg import encode_raw_frames

__all__ = ["LocalVideoDouble", "AlwaysFailingProvider"]


@dataclass
class LocalVideoDouble:
    """Implémente le port en encodant réellement un dégradé animé."""

    name: str = "atelier-local"
    model: str = "double-1"
    state: CapabilityState = CapabilityState.AVAILABLE
    strategies: tuple[RenderStrategy, ...] = (
        RenderStrategy.DIRECT_I2V,
        RenderStrategy.CONTROLLED_I2V,
        RenderStrategy.HYBRID,
    )
    max_duration_s: float | None = None
    cost_per_second_usd: float = 0.0
    into: Path | None = None
    jobs: list[VideoJob] = field(default_factory=list)

    def get_capabilities(self) -> VideoCapability:
        return VideoCapability(
            capability=ProviderCapability(
                provider=self.name,
                state=self.state,
                measured_at=datetime.now(UTC) if self.state is not CapabilityState.UNKNOWN else None,
                measurement_method="double de test : encodage local vérifié",
                detail="fournisseur de test, local, sans réseau",
                requires_network=False,
            ),
            model=self.model,
            strategies=list(self.strategies),
            camera_moves=[CameraMove.LOCK, CameraMove.PUSH_IN, CameraMove.ORBIT],
            max_duration_s=self.max_duration_s,
            supports_image_to_video=True,
            supports_reference_images=True,
            cost_per_second_usd=self.cost_per_second_usd,
        )

    def generate(self, job: VideoJob) -> VideoResult:
        capability = self.get_capabilities()
        if not capability.usable:
            raise ProviderUnavailable(f"{self.name} : {capability.capability.detail}")
        cible = (self.into or job.start_image.parent) / f"{job.executable.shot_id}-i2v.mp4"
        largeur = job.executable.resolution.width
        hauteur = job.executable.resolution.height
        images = max(2, int(round(job.executable.duration_s * job.executable.fps)))
        debut = time.monotonic()

        def trames():
            for index in range(images):
                t = index / (images - 1)
                # Un dégradé qui se déplace : le résultat bouge réellement,
                # donc l'observateur mesurera un mouvement non nul.
                niveau = bytes([int(20 + 200 * t)]) * (largeur * hauteur * 3)
                yield niveau

        encode_raw_frames(
            frames=trames(),
            width=largeur,
            height=hauteur,
            fps=job.executable.fps,
            out_path=cible,
        )
        self.jobs.append(job)
        return VideoResult(
            path=cible,
            provider=self.name,
            model=self.model,
            latency_s=round(time.monotonic() - debut, 4),
            cost_usd=round(self.cost_per_second_usd * job.executable.duration_s, 6),
        )


@dataclass
class AlwaysFailingProvider:
    """Se déclare joignable, puis échoue. Le cas qui compte le plus."""

    name: str = "atelier-en-panne"
    appels: int = 0

    def get_capabilities(self) -> VideoCapability:
        return VideoCapability(
            capability=ProviderCapability(
                provider=self.name,
                state=CapabilityState.AVAILABLE,
                measured_at=datetime.now(UTC),
                measurement_method="double de test",
                requires_network=False,
            ),
            model="panne-1",
            strategies=[RenderStrategy.DIRECT_I2V, RenderStrategy.HYBRID],
            supports_image_to_video=True,
        )

    def generate(self, job: VideoJob) -> VideoResult:
        self.appels += 1
        raise ProviderUnavailable("le moteur a refusé la tâche (double de test)")
