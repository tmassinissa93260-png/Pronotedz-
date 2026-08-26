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

    supports_alpha_layers: bool = False
    """Ce moteur sait-il rendre un calque à fond transparent ?

    Non, et ce n'est pas un réglage : `flux` est un moteur texte-vers-image
    qui rend un PNG **opaque**, sans canal alpha utile. Mesuré sur les
    fichiers du run #8 — alpha = 255 sur la totalité des pixels des vingt-deux
    calques rendus.

    La conséquence est fatale et elle est restée invisible deux runs de suite.
    `LayerSpec.must_be_separable` est une exigence du contrat ; empiler des
    images opaques n'est pas composer, c'est écraser. Au run #7 le tri était
    descendant et le calque le plus lointain recouvrait tout ; j'ai corrigé le
    tri, et au run #8 c'est le plus **proche** qui recouvrait tout — le même
    défaut par l'autre bout. Sur un plan large à quatre calques, trois images
    générées sont jetées et celle qui reste est celle dont la commande dit
    « éléments de premier plan de la scène, cadre partiel » : précisément la
    moins susceptible de montrer le sujet.

    C'est ce qu'on voit à l'écran du run #8 : des cartons au premier plan d'un
    entrepôt, un anneau de néon dans un couloir, un homme de dos dans une
    embrasure. Des avant-plans, quatre fois payés, sans leur scène.
    """

    def get_capabilities(self) -> ProviderCapability:
        return _sonder(self.name)

    @staticmethod
    def _calque_porteur(spec: ImageSpec):
        """Le calque à rendre quand on ne peut en rendre qu'un.

        Celui qui porte le sujet, puisque c'est le sujet qu'on veut voir. À
        défaut, le plus proche — un cadrage plat n'a de toute façon qu'un
        calque, et il est déjà le bon.
        """
        for calque in spec.layers:
            if calque.role is LayerRole.SUBJECT:
                return calque
        return max(spec.layers, key=lambda item: item.depth) if spec.layers else None

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
            # Un moteur qui ne sait pas rendre de transparence ne rend pas des
            # calques : il rend une image. En demander quatre coûte quatre
            # appels pour n'en garder qu'un, et celui qu'on garde n'est même
            # pas celui du sujet.
            if self.supports_alpha_layers:
                demandes = list(spec.layers)
            else:
                porteur = self._calque_porteur(spec)
                demandes = [porteur] if porteur is not None else []
            for calque in demandes:
                cible = dossier / f"{spec.shot_id}-{calque.role.value}.png"
                sortie = _appeler(
                    self.model,
                    {
                        "prompt": image_prompt(spec, visual_bible, calque),
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
            if self.supports_alpha_layers:
                _composer(calques, composite, spec)
            else:
                # Un seul calque : le composite EST ce calque. Passer par
                # `_composer` donnerait le même octet pour un aller-retour
                # disque, et laisserait croire qu'une composition a eu lieu.
                seul = next(iter(calques.values()))
                composite.write_bytes(seul.read_bytes())
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
                *(
                    []
                    if self.supports_alpha_layers
                    else [
                        f"{self.name} rend des images opaques : un seul calque "
                        "demandé par plan, celui du sujet. Le parallaxe 2.5D "
                        "n'est pas disponible sur ces images — le routeur le "
                        "constate et le déclare."
                    ]
                ),
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
    """Empile les calques du fond vers l'avant.

    La convention de profondeur du système est fixée par le renderer 2.5D :
    **une profondeur haute est un calque proche**, puisque c'est lui qui se
    décale le plus en parallaxe. Peindre du fond vers l'avant impose donc un
    tri **croissant**.

    Ce tri était descendant, et le défaut est resté invisible pendant tout le
    développement : le moteur local dessine des calques **transparents**, sur
    lesquels l'ordre ne change presque rien. Un moteur génératif rend des
    images **opaques** — le calque le plus lointain était donc peint en
    dernier, et recouvrait tout le reste. Sur un plan large à quatre calques,
    l'image finale n'était que la génération demandée pour « fond lointain ».

    C'est une des causes des images génériques du run #7, et elle ne pouvait
    apparaître qu'en branchant un vrai fournisseur.

    Corriger le tri n'a pas suffi, et le run #8 l'a montré : quand tous les
    calques sont opaques, peindre du fond vers l'avant fait gagner le plus
    proche au lieu du plus lointain. Le même défaut par l'autre bout. Empiler
    des images opaques n'est pas composer, c'est écraser.

    Cette fonction ne s'appelle donc plus que sur un moteur qui déclare savoir
    rendre de la transparence. Pour les autres, un seul calque est demandé, et
    il n'y a rien à composer.
    """
    from PIL import Image

    ordre = sorted(spec.layers, key=lambda item: item.depth)
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
            # Zéro parce que rien n'a été facturé ET relevé, pas parce que
            # l'appel est gratuit : `cost_per_second_usd` reste vide pour la
            # même raison, et c'est ce vide qui fait refuser le gouverneur.
            cost_usd=0.0,
        )
