"""Commande de la phase 5 : générer les images de départ.

    pdz2 assets  STATIC_VALIDATION → ASSETS

L'étape est barrée par le validateur : sans rapport accepté, elle ne démarre
pas. C'est la barrière de coût, appliquée par le graphe d'étapes.
"""

from __future__ import annotations

import argparse
import sys

from pdz2.contracts.pipeline import Stage
from pdz2.contracts.visual import ImageSpec, VisualBible
from pdz2.engines.imagery import ImageRenderFailed, ProceduralImageRenderer
from pdz2.state import EpisodeStateMachine, TransitionRefused
from pdz2.storage import EpisodeStore

__all__ = ["register", "cmd_assets"]

ASSETS_DIR = "assets"


def cmd_assets(args: argparse.Namespace) -> int:
    store = EpisodeStore(args.episode)
    if not store.has_snapshot():
        print(f"aucun épisode dans {args.episode}", file=sys.stderr)
        return 1
    machine = EpisodeStateMachine.resume(store.load_snapshot())
    specs: list[ImageSpec] = sorted(
        store.load_collection("image_spec"), key=lambda spec: spec.shot_id
    )
    if not specs:
        print("pas de spécifications d'image — lancer `pdz2 specs`", file=sys.stderr)
        return 1

    try:
        machine.start(Stage.ASSETS, reason=f"{len(specs)} images")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1

    try:
        outcome = ProceduralImageRenderer().render(
            specs=specs,
            visual_bible=store.load_as(VisualBible),
            into=store.root / ASSETS_DIR,
        )
    except ImageRenderFailed as failure:
        machine.fail(Stage.ASSETS, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"génération refusée : {failure}", file=sys.stderr)
        return 1

    for artifact in outcome.artifacts:
        store.save(artifact)
    machine.complete(
        Stage.ASSETS,
        artifact_ids=[artifact.id for artifact in outcome.artifacts],
        cost_usd=0.0,
        reason=f"{len(outcome.images)} images composées localement",
    )
    store.save_snapshot(machine.snapshot)

    for note in outcome.notes:
        print(note)
    for image in outcome.images:
        print(
            f"  {image.shot_id}: {image.layer_count} calques, "
            f"{image.composite_path.stat().st_size // 1024} Kio, graine {image.seed}"
        )
    print(f"\nécrit : {store.root / ASSETS_DIR}")
    return 0


def register(subparsers) -> None:
    assets = subparsers.add_parser("assets", help="générer les images de départ")
    assets.add_argument("--episode", required=True)
    assets.set_defaults(func=cmd_assets)
