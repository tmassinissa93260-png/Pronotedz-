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
from pdz2.contracts.research import TopicRequest
from pdz2.contracts.visual import ImageSpec, LayerRole, VisualBible
from pdz2.engines.imagery.renderer import RenderedImage
from pdz2.execution import ExecutionDispatcher
from pdz2.execution.dispatcher import DispatchRejected
from pdz2.providers import active_providers
from pdz2.renderers import DeterministicRenderer, FfmpegUnavailable, RenderFailed
from pdz2.state import EpisodeStateMachine, TransitionRefused
from pdz2.storage import EpisodeStore


def _palette(bible: VisualBible) -> list[tuple[int, int, int]]:
    """Palette de la bible, en RGB, pour les indicateurs de mouvement.

    Le renderer dessine le mouvement du sujet dans les couleurs décidées par
    la réalisation, comme il écrit les incrustations dans sa typographie. Sans
    ce passage, il retomberait sur une palette de secours et l'épisode aurait
    deux chartes de couleur.
    """
    return [
        tuple(int(couleur.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
        for couleur in bible.color.palette
    ]


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
    # L'aiguilleur, pas le renderer : c'est lui qui décide qui exécute quoi.
    # Les fournisseurs viennent de l'inventaire, qui lit l'environnement :
    # sans clé la liste est vide et tout part en local, avec sa dégradation
    # inscrite ; avec clé le chemin fournisseur est emprunté, sans que le CLI
    # n'ait à savoir lequel.
    fournisseurs = active_providers().video
    dispatcher = ExecutionDispatcher(renderer=renderer, providers=fournisseurs)
    print(
        "fournisseurs vidéo actifs : "
        + (", ".join(f.name for f in fournisseurs) or "aucun, rendu local seul")
    )

    try:
        machine.start(Stage.RENDER, reason=f"{len(executables)} plans")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1

    bible = store.load_as(VisualBible)
    try:
        images = _rebuild_images(store)
        plans = store.load_collection("execution_plan")
        outcome = dispatcher.execute(
            executables=executables,
            motion_programs=store.load_collection("motion_program"),
            images=images,
            into=store.root / RENDERS_DIR,
            plan=plans[0] if plans else None,
            typography=bible.typography,
            palette=_palette(bible),
            animated_shots_max=store.load_as(TopicRequest).animated_shots_max,
        )
    except (RenderFailed, FfmpegUnavailable, DispatchRejected) as failure:
        machine.fail(Stage.RENDER, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"rendu refusé : {failure}", file=sys.stderr)
        return 1

    for artifact in outcome.artifacts:
        store.save(artifact)
    depense = round(sum(a.actual_cost_usd for a in outcome.artifacts), 6)
    machine.complete(
        Stage.RENDER,
        artifact_ids=[a.id for a in outcome.artifacts],
        cost_usd=depense,
        reason=f"{len(outcome.artifacts)} plans rendus",
    )
    store.save_snapshot(machine.snapshot)

    for note in outcome.notes:
        print(note)
    for dispatch in sorted(outcome.dispatches, key=lambda d: d.shot_id):
        artefact = next(
            (a for a in outcome.artifacts if a.shot_id == dispatch.shot_id), None
        )
        taille = f"{artefact.size_bytes // 1024:>5} Kio" if artefact else "    —"
        print(
            f"  {dispatch.shot_id}: {dispatch.strategy.value:<15} "
            f"[{dispatch.executor.value:<8}] {taille}  {dispatch.detail}"
        )
    for ecart in outcome.degradations:
        print(f"  DÉGRADÉ {ecart.field} : {ecart.reason}")
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
