"""Renderers déterministes : still, Ken Burns, parallaxe 2.5D, procédural.

Ce sont les quatre stratégies qui n'ont besoin de personne. Elles font tourner
le système entier sans le moindre fournisseur — ce que le §46 exige :
« capable de fonctionner avec ou sans génération vidéo IA ».

Toutes suivent la même mécanique : lire les calques produits en phase 5,
échantillonner le `MotionProgram` image par image avec l'évaluateur de
trajectoires, composer chaque image, puis laisser ffmpeg encoder.

    STILL         une image, répétée. Rien ne bouge, et c'est assumé.
    KEN_BURNS     recadrage progressif sur l'image composite.
    PARALLAX_2_5D chaque calque se décale selon sa profondeur.
    PROCEDURAL    parallaxe + rotation ou orbite du sujet.

Le mouvement vient du `MotionProgram`, jamais d'une phrase. Le prompt n'existe
pas ici : il n'y a personne à qui parler.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from pdz2.contracts.capability import ProviderCapability
from pdz2.contracts.enums import ArtifactKind
from pdz2.contracts.motion import CameraMove, MotionPrimitive, MotionProgram
from pdz2.contracts.render import (
    RenderArtifact,
    RenderSpecExecutable,
    RenderStrategy,
)
from pdz2.contracts.visual import LayerRole, Typography
from pdz2.engines.imagery.renderer import RenderedImage
from pdz2.renderers.ffmpeg import (
    EncodingFailed,
    FfmpegUnavailable,
    encode_raw_frames,
    ffmpeg_capability,
    probe_video,
)
from pdz2.renderers.graphics import draw_text_overlay
from pdz2.renderers.motion_paths import sample_trajectory

__all__ = [
    "DeterministicRenderer",
    "ShotRender",
    "RenderOutcome",
    "RenderFailed",
    "SUPPORTED_STRATEGIES",
    "RENDERER_VERSION",
]

RENDERER_VERSION = "1.1.0"
"""1.1.0 : les incrustations de texte sont réellement dessinées."""

_DEFAULT_TYPOGRAPHY = Typography(family="DejaVu Sans", weight=700, uppercase=False)
"""Réglage de repli quand la bible n'est pas fournie au renderer.

Ne pas dessiner du tout serait pire : le compilateur de plans a décidé qu'une
grandeur chiffrée devait apparaître, et la casse ne justifie pas de l'effacer.
"""

SUPPORTED_STRATEGIES = frozenset(
    {
        RenderStrategy.STILL,
        RenderStrategy.KEN_BURNS,
        RenderStrategy.PARALLAX_2_5D,
        RenderStrategy.PROCEDURAL,
    }
)

MAX_ZOOM = 0.18
"""Amplitude maximale d'un recadrage, en fraction de cadre.

Au-delà, le recadrage se voit comme un zoom numérique — ce qu'il est.
"""

MAX_PARALLAX_SHIFT = 0.09
"""Décalage maximal du calque le plus proche, en fraction de largeur."""

_OVERSCAN = 1.30
"""Marge de sécurité autour du cadre, pour que le mouvement ne révèle pas de bord."""


class RenderFailed(RuntimeError):
    """Le rendu d'un plan a échoué. La raison est nommée."""


@dataclass(frozen=True)
class ShotRender:
    shot_id: str
    strategy: RenderStrategy
    video_path: Path
    frame_count: int
    duration_s: float
    latency_s: float


@dataclass
class RenderOutcome:
    renders: list[ShotRender]
    artifacts: list[RenderArtifact]
    notes: list[str] = field(default_factory=list)

    def for_shot(self, shot_id: str) -> ShotRender:
        for render in self.renders:
            if render.shot_id == shot_id:
                return render
        raise KeyError(shot_id)


@dataclass
class DeterministicRenderer:
    """Exécute les stratégies locales. Aucun réseau, aucun identifiant."""

    name = "deterministic"
    keep_frames: bool = False

    def get_capabilities(self) -> ProviderCapability:
        return ffmpeg_capability()

    def render(
        self,
        *,
        executables: list[RenderSpecExecutable],
        motion_programs: list[MotionProgram],
        images: list[RenderedImage],
        into: Path,
        typography: Typography | None = None,
    ) -> RenderOutcome:
        """Rend chaque plan. `typography` vient de la bible visuelle.

        Sans elle, les incrustations sont dessinées avec un réglage par
        défaut plutôt que sautées : une grandeur chiffrée décidée par le
        compilateur de plans doit apparaître, la casse est un détail de style.
        """
        capability = self.get_capabilities()
        if not capability.usable:
            raise FfmpegUnavailable(
                f"rendu impossible : {capability.detail} — aucune stratégie locale "
                "ne peut encoder sans lui"
            )

        motions = {program.id: program for program in motion_programs}
        by_shot = {image.shot_id: image for image in images}
        directory = Path(into)
        directory.mkdir(parents=True, exist_ok=True)

        renders: list[ShotRender] = []
        artifacts: list[RenderArtifact] = []
        for executable in executables:
            if executable.strategy not in SUPPORTED_STRATEGIES:
                raise RenderFailed(
                    f"{executable.shot_id} : stratégie {executable.strategy.value} "
                    "hors du périmètre des renderers déterministes"
                )
            image = by_shot.get(executable.shot_id)
            if image is None:
                raise RenderFailed(
                    f"{executable.shot_id} : aucune image de départ"
                )
            motion = self._motion_for(executable, motions)
            render, artifact = self._render_one(
                executable, motion, image, directory, typography
            )
            renders.append(render)
            artifacts.append(artifact)

        return RenderOutcome(
            renders=renders,
            artifacts=artifacts,
            notes=[
                f"{len(renders)} plans rendus par {self.name} {RENDERER_VERSION}",
                f"{sum(r.frame_count for r in renders)} images composées",
                f"{sum(r.duration_s for r in renders):.2f}s de vidéo",
                capability.detail,
            ],
        )

    # ------------------------------------------------------------------ rendu

    @staticmethod
    def _motion_for(executable, motions) -> MotionProgram | None:
        for program in motions.values():
            if program.shot_id == executable.shot_id:
                return program
        return None

    def _render_one(
        self,
        executable: RenderSpecExecutable,
        motion: MotionProgram | None,
        image: RenderedImage,
        directory: Path,
        typography: Typography | None = None,
    ) -> tuple[ShotRender, RenderArtifact]:
        started = time.monotonic()
        width = executable.resolution.width
        height = executable.resolution.height
        frame_count = max(1, int(round(executable.duration_s * executable.fps)))
        layers = self._load_layers(executable, image, width, height)
        video_path = directory / f"{executable.shot_id}.mp4"

        def frames():
            for index in range(frame_count):
                t = index / max(1, frame_count - 1) if frame_count > 1 else 0.0
                composed = self._compose(
                    executable, motion, layers, t, width, height
                )
                if executable.text_overlay is not None:
                    composed = draw_text_overlay(
                        composed,
                        executable.text_overlay,
                        typography or _DEFAULT_TYPOGRAPHY,
                        t * executable.duration_s,
                    )
                if self.keep_frames:
                    debug = directory / f"frames-{executable.shot_id}"
                    debug.mkdir(parents=True, exist_ok=True)
                    composed.save(debug / f"f{index:05d}.png", "PNG", compress_level=1)
                yield composed.tobytes()

        try:
            encode_raw_frames(
                frames=frames(),
                width=width,
                height=height,
                fps=executable.fps,
                out_path=video_path,
            )
        except (EncodingFailed, OSError) as error:
            raise RenderFailed(f"{executable.shot_id} : {error}") from error

        probe = probe_video(video_path)
        latency = time.monotonic() - started
        artifact = RenderArtifact(
            kind=ArtifactKind.VIDEO,
            path=video_path.name,
            sha256=hashlib.sha256(video_path.read_bytes()).hexdigest(),
            size_bytes=probe.size_bytes,
            duration_s=round(probe.duration_s, 6),
            resolution=executable.resolution,
            fps=int(round(probe.fps)) or executable.fps,
            provider=None,
            model=f"{self.name} {RENDERER_VERSION} / {executable.strategy.value}",
            source_contract_id=executable.id,
            executable_spec_id=executable.id,
            shot_id=executable.shot_id,
            actual_cost_usd=0.0,
            latency_s=round(latency, 4),
            parent_id=executable.id,
        )
        return (
            ShotRender(
                shot_id=executable.shot_id,
                strategy=executable.strategy,
                video_path=video_path,
                frame_count=probe.frame_count,
                duration_s=probe.duration_s,
                latency_s=round(latency, 4),
            ),
            artifact,
        )

    @staticmethod
    def _load_layers(
        executable: RenderSpecExecutable,
        image: RenderedImage,
        width: int,
        height: int,
    ) -> list[tuple[float, Image.Image]]:
        """Calques agrandis, prêts à être décalés sans révéler de bord."""
        target = (int(width * _OVERSCAN), int(height * _OVERSCAN))
        if executable.strategy in {RenderStrategy.STILL, RenderStrategy.KEN_BURNS}:
            with Image.open(image.composite_path) as opened:
                return [(0.5, opened.convert("RGBA").resize(target, Image.LANCZOS))]

        ordered = sorted(image.layer_paths.items(), key=lambda item: _DEPTH[item[0]])
        loaded: list[tuple[float, Image.Image]] = []
        for role, path in ordered:
            with Image.open(path) as opened:
                loaded.append(
                    (_DEPTH[role], opened.convert("RGBA").resize(target, Image.LANCZOS))
                )
        return loaded or [(0.5, Image.new("RGBA", target, (0, 0, 0, 255)))]

    def _compose(
        self,
        executable: RenderSpecExecutable,
        motion: MotionProgram | None,
        layers: list[tuple[float, Image.Image]],
        t: float,
        width: int,
        height: int,
    ) -> Image.Image:
        strategy = executable.strategy
        offset = self._camera_offset(executable, motion, t)
        zoom = self._zoom(executable, t)

        canvas = Image.new("RGB", (width, height), (0, 0, 0))
        for depth, layer in layers:
            # Un calque proche se décale davantage : c'est tout le parallaxe.
            factor = depth if strategy in {
                RenderStrategy.PARALLAX_2_5D,
                RenderStrategy.PROCEDURAL,
            } else 1.0
            shift_x = offset[0] * factor * width
            shift_y = offset[1] * factor * height

            frame = layer
            if strategy is RenderStrategy.PROCEDURAL and depth >= 0.5 and motion:
                frame = self._spin(frame, motion, t)

            # Recadrage et redimensionnement en une passe : `box` désigne la
            # zone source à lire, et la sortie fait directement la taille du
            # cadre. Redimensionner le calque entier à chaque image coûterait
            # plusieurs secondes par plan pour un résultat identique.
            source_w = width / (1.0 + zoom)
            source_h = height / (1.0 + zoom)
            left = (frame.width - source_w) / 2 - shift_x
            top = (frame.height - source_h) / 2 - shift_y
            left = max(0.0, min(left, frame.width - source_w))
            top = max(0.0, min(top, frame.height - source_h))
            cropped = frame.resize(
                (width, height),
                Image.BILINEAR,
                box=(left, top, left + source_w, top + source_h),
            )
            canvas.paste(cropped, (0, 0), cropped)
        return canvas

    @staticmethod
    def _camera_offset(
        executable: RenderSpecExecutable, motion: MotionProgram | None, t: float
    ) -> tuple[float, float]:
        """Déplacement caméra à l'instant t, en fraction de cadre."""
        if executable.strategy is RenderStrategy.STILL or motion is None:
            return (0.0, 0.0)
        move = executable.execution_camera
        if move is CameraMove.LOCK:
            return (0.0, 0.0)
        sample = sample_trajectory(motion.trajectory, t)
        amplitude = MAX_PARALLAX_SHIFT * motion.perceptual_target.motion_energy
        if move in {CameraMove.PAN, CameraMove.TRACK, CameraMove.PARALLAX}:
            return (sample.x * amplitude, 0.0)
        if move is CameraMove.TILT:
            return (0.0, sample.y * amplitude)
        if move is CameraMove.ORBIT:
            return (sample.x * amplitude, sample.z * amplitude * 0.4)
        if move is CameraMove.HANDHELD:
            return (sample.x * amplitude, sample.y * amplitude)
        return (0.0, 0.0)

    @staticmethod
    def _zoom(executable: RenderSpecExecutable, t: float) -> float:
        """Recadrage progressif. Positif on entre, négatif on sort."""
        if executable.strategy is RenderStrategy.STILL:
            return 0.0
        move = executable.execution_camera
        if move is CameraMove.PUSH_IN:
            return MAX_ZOOM * t
        if move is CameraMove.PULL_OUT:
            return MAX_ZOOM * (1.0 - t)
        if executable.strategy is RenderStrategy.KEN_BURNS:
            # Sans mouvement caméra nommé, Ken Burns entre lentement : c'est sa
            # définition, et le routeur ne l'a pas choisi pour rien.
            return MAX_ZOOM * 0.6 * t
        return 0.0

    @staticmethod
    def _spin(layer: Image.Image, motion: MotionProgram, t: float) -> Image.Image:
        """Rotation du sujet, quand le mouvement du sujet en demande une."""
        primitive = motion.subject_motion.primitive
        if primitive not in {MotionPrimitive.ROTATE, MotionPrimitive.ORBIT}:
            return layer
        degrees = motion.subject_motion.trajectory.amplitude * t
        return layer.rotate(degrees, resample=Image.BILINEAR, center=None)


_DEPTH: dict[LayerRole, float] = {
    LayerRole.SKY: 0.05,
    LayerRole.BACKGROUND: 0.25,
    LayerRole.MIDGROUND: 0.45,
    LayerRole.SUBJECT: 0.70,
    LayerRole.FOREGROUND: 1.00,
    LayerRole.OVERLAY: 1.00,
}
"""Profondeur perçue par rôle de calque. Fixe l'ampleur du décalage."""
