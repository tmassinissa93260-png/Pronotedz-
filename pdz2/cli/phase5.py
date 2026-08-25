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
from pdz2.engines.imagery import ImageRenderFailed
from pdz2.providers import active_providers
from pdz2.providers.image import ImageProviderUnavailable
from pdz2.providers.video import ProviderUnavailable
from pdz2.state import EpisodeStateMachine, TransitionRefused
from pdz2.storage import EpisodeStore

__all__ = ["register", "cmd_assets", "render_with_fallback"]

ASSETS_DIR = "assets"

_RENDER_REFUSALS = (ImageProviderUnavailable, ProviderUnavailable, ImageRenderFailed)
"""Ce qui écarte un moteur d'images sans arrêter la production.

Trois exceptions de trois couches — le port, le transport, le moteur local —
et la même conséquence : on passe au suivant. Toute autre exception remonte :
un bogue ne doit pas se déguiser en dégradation.
"""


def render_with_fallback(providers, *, specs, visual_bible, into):
    """Essaie chaque moteur dans l'ordre ; le dernier est le repli local.

    Rend le résultat **et le nom du moteur qui l'a produit**, plus la liste
    des refus rencontrés. Un repli silencieux serait une dégradation cachée :
    l'appelant doit pouvoir l'inscrire au journal.
    """
    refus: list[str] = []
    for provider in providers:
        try:
            outcome = provider.render(specs=specs, visual_bible=visual_bible, into=into)
        except _RENDER_REFUSALS as ecart:
            refus.append(f"{provider.name} écarté : {ecart}")
            continue
        return outcome, provider.name, refus
    raise ImageRenderFailed(
        "aucun moteur d'images n'a rendu — " + " | ".join(refus or ["aucun moteur actif"])
    )


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

    moteurs = active_providers().image
    try:
        outcome, moteur, refus = render_with_fallback(
            moteurs,
            specs=specs,
            visual_bible=store.load_as(VisualBible),
            into=store.root / ASSETS_DIR,
        )
    except ImageRenderFailed as failure:
        machine.fail(Stage.ASSETS, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"génération refusée : {failure}", file=sys.stderr)
        return 1

    distant = moteur != "procedural-image"
    for artifact in outcome.artifacts:
        store.save(artifact)
    machine.complete(
        Stage.ASSETS,
        artifact_ids=[artifact.id for artifact in outcome.artifacts],
        cost_usd=0.0,
        reason=(
            f"{len(outcome.images)} images par {moteur}"
            + (" — montant réel non relevé, hors registre" if distant else " (local)")
            + ("".join(f" | {ligne}" for ligne in refus))
        ),
    )
    store.save_snapshot(machine.snapshot)

    for ligne in refus:
        print(ligne)
    for note in outcome.notes:
        print(note)
    if distant:
        print(
            f"\nATTENTION : {moteur} est un service facturé. Le registre de "
            "dépenses inscrit 0 parce que ce montant n'a pas été relevé — "
            "c'est une lacune déclarée, pas une gratuité."
        )
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
