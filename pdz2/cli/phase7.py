"""Commande de la phase 7 : rendre réellement les plans.

    pdz2 render  ROUTING + ASSETS → RENDER

Quatre stratégies déterministes, aucun fournisseur. C'est ce qui permet au
système d'aboutir « avec ou sans génération vidéo IA ».
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pdz2.contracts.pipeline import Stage
from pdz2.contracts.render import RenderSpecExecutable
from pdz2.contracts.visual import ImageSpec, LayerRole
from pdz2.engines.imagery.renderer import RenderedImage
from pdz2.renderers import DeterministicRenderer, FfmpegUnavailable, RenderFailed
from pdz2.state import EpisodeStateMachine, TransitionRefused
from pdz2.storage import EpisodeStore

__all__ = ["register", "cmd_render"]

RENDERS_DIR = "renders"
ASSETS_DIR = "assets"


def _rebuild_images(store: EpisodeStore) -> list[RenderedImage]:
    """Reconstitue les images rendues à partir des fichiers sur le disque.

    On ne fait pas confiance à une mémoire : les calques sont retrouvés par
    leur nom, et une absence est une erreur, pas un calque en moins.
    """
    assets = store.root / ASSETS_DIR
    images: list[RenderedImage] = []
    specs: list[ImageSpec] = sorted(
        store.load_collection("image_spec"), key=lambda spec: spec.shot_id
    )
    for spec in specs:
        composite = assets / f"{spec.shot_id}.png"
        if not composite.is_file():
            raise RenderFailed(
                f"{spec.shot_id} : image composite absente — relancer `pdz2 assets`"
            )
        layers: dict[LayerRole, Path] = {}
        for layer in spec.layers:
            path = assets / f"{spec.shot_id}-{layer.role.value}.png"
            if not path.is_file():
                raise RenderFailed(
                    f"{spec.shot_id} : calque {layer.role.value} absent"
                )
            layers[layer.role] = path
        images.append(
            RenderedImage(
                spec_id=spec.id,
                shot_id=spec.shot_id,
                composite_path=composite,
                layer_paths=layers,
                resolution=spec.resolution,
                seed=spec.seed or 0,
            )
        )
    return images


def cmd_render(args: argparse.Namespace) -> int:
    store = EpisodeStore(args.episode)
    if not store.has_snapshot():
        print(f"aucun épisode dans {args.episode}", file=sys.stderr)
        return 1
    machine = EpisodeStateMachine.resume(store.load_snapshot())
    executables: list[RenderSpecExecutable] = sorted(
        store.load_collection("render_spec_executable"), key=lambda e: e.shot_id
    )
    if not executables:
        print("pas de spécifications exécutables — lancer `pdz2 route`", file=sys.stderr)
        return 1

    renderer = DeterministicRenderer(keep_frames=args.keep_frames)
    capability = renderer.get_capabilities()
    print(f"encodeur : {capability.state.value} — {capability.detail}")

    try:
        machine.start(Stage.RENDER, reason=f"{len(executables)} plans")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1

    try:
        images = _rebuild_images(store)
        outcome = renderer.render(
            executables=executables,
            motion_programs=store.load_collection("motion_program"),
            images=images,
            into=store.root / RENDERS_DIR,
        )
    except (RenderFailed, FfmpegUnavailable) as failure:
        machine.fail(Stage.RENDER, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"rendu refusé : {failure}", file=sys.stderr)
        return 1

    for artifact in outcome.artifacts:
        store.save(artifact)
    machine.complete(
        Stage.RENDER,
        artifact_ids=[a.id for a in outcome.artifacts],
        cost_usd=0.0,
        reason=f"{len(outcome.renders)} plans rendus localement",
    )
    store.save_snapshot(machine.snapshot)

    for note in outcome.notes:
        print(note)
    for render in outcome.renders:
        print(
            f"  {render.shot_id}: {render.strategy.value:<15} "
            f"{render.frame_count:>4} images {render.duration_s:6.3f}s "
            f"{render.video_path.stat().st_size // 1024:>5} Kio "
            f"en {render.latency_s:.1f}s"
        )
    print(f"\nécrit : {store.root / RENDERS_DIR}")
    return 0


def register(subparsers) -> None:
    render = subparsers.add_parser("render", help="rendre les plans, réellement")
    render.add_argument("--episode", required=True)
    render.add_argument(
        "--keep-frames",
        action="store_true",
        dest="keep_frames",
        help="conserver les images intermédiaires, pour inspection",
    )
    render.set_defaults(func=cmd_render)
