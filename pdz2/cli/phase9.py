"""Commandes de la phase 9 : diagnostiquer et réparer.

    pdz2 diagnose  OBSERVATION → DIAGNOSIS
    pdz2 repair    DIAGNOSIS   → REPAIR  (et rembobine ce qu'il faut refaire)

`diagnose` se saute explicitement quand tout est conforme : sauter une étape
est une décision écrite au journal, pas un oubli.
"""

from __future__ import annotations

import argparse
import json
import sys

from pdz2.contracts.pipeline import Stage
from pdz2.repair import FailureDiagnoser, RepairCompiler, RepairRejected
from pdz2.state import EpisodeStateMachine, TransitionRefused
from pdz2.storage import EpisodeStore

__all__ = ["register", "cmd_diagnose", "cmd_repair"]

FORBIDDEN_FILE = "repairs/forbidden_strategies.json"


def _open(episode: str):
    store = EpisodeStore(episode)
    if not store.has_snapshot():
        print(f"aucun épisode dans {episode}", file=sys.stderr)
        return None
    return store, EpisodeStateMachine.resume(store.load_snapshot())


def cmd_diagnose(args: argparse.Namespace) -> int:
    opened = _open(args.episode)
    if opened is None:
        return 1
    store, machine = opened
    reports = store.load_collection("observation_report")
    if not reports:
        print("aucune observation — lancer `pdz2 observe`", file=sys.stderr)
        return 1

    failed = [report for report in reports if not report.passed]
    if not failed:
        try:
            machine.skip(
                Stage.DIAGNOSIS,
                reason=f"{len(reports)} plans conformes, rien à diagnostiquer",
            )
            machine.skip(Stage.REPAIR, reason="aucun diagnostic à réparer")
        except TransitionRefused as refusal:
            print(f"étape refusée : {refusal}", file=sys.stderr)
            return 1
        store.save_snapshot(machine.snapshot)
        print(f"{len(reports)} plans conformes — diagnostic et réparation sautés")
        return 0

    try:
        machine.start(Stage.DIAGNOSIS, reason=f"{len(failed)} plans non conformes")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1

    outcome = FailureDiagnoser().diagnose(
        reports=reports,
        executables=store.load_collection("render_spec_executable"),
    )
    for diagnosis in outcome.diagnoses:
        store.save(diagnosis)
    machine.complete(
        Stage.DIAGNOSIS, artifact_ids=[d.id for d in outcome.diagnoses]
    )
    store.save_snapshot(machine.snapshot)

    for note in outcome.notes:
        print(note)
    for diagnosis in outcome.diagnoses:
        print(f"\n  {diagnosis.shot_id} — cause racine « {diagnosis.root_cause.value} »")
        print(f"      {diagnosis.explanation}")
        for finding in diagnosis.findings:
            print(
                f"      [{finding.severity.value:<8} conf {finding.confidence:.2f}] "
                f"{finding.kind.value}"
            )
            print(f"          {finding.explanation}")
            print(f"          mesures : {', '.join(finding.evidence_measurements)}")
    return 0


def cmd_repair(args: argparse.Namespace) -> int:
    opened = _open(args.episode)
    if opened is None:
        return 1
    store, machine = opened
    diagnoses = store.load_collection("failure_diagnosis")
    if not diagnoses:
        print("aucun diagnostic — lancer `pdz2 diagnose`", file=sys.stderr)
        return 1

    try:
        machine.start(Stage.REPAIR, reason=f"{len(diagnoses)} plans à réparer")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1

    snapshot = machine.snapshot
    cycle = snapshot.repair_cycles + 1
    previous = _load_forbidden(store)
    try:
        outcome = RepairCompiler(max_cycles=snapshot.max_repair_cycles).compile(
            diagnoses=diagnoses,
            executables=store.load_collection("render_spec_executable"),
            cycle=cycle,
            already_forbidden=previous,
        )
    except RepairRejected as failure:
        machine.fail(Stage.REPAIR, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"réparation refusée : {failure}", file=sys.stderr)
        return 1

    for plan in outcome.plans:
        store.save(plan)
    _save_forbidden(store, outcome.forbidden_strategies)
    machine.complete(Stage.REPAIR, artifact_ids=[p.id for p in outcome.plans])

    for note in outcome.notes:
        print(note)
    for plan in outcome.plans:
        print(f"\n  {plan.shot_id} — cycle {plan.cycle}/{plan.max_cycles}")
        for step in plan.steps:
            print(f"      {step.action.value} → rembobine « {step.target_stage.value} »")
            print(f"          {step.rationale}")
        print(f"      repli garanti : {plan.guaranteed_fallback.value}")

    if args.apply:
        earliest = _earliest_stage(outcome.rewind_stages)
        rewound = machine.rewind(
            earliest,
            reason=(
                f"réparation cycle {cycle} : "
                + ", ".join(sorted({s.action.value for p in outcome.plans for s in p.steps}))
            ),
        )
        print(
            f"\nrembobiné depuis « {earliest.value} » : "
            + ", ".join(stage.value for stage in rewound)
        )
    else:
        print("\n(--apply pour rembobiner les étapes concernées)")
    store.save_snapshot(machine.snapshot)
    return 0


def _earliest_stage(stages) -> Stage:
    """L'étape la plus en amont : refaire depuis là suffit pour tout refaire."""
    from pdz2.state.stages import STAGE_ORDER

    order = {stage: index for index, stage in enumerate(STAGE_ORDER)}
    return min(stages, key=lambda stage: order[stage])


def _load_forbidden(store: EpisodeStore) -> dict[str, set]:
    from pdz2.contracts.render import RenderStrategy

    path = store.root / FORBIDDEN_FILE
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        shot: {RenderStrategy(value) for value in values}
        for shot, values in payload.items()
    }


def _save_forbidden(store: EpisodeStore, forbidden: dict[str, set]) -> None:
    path = store.root / FORBIDDEN_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {shot: sorted(s.value for s in values) for shot, values in forbidden.items()},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def register(subparsers) -> None:
    diagnose = subparsers.add_parser("diagnose", help="expliquer les échecs mesurés")
    diagnose.add_argument("--episode", required=True)
    diagnose.set_defaults(func=cmd_diagnose)

    repair = subparsers.add_parser("repair", help="composer un plan de réparation")
    repair.add_argument("--episode", required=True)
    repair.add_argument(
        "--apply",
        action="store_true",
        help="rembobiner les étapes concernées pour refaire ce qu'il faut",
    )
    repair.set_defaults(func=cmd_repair)
