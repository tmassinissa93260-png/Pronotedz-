"""Commandes de la phase 3 : bible visuelle et découpage.

    pdz2 bible  DIRECTION → VISUAL_BIBLE   registre visuel, sans fournisseur
    pdz2 shots  TIMELINE  → SHOT_GRAPH     découpage du temps mesuré en plans

`shots` refuse de démarrer tant que la timeline mesurée n'existe pas : c'est
le graphe d'étapes qui le garantit, pas ce fichier.
"""

from __future__ import annotations

import argparse
import sys

from pdz2.contracts.direction import DirectorBrief, DirectorState
from pdz2.contracts.pipeline import Stage
from pdz2.contracts.research import ResearchState, TopicRequest
from pdz2.contracts.script import ScriptState, VoiceTimeline
from pdz2.contracts.visual import VisualBible
from pdz2.engines.shots import ShotGraphCompiler, ShotGraphRejected
from pdz2.engines.temporal import TemporalDirector, TemporalRejected
from pdz2.engines.visual import VisualBibleCompiler, VisualBibleRejected
from pdz2.state import EpisodeStateMachine, TransitionRefused
from pdz2.storage import EpisodeStore

__all__ = ["register", "cmd_bible", "cmd_shots"]


def _open(episode: str):
    store = EpisodeStore(episode)
    if not store.has_snapshot():
        print(f"aucun épisode dans {episode}", file=sys.stderr)
        return None
    return store, EpisodeStateMachine.resume(store.load_snapshot())


def cmd_bible(args: argparse.Namespace) -> int:
    opened = _open(args.episode)
    if opened is None:
        return 1
    store, machine = opened
    if not store.exists("director_state") or not store.exists("director_brief"):
        print("pas de réalisation — lancer `pdz2 direct` d'abord", file=sys.stderr)
        return 1

    director_state = store.load_as(DirectorState)
    brief = store.load_as(DirectorBrief)
    try:
        machine.start(Stage.VISUAL_BIBLE, reason=f"registre {director_state.tone.value}")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1

    try:
        outcome = VisualBibleCompiler().compile(
            director_state=director_state, brief=brief
        )
    except VisualBibleRejected as failure:
        machine.fail(Stage.VISUAL_BIBLE, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"bible refusée : {failure}", file=sys.stderr)
        return 1

    store.save(outcome.bible)
    machine.complete(Stage.VISUAL_BIBLE, artifact_ids=[outcome.bible.id])
    store.save_snapshot(machine.snapshot)

    bible = outcome.bible
    for note in outcome.notes:
        print(note)
    print()
    print(f"  style           {bible.style}")
    print(f"  lumière         {bible.lighting}")
    print(f"  palette         {' '.join(bible.color.palette)}")
    print(f"  contraste/satur {bible.color.contrast} / {bible.color.saturation}")
    print(f"  caméra          {bible.camera_language}")
    print(f"  optique         {bible.lens_language}")
    print(f"  profondeur      {bible.depth_of_field}")
    print(f"  matières        {', '.join(bible.materials)}")
    print(f"  texture         {bible.texture}")
    print(f"  décor           {bible.environment}")
    print(f"  graphisme       {bible.graphics}")
    print(f"  typographie     {bible.typography.family}, {bible.typography.max_chars_per_line} car./ligne")
    print(f"  densité         {bible.visual_density}")
    if bible.forbidden:
        print(f"  interdits       {', '.join(bible.forbidden)}")
    print(f"\nécrit : {store.path_for('visual_bible')}")
    return 0


def cmd_shots(args: argparse.Namespace) -> int:
    opened = _open(args.episode)
    if opened is None:
        return 1
    store, machine = opened
    for name, command in (
        ("voice_timeline", "pdz2 timeline"),
        ("visual_bible", "pdz2 bible"),
        ("script_state", "pdz2 script"),
    ):
        if not store.exists(name):
            print(f"pas de {name} — lancer `{command}` d'abord", file=sys.stderr)
            return 1

    director_state = store.load_as(DirectorState)
    script = store.load_as(ScriptState)
    timeline = store.load_as(VoiceTimeline)
    bible = store.load_as(VisualBible)
    research = store.load_as(ResearchState)
    request = store.load_as(TopicRequest)

    try:
        machine.start(Stage.SHOT_GRAPH, reason=f"découpage de {timeline.total_duration_s:.2f}s mesurées")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1

    try:
        temporal = TemporalDirector().plan(
            director_state=director_state, script=script, timeline=timeline
        )
        shots = ShotGraphCompiler().compile(
            director_state=director_state,
            temporal_plan=temporal.plan,
            visual_bible=bible,
            script=script,
            research=research,
            request=request,
        )
    except (TemporalRejected, ShotGraphRejected) as failure:
        machine.fail(Stage.SHOT_GRAPH, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"découpage refusé : {failure}", file=sys.stderr)
        return 1

    store.save(temporal.plan)
    for program in shots.camera_programs:
        store.save(program)
    store.save(shots.graph)
    machine.complete(
        Stage.SHOT_GRAPH,
        artifact_ids=[temporal.plan.id, shots.graph.id]
        + [program.id for program in shots.camera_programs],
    )
    store.save_snapshot(machine.snapshot)

    for note in temporal.notes + shots.notes:
        print(note)
    print()
    for shot in shots.graph.shots:
        slot = temporal.plan.slot(shot.shot_id)
        targets = temporal.plan.targets_for(shot.shot_id)
        camera = shots.camera_for_shot(shot.shot_id)
        print(
            f"  {shot.shot_id} {slot.start_s:>6.2f}→{slot.end_s:>6.2f}s "
            f"[{shot.narrative_function.value:<11}] "
            f"{shot.composition.framing.value:<17} {camera.move.value:<9} "
            f"mv {targets['motion']:.2f} nv {targets['visual_novelty']:.2f} "
            f"at {targets['attention']:.2f} in {targets['information']:.2f}"
        )
        print(f"       {shot.visual_subject[:88]}")
        if shot.text_overlay:
            print(f"       incrustation « {shot.text_overlay.text} »")
    if temporal.plan.findings:
        print("\nconstats de rythme :")
        for finding in temporal.plan.findings:
            where = f"{finding.shot_id} : " if finding.shot_id else ""
            print(f"  [{finding.kind.value}] {where}{finding.detail}")
    print(f"\nécrit : {store.path_for('shot_graph')}")
    return 0


def register(subparsers) -> None:
    bible = subparsers.add_parser("bible", help="compiler la bible visuelle")
    bible.add_argument("--episode", required=True)
    bible.set_defaults(func=cmd_bible)

    shots = subparsers.add_parser(
        "shots", help="découper le temps mesuré en plans motivés"
    )
    shots.add_argument("--episode", required=True)
    shots.set_defaults(func=cmd_shots)
