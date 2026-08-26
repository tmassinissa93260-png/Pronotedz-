"""Commandes de la phase 4 : mouvement, spécifications, validation.

    pdz2 motion    SHOT_GRAPH → MOTION             source de vérité du mouvement
    pdz2 specs     MOTION     → RENDER_SPEC        images + demandes de rendu
    pdz2 validate  RENDER_SPEC → STATIC_VALIDATION barrière de coût

Tant que `validate` n'a pas accepté, la machine à états refuse de démarrer les
étapes payantes : c'est le graphe qui le garantit, pas ce fichier.
"""

from __future__ import annotations

import argparse
import sys

from pdz2.contracts.direction import DirectorState
from pdz2.contracts.pipeline import Stage
from pdz2.contracts.research import TopicRequest
from pdz2.contracts.shots import ShotGraph
from pdz2.contracts.temporal import TemporalPlan
from pdz2.contracts.visual import VisualBible
from pdz2.engines.imagery import ImageSpecCompiler
from pdz2.engines.motion import MotionCompiler, MotionRejected
from pdz2.engines.renderspec import RenderSpecCompiler, RenderSpecRejected
from pdz2.engines.validation import StaticValidator
from pdz2.providers import active_providers
from pdz2.state import EpisodeStateMachine, TransitionRefused
from pdz2.storage import EpisodeStore

__all__ = ["register", "cmd_motion", "cmd_specs", "cmd_validate"]


def _open(episode: str):
    store = EpisodeStore(episode)
    if not store.has_snapshot():
        print(f"aucun épisode dans {episode}", file=sys.stderr)
        return None
    return store, EpisodeStateMachine.resume(store.load_snapshot())


def _need(store, names: dict[str, str]) -> bool:
    for name, command in names.items():
        if not store.exists(name):
            print(f"pas de {name} — lancer `{command}` d'abord", file=sys.stderr)
            return False
    return True


def cmd_motion(args: argparse.Namespace) -> int:
    opened = _open(args.episode)
    if opened is None:
        return 1
    store, machine = opened
    if not _need(store, {"shot_graph": "pdz2 shots"}):
        return 1

    graph = store.load_as(ShotGraph)
    plan = store.load_as(TemporalPlan)
    cameras = [c for c in store.load_collection("camera_program")]
    try:
        machine.start(Stage.MOTION, reason=f"{len(graph.shots)} plans")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1
    try:
        outcome = MotionCompiler().compile(
            shot_graph=graph,
            temporal_plan=plan,
            camera_programs=cameras,
            director_state=store.load_as(DirectorState),
            visual_bible=store.load_as(VisualBible),
        )
    except MotionRejected as failure:
        machine.fail(Stage.MOTION, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"mouvement refusé : {failure}", file=sys.stderr)
        return 1

    for program in outcome.programs:
        store.save(program)
    machine.complete(Stage.MOTION, artifact_ids=[p.id for p in outcome.programs])
    store.save_snapshot(machine.snapshot)
    for note in outcome.notes:
        print(note)
    for program in outcome.programs:
        target = program.perceptual_target
        print(
            f"  {program.shot_id} intensité {program.intensity:.2f} "
            f"| énergie {target.motion_energy:.2f} nouveauté {target.visual_novelty:.2f} "
            f"lisibilité {target.readability:.2f} | préserve {len(program.must_preserve)}"
        )
    return 0


def cmd_specs(args: argparse.Namespace) -> int:
    opened = _open(args.episode)
    if opened is None:
        return 1
    store, machine = opened
    if not _need(store, {"shot_graph": "pdz2 shots", "visual_bible": "pdz2 bible"}):
        return 1

    graph = store.load_as(ShotGraph)
    motions = store.load_collection("motion_program")
    if not motions:
        print("pas de programmes de mouvement — lancer `pdz2 motion`", file=sys.stderr)
        return 1
    try:
        machine.start(Stage.RENDER_SPEC, reason=f"{len(graph.shots)} plans")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1

    request = store.load_as(TopicRequest)
    try:
        images = ImageSpecCompiler(
            separable_layers=_calques_separables()
        ).compile(
            shot_graph=graph,
            visual_bible=store.load_as(VisualBible),
            director_state=store.load_as(DirectorState),
            request=request,
        )
        specs = RenderSpecCompiler(fps=args.fps).compile(
            shot_graph=graph,
            motion_programs=motions,
            camera_programs=store.load_collection("camera_program"),
            image_specs=images.specs,
            request=request,
        )
    except RenderSpecRejected as failure:
        machine.fail(Stage.RENDER_SPEC, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"spécifications refusées : {failure}", file=sys.stderr)
        return 1

    for spec in images.specs:
        store.save(spec)
    for spec in specs.specs:
        store.save(spec)
    machine.complete(
        Stage.RENDER_SPEC,
        artifact_ids=[s.id for s in images.specs] + [s.id for s in specs.specs],
    )
    store.save_snapshot(machine.snapshot)
    for note in images.notes + specs.notes:
        print(note)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    opened = _open(args.episode)
    if opened is None:
        return 1
    store, machine = opened
    requested = [
        s for s in store.load_collection("render_spec_requested")
    ]
    if not requested:
        print("pas de demandes de rendu — lancer `pdz2 specs`", file=sys.stderr)
        return 1
    try:
        machine.start(Stage.STATIC_VALIDATION, reason=f"{len(requested)} demandes")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1

    outcome = StaticValidator().validate(
        episode_id=store.root.name,
        shot_graph=store.load_as(ShotGraph),
        requested=requested,
        motion_programs=store.load_collection("motion_program"),
        camera_programs=store.load_collection("camera_program"),
        image_specs=[
            s for s in store.load_collection("image_spec")
        ],
        request=store.load_as(TopicRequest),
    )
    store.save(outcome.report)
    for note in outcome.notes:
        print(note)
    for issue in outcome.report.issues:
        print(f"  [{issue.severity.value:<8} {issue.rule.value:<22}] "
              f"{issue.subject_id}: {issue.detail}")
        if issue.remedy:
            print(f"           → {issue.remedy}")

    if not outcome.report.accepted:
        machine.fail(
            Stage.STATIC_VALIDATION,
            reason=(
                f"{len(outcome.report.blocking)} blocage(s) : "
                + ", ".join(sorted({i.rule.value for i in outcome.report.blocking}))
            ),
        )
        store.save_snapshot(machine.snapshot)
        print("\nREFUSÉ — aucune dépense autorisée.", file=sys.stderr)
        return 1

    machine.complete(Stage.STATIC_VALIDATION, artifact_ids=[outcome.report.id])
    store.save_snapshot(machine.snapshot)
    print("\nACCEPTÉ — la barrière de coût est levée.")
    return 0


def _calques_separables() -> bool:
    """Le moteur d'images qui rendra ces plans sait-il la transparence ?

    On interroge le fournisseur prioritaire, celui que le répartiteur prendra
    en premier. Le repli local sait toujours composer ; c'est le moteur
    distant qui ne sait pas, et c'est donc lui qui décide du nombre de calques
    qu'il est honnête de demander.

    Un adaptateur muet sur la question est traité comme incapable : mieux vaut
    demander un calque de trop peu qu'en payer trois qui seront écrasés.
    """
    moteurs = active_providers().image
    if not moteurs:
        return True
    return bool(getattr(moteurs[0], "supports_alpha_layers", False))


def register(subparsers) -> None:
    motion = subparsers.add_parser("motion", help="compiler les programmes de mouvement")
    motion.add_argument("--episode", required=True)
    motion.set_defaults(func=cmd_motion)

    specs = subparsers.add_parser("specs", help="compiler images et demandes de rendu")
    specs.add_argument("--episode", required=True)
    specs.add_argument("--fps", type=int, default=30)
    specs.set_defaults(func=cmd_specs)

    validate = subparsers.add_parser(
        "validate", help="valider avant toute dépense"
    )
    validate.add_argument("--episode", required=True)
    validate.set_defaults(func=cmd_validate)
