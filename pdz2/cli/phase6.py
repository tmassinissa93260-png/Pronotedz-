"""Commande de la phase 6 : choisir une stratégie par plan.

    pdz2 route  STATIC_VALIDATION → ROUTING

Le routeur produit les spécifications exécutables et le plan d'exécution.
Chaque écart avec la demande y est enregistré : le contrat refuse d'être
construit autrement.
"""

from __future__ import annotations

import argparse
import sys

from pdz2.contracts.pipeline import Stage
from pdz2.contracts.research import TopicRequest
from pdz2.engines.routing import RenderRouter, RoutingRejected
from pdz2.providers import active_providers
from pdz2.state import EpisodeStateMachine, TransitionRefused
from pdz2.storage import EpisodeStore

__all__ = ["register", "cmd_route"]


def cmd_route(args: argparse.Namespace) -> int:
    store = EpisodeStore(args.episode)
    if not store.has_snapshot():
        print(f"aucun épisode dans {args.episode}", file=sys.stderr)
        return 1
    machine = EpisodeStateMachine.resume(store.load_snapshot())
    requested = sorted(
        store.load_collection("render_spec_requested"), key=lambda s: s.shot_id
    )
    if not requested:
        print("pas de demandes de rendu — lancer `pdz2 specs`", file=sys.stderr)
        return 1

    try:
        machine.start(Stage.ROUTING, reason=f"{len(requested)} plans à router")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1

    request = store.load_as(TopicRequest)
    # L'aiguilleur ne connaît que des capacités, jamais des marques. Sans
    # fournisseur actif la liste est vide, et l'échelle de stratégies
    # s'arrête d'elle-même aux stratégies déterministes locales.
    fournisseurs = active_providers().video
    capacites = [fournisseur.get_capabilities() for fournisseur in fournisseurs]
    for capacite in capacites:
        declaree = capacite.capability
        print(
            f"fournisseur vidéo {declaree.provider} : {declaree.state.value} — "
            f"{declaree.detail}"
        )
    try:
        outcome = RenderRouter(
            video_capabilities=capacites,
            capability_matrix=store.latest("capability_matrix"),
        ).route(
            episode_id=store.root.name,
            requested=requested,
            motion_programs=store.load_collection("motion_program"),
            image_specs=store.load_collection("image_spec"),
            budget_cap_usd=request.budget_cap_usd,
        )
    except RoutingRejected as failure:
        machine.fail(Stage.ROUTING, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"routage refusé : {failure}", file=sys.stderr)
        return 1

    for executable in outcome.executables:
        store.save(executable)
    store.save(outcome.plan)
    machine.complete(
        Stage.ROUTING,
        artifact_ids=[e.id for e in outcome.executables] + [outcome.plan.id],
    )
    store.save_snapshot(machine.snapshot)

    for note in outcome.notes:
        print(note)
    print()
    for executable in outcome.executables:
        print(
            f"  {executable.shot_id}: {executable.strategy.value:<15} "
            f"caméra {executable.requested.camera.value} → "
            f"{executable.execution_camera.value}"
        )
        for degradation in executable.degradations:
            print(
                f"      [{degradation.severity.value:<10} {degradation.field}] "
                f"{degradation.requested} → {degradation.executed}"
            )
            print(f"          {degradation.reason}")
    return 0


def register(subparsers) -> None:
    route = subparsers.add_parser(
        "route", help="choisir une stratégie de rendu par plan"
    )
    route.add_argument("--episode", required=True)
    route.set_defaults(func=cmd_route)
