"""Commande de la phase 8 : mesurer ce qui est réellement sorti.

    pdz2 observe  RENDER → OBSERVATION
"""

from __future__ import annotations

import argparse
import sys

from pdz2.contracts.enums import ArtifactKind
from pdz2.contracts.pipeline import Stage
from pdz2.contracts.visual import VisualBible
from pdz2.qa import DeterministicObserver, ObservationFailed
from pdz2.state import EpisodeStateMachine, TransitionRefused
from pdz2.storage import EpisodeStore

__all__ = ["register", "cmd_observe"]

RENDERS_DIR = "renders"


def cmd_observe(args: argparse.Namespace) -> int:
    store = EpisodeStore(args.episode)
    if not store.has_snapshot():
        print(f"aucun épisode dans {args.episode}", file=sys.stderr)
        return 1
    machine = EpisodeStateMachine.resume(store.load_snapshot())
    executables = store.load_collection("render_spec_executable")
    videos = [
        artifact
        for artifact in store.load_collection("render_artifact")
        if artifact.kind is ArtifactKind.VIDEO
    ]
    if not videos:
        print("aucun rendu vidéo — lancer `pdz2 render`", file=sys.stderr)
        return 1

    try:
        machine.start(Stage.OBSERVATION, reason=f"{len(videos)} rendus à mesurer")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1

    try:
        outcome = DeterministicObserver().observe(
            artifacts=sorted(videos, key=lambda a: a.shot_id or ""),
            executables=executables,
            motion_programs=store.load_collection("motion_program"),
            visual_bible=store.load_as(VisualBible),
            renders_dir=store.root / RENDERS_DIR,
        )
    except ObservationFailed as failure:
        machine.fail(Stage.OBSERVATION, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"observation impossible : {failure}", file=sys.stderr)
        return 1

    for report in outcome.reports:
        store.save(report)
    machine.complete(
        Stage.OBSERVATION,
        artifact_ids=[report.id for report in outcome.reports],
        reason=f"{len(outcome.failed)} plan(s) non conforme(s)",
    )
    store.save_snapshot(machine.snapshot)

    for note in outcome.notes:
        print(note)
    print()
    for report in outcome.reports:
        mark = "conforme" if report.passed else "NON CONFORME"
        print(f"  {report.shot_id} : {mark}")
        if args.verbose:
            for measurement in report.measurements:
                print(
                    f"      {measurement.name:<24} {measurement.value:>14.6f} "
                    f"{measurement.unit}"
                )
        for check in report.checks:
            if check.passed and not args.verbose:
                continue
            state = "ok " if check.passed else "NON"
            print(
                f"      [{state} {check.severity.value:<8}] {check.check_id} "
                f"observé {check.observed} attendu {check.expected}"
            )
            if not check.passed and check.detail:
                print(f"            {check.detail}")

    if outcome.failed:
        print(
            f"\n{len(outcome.failed)} plan(s) à diagnostiquer — `pdz2 diagnose`"
        )
    return 0


def register(subparsers) -> None:
    observe = subparsers.add_parser("observe", help="mesurer les rendus")
    observe.add_argument("--episode", required=True)
    observe.add_argument("-v", "--verbose", action="store_true")
    observe.set_defaults(func=cmd_observe)
