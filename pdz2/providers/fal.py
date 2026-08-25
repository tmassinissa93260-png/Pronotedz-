"""Adaptateurs fal.ai — images (FLUX) et animation (image vers vidéo).

    ⚠️ JAMAIS EXÉCUTÉ DANS L'ENVIRONNEMENT OÙ CE CODE A ÉTÉ ÉCRIT.

`fal.run` y est injoignable (connexion refusée), et `docs.fal.ai` aussi : ce
code a été écrit sans pouvoir consulter la documentation ni appeler le
service une seule fois. Il est structurellement correct — sonde réelle, aucune
capacité inventée, échec bruyant — mais la forme exacte des charges utiles et
des réponses n'a pas été vérifiée contre l'API.

Son premier vrai test est le workflow GitHub Actions. Tant qu'un run n'a pas
abouti, considérer ces adaptateurs comme **non vérifiés**, et non comme
fonctionnels.

Ce qu'ils ne font jamais, en revanche, est certain :

* la sonde interroge réellement le service ; sans clé, elle rend UNAVAILABLE
  avec sa raison, jamais un état supposé ;
* un échec lève, il ne rend pas un fichier vide ;
* le fichier rendu est mesuré (taille non nulle) avant d'être annoncé ;
* aucune valeur de capacité n'est inventée : le coût reste ANNOUNCED tant
  qu'aucune facture n'a été relevée.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx

from pdz2.contracts.capability import CapabilityState, ProviderCapability
from pdz2.contracts.enums import ArtifactKind
from pdz2.contracts.motion import CameraMove
from pdz2.contracts.render import RenderArtifact, RenderStrategy
from pdz2.contracts.visual import ImageSpec, LayerRole, VisualBible
from pdz2.engines.imagery.renderer import ImageRenderOutcome, RenderedImage
from pdz2.providers.image import ImageProviderUnavailable
from pdz2.providers.prompting import animation_prompt, image_prompt, negative_prompt
from pdz2.providers.video import (
    ProviderUnavailable,
    VideoCapability,
    VideoJob,
    VideoResult,
)

__all__ = ["FalImageProvider", "FalVideoProvider", "FAL_KEY_ENV"]

FAL_KEY_ENV = "FAL_KEY"
BASE_URL = "https://fal.run"
_PROBE_TIMEOUT_S = 15.0
_JOB_TIMEOUT_S = 300.0


def _cle() -> str | None:
    valeur = os.environ.get(FAL_KEY_ENV, "").strip()
    return valeur or None


def _capacite(nom: str, *, joignable: bool, detail: str) -> ProviderCapability:
    return ProviderCapability(
        provider=nom,
        state=CapabilityState.AVAILABLE if joignable else CapabilityState.UNAVAILABLE,
        measured_at=datetime.now(UTC),
        measurement_method=f"appel HTTP à {BASE_URL}",
        detail=detail,
        requires_network=True,
        requires_credentials=True,
    )


def _sonder(nom: str) -> ProviderCapability:
    """Sonde réellement le service. Sans clé, il est indisponible, point."""
    cle = _cle()
    if cle is None:
        return _capacite(
            nom,
            joignable=False,
            detail=f"{FAL_KEY_ENV} absente de l'environnement",
        )
    try:
        reponse = httpx.get(
            BASE_URL,
            headers={"Authorization": f"Key {cle}"},
            timeout=_PROBE_TIMEOUT_S,
        )
    except httpx.HTTPError as erreur:
        return _capacite(nom, joignable=False, detail=f"{BASE_URL} injoignable : {erreur}")
    if reponse.status_code in {401, 403}:
        return _capacite(nom, joignable=False, detail=f"clé refusée ({reponse.status_code})")
    return _capacite(
        nom, joignable=True, detail=f"{BASE_URL} répond ({reponse.status_code})"
    )


def _telecharger(url: str, cible: Path) -> Path:
    """Rapatrie un fichier et vérifie qu'il n'est pas vide."""
    cible.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, timeout=_JOB_TIMEOUT_S, follow_redirects=True) as flux:
        flux.raise_for_status()
        with cible.open("wb") as sortie:
            for morceau in flux.iter_bytes():
                sortie.write(morceau)
    if cible.stat().st_size == 0:
        raise ProviderUnavailable(f"fichier vide rendu par le fournisseur : {cible.name}")
    return cible


def _appeler(chemin: str, charge: dict) -> dict:
    """Un appel synchrone à fal.run, avec sa clé et son délai."""
    cle = _cle()
    if cle is None:
        raise ProviderUnavailable(f"{FAL_KEY_ENV} absente")
    reponse = httpx.post(
        f"{BASE_URL}/{chemin}",
        headers={"Authorization": f"Key {cle}", "Content-Type": "application/json"},
        json=charge,
        timeout=_JOB_TIMEOUT_S,
    )
    if reponse.status_code >= 400:
        raise ProviderUnavailable(
            f"{chemin} : code {reponse.status_code} — {reponse.text[:300]}"
        )
    return reponse.json()


# ------------------------------------------------------------------- images


@dataclass
class FalImageProvider:
    """Images FLUX. Un calque par appel, pour rester séparable en 2.5D."""

    name: str = "fal-flux"
    model: str = "fal-ai/flux/schnell"
    steps: int = 4

    def get_capabilities(self) -> ProviderCapability:
        return _sonder(self.name)

    def render(
        self, *, specs: list[ImageSpec], visual_bible: VisualBible, into: Path
    ) -> ImageRenderOutcome:
        capacite = self.get_capabilities()
        if not capacite.usable:
            raise ImageProviderUnavailable(f"{self.name} : {capacite.detail}")

        dossier = Path(into)
        dossier.mkdir(parents=True, exist_ok=True)
        images: list[RenderedImage] = []
        artefacts: list[RenderArtifact] = []

        for spec in specs:
            if spec.visual_bible_id != visual_bible.id:
                raise ImageProviderUnavailable(
                    f"{spec.shot_id} : l'image ne descend pas de cette bible"
                )
            calques: dict[LayerRole, Path] = {}
            for calque in spec.layers:
                cible = dossier / f"{spec.shot_id}-{calque.role.value}.png"
                sortie = _appeler(
                    self.model,
                    {
                        "prompt": f"{image_prompt(spec, visual_bible)}. "
                                  f"Plan {calque.role.value} : {calque.description}",
                        "negative_prompt": negative_prompt(spec, visual_bible),
                        "image_size": {
                            "width": spec.resolution.width,
                            "height": spec.resolution.height,
                        },
                        "num_inference_steps": self.steps,
                        "num_images": 1,
                        **({"seed": spec.seed} if spec.seed is not None else {}),
                    },
                )
                fichiers = sortie.get("images") or []
                if not fichiers or not fichiers[0].get("url"):
                    raise ProviderUnavailable(
                        f"{spec.shot_id}/{calque.role.value} : réponse sans image"
                    )
                _telecharger(fichiers[0]["url"], cible)
                calques[calque.role] = cible
                artefacts.append(
                    _artefact_image(cible, spec, self.name, self.model)
                )

            composite = dossier / f"{spec.shot_id}.png"
            _composer(calques, composite, spec)
            images.append(
                RenderedImage(
                    spec_id=spec.id,
                    shot_id=spec.shot_id,
                    composite_path=composite,
                    layer_paths=calques,
                    resolution=spec.resolution,
                    seed=spec.seed or 0,
                )
            )

        return ImageRenderOutcome(
            images=images,
            artifacts=artefacts,
            notes=[
                f"{len(images)} image(s) générées par {self.name}/{self.model}",
                "adaptateur jamais vérifié hors CI : lire les journaux du run",
            ],
        )


def _artefact_image(chemin: Path, spec: ImageSpec, fournisseur: str, modele: str):
    import hashlib

    octets = chemin.read_bytes()
    return RenderArtifact(
        kind=ArtifactKind.IMAGE,
        path=chemin.name,
        sha256=hashlib.sha256(octets).hexdigest(),
        size_bytes=len(octets),
        resolution=spec.resolution,
        provider=fournisseur,
        model=modele,
        source_contract_id=spec.id,
        shot_id=spec.shot_id,
        parent_id=spec.id,
    )


def _composer(calques: dict, cible: Path, spec: ImageSpec) -> None:
    """Empile les calques dans l'ordre de profondeur, du fond vers l'avant."""
    from PIL import Image

    ordre = sorted(spec.layers, key=lambda item: -item.depth)
    fond = Image.new("RGB", (spec.resolution.width, spec.resolution.height), (0, 0, 0))
    for calque in ordre:
        chemin = calques.get(calque.role)
        if chemin is None:
            continue
        dessus = Image.open(chemin).convert("RGBA")
        if dessus.size != fond.size:
            dessus = dessus.resize(fond.size)
        fond.paste(dessus, (0, 0), dessus)
    fond.save(cible, "PNG")


# ---------------------------------------------------------------- animation


@dataclass
class FalVideoProvider:
    """Animation image vers vidéo. Le mouvement vient du MotionProgram."""

    name: str = "fal-kling"
    model: str = "fal-ai/kling-video/v2.1/standard/image-to-video"
    max_duration_s: float = 10.0
    cost_per_second_usd: float | None = None
    """Laissé vide à dessein : un tarif non facturé reste ANNOUNCED, et le
    gouverneur de coût refusera la dépense tant qu'il n'aura pas été relevé."""

    jobs: list[VideoJob] = field(default_factory=list)

    def get_capabilities(self) -> VideoCapability:
        return VideoCapability(
            capability=_sonder(self.name),
            model=self.model,
            strategies=[RenderStrategy.DIRECT_I2V, RenderStrategy.CONTROLLED_I2V],
            camera_moves=[
                CameraMove.LOCK,
                CameraMove.PUSH_IN,
                CameraMove.PULL_OUT,
                CameraMove.PAN,
                CameraMove.TILT,
            ],
            max_duration_s=self.max_duration_s,
            supports_image_to_video=True,
            supports_reference_images=False,
            cost_per_second_usd=self.cost_per_second_usd,
        )

    def generate(self, job: VideoJob) -> VideoResult:
        capacite = self.get_capabilities()
        if not capacite.usable:
            raise ProviderUnavailable(f"{self.name} : {capacite.capability.detail}")

        debut = time.monotonic()
        with job.start_image.open("rb") as source:
            import base64

            encodee = base64.b64encode(source.read()).decode("ascii")
        sortie = _appeler(
            self.model,
            {
                "image_url": f"data:image/png;base64,{encodee}",
                "prompt": job.prompt or animation_prompt(job.executable, None),
                "duration": str(int(round(job.executable.duration_s))),
            },
        )
        video = (sortie.get("video") or {}).get("url")
        if not video:
            raise ProviderUnavailable(f"{job.executable.shot_id} : réponse sans vidéo")
        cible = job.start_image.parent / f"{job.executable.shot_id}-i2v.mp4"
        _telecharger(video, cible)
        self.jobs.append(job)
        return VideoResult(
            path=cible,
            provider=self.name,
            model=self.model,
            latency_s=round(time.monotonic() - debut, 3),
            cost_usd=0.0,
        )
