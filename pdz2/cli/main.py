"""Ligne de commande PDZ 2.

Phase 0 : inspecter les contrats, exporter les schémas, lire le graphe
d'étapes, et lire l'état d'un épisode existant. La commande `create` sera
branchée quand les phases 1 à 12 seront réellement implémentées — elle
refuse aujourd'hui plutôt que de simuler une production.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pdz2.contracts  # noqa: F401  (enregistre les contrats dans le registre)
from pdz2 import __version__
from pdz2.contracts.pipeline import Stage, StageStatus
from pdz2.contracts.versioning import registry
from pdz2.schemas import SCHEMA_DIR, check_up_to_date, export_all, schema_for
from pdz2.state.stages import STAGE_ORDER, definition
from pdz2.storage import EpisodeStore

IMPLEMENTED_PHASES = (
    "Phase 0 — contrats, versionnage, machine à états",
    "Phase 1 — research + fact graph + director state "
    "(corpus local ; aucun raisonneur branché, le brief est rédigé)",
    "Phase 2 — script + TTS réel + timing "
    "(eSpeak NG hors-ligne ; durées mesurées sur l'audio, pas estimées)",
    "Phase 3 — shot graph + visual bible "
    "(découpage du temps mesuré ; aucun fournisseur nommé)",
    "Phase 4 — render spec + static validator "
    "(douze règles nommées ; barrière de coût effective)",
    "Phase 5 — image engine "
    "(moteur schématique déterministe, calqué ; aucun fournisseur joignable)",
    "Phase 6 — motion program + port fournisseur vidéo + routeur de stratégie "
    "(aucun adaptateur vidéo implémenté : chaque dégradation est enregistrée)",
    "Phase 7 — 2.5D + procédural "
    "(vraies vidéos H.264 par ffmpeg, sans aucun fournisseur)",
    "Phase 8 — observateur déterministe "
    "(mesures sur les pixels réels ; aucun jugement esthétique)",
    "Phase 9 — diagnostic + repair compiler "
    "(causes adossées aux mesures, boucle bornée, repli garanti)",
)
PENDING_PHASES = (
    "Phase 10 — montage + mastering audio",
    "Phase 11 — capability matrix + cost governor",
    "Phase 12 — production journal",
)


def _cmd_contracts_list(args: argparse.Namespace) -> int:
    for contract_type in registry.types():
        print(f"{contract_type.CONTRACT_NAME:<26} {contract_type.CONTRACT_VERSION:<8} "
              f"{contract_type.__module__}.{contract_type.__name__}")
    print(f"\n{len(registry.names())} contrats enregistrés.")
    return 0


def _cmd_contracts_schema(args: argparse.Namespace) -> int:
    try:
        contract_type = registry.get(args.name)
    except LookupError as error:
        print(str(error), file=sys.stderr)
        return 1
    json.dump(schema_for(contract_type), sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    print()
    return 0


def _cmd_schemas_export(args: argparse.Namespace) -> int:
    directory = Path(args.out) if args.out else SCHEMA_DIR
    written = export_all(directory)
    print(f"{len(written)} schémas écrits dans {directory}")
    return 0


def _cmd_schemas_check(args: argparse.Namespace) -> int:
    problems = check_up_to_date()
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print("\nRelancer : pdz2 schemas export", file=sys.stderr)
        return 1
    print("schémas à jour")
    return 0


def _cmd_state_graph(args: argparse.Namespace) -> int:
    for stage in STAGE_ORDER:
        spec = definition(stage)
        flags = []
        if spec.incurs_cost:
            flags.append("coût")
        if spec.gated_by_validation:
            flags.append("barré-validation")
        if spec.optional:
            flags.append("sautable")
        depends = ", ".join(dep.value for dep in spec.depends_on) or "—"
        suffix = f"  [{' '.join(flags)}]" if flags else ""
        print(f"{stage.value:<18} ← {depends}{suffix}")
        if args.verbose and spec.description:
            print(f"{'':<18}   {spec.description}")
    return 0


def _cmd_state_show(args: argparse.Namespace) -> int:
    store = EpisodeStore(args.episode)
    if not store.has_snapshot():
        print(f"aucun état dans {args.episode}", file=sys.stderr)
        return 1
    snapshot = store.load_snapshot()
    print(f"épisode  : {snapshot.episode_id}")
    print(f"statut   : {snapshot.episode_status.value}")
    print(f"dépensé  : {snapshot.spent_usd:.4f} USD")
    print(f"réparations : {snapshot.repair_cycles}/{snapshot.max_repair_cycles}")
    print()
    marks = {
        StageStatus.PENDING: ".",
        StageStatus.RUNNING: ">",
        StageStatus.DONE: "x",
        StageStatus.FAILED: "!",
        StageStatus.SKIPPED: "-",
    }
    for stage in Stage:
        state = snapshot.state(stage)
        detail = f"  {state.detail}" if state.detail else ""
        print(f"[{marks[state.status]}] {stage.value:<18} {state.status.value}{detail}")
    return 0


def _cmd_phases(args: argparse.Namespace) -> int:
    print("Implémenté :")
    for line in IMPLEMENTED_PHASES:
        print(f"  [x] {line}")
    print("\nÀ faire :")
    for line in PENDING_PHASES:
        print(f"  [ ] {line}")
    return 0


def _cmd_create(args: argparse.Namespace) -> int:
    print(
        "PDZ 2 ne sait pas encore produire d'épisode de bout en bout : les "
        "phases 0 à 3 sont implémentées (contrats, machine à états, recherche, "
        "Director Core, script, voix mesurée, découpage et bible visuelle).\n"
        "Chaîne disponible aujourd'hui :\n"
        "  pdz2 research       --episode DIR --topic \"...\" --corpus DIR\n"
        "  pdz2 brief-template --episode DIR --out brief.json\n"
        "  pdz2 direct         --episode DIR --brief brief.json\n"
        "  pdz2 script         --episode DIR\n"
        "  pdz2 voice          --episode DIR\n"
        "  pdz2 timeline       --episode DIR\n"
        "  pdz2 bible          --episode DIR\n"
        "  pdz2 shots          --episode DIR\n"
        "  pdz2 motion         --episode DIR\n"
        "  pdz2 specs          --episode DIR\n"
        "  pdz2 validate       --episode DIR\n"
        "  pdz2 route          --episode DIR\n"
        "  pdz2 assets         --episode DIR\n"
        "  pdz2 render         --episode DIR\n"
        "  pdz2 observe        --episode DIR\n"
        "  pdz2 diagnose       --episode DIR\n"
        "  pdz2 repair         --episode DIR [--apply]\n"
        "Voir `pdz2 phases` pour l'état réel du chantier.",
        file=sys.stderr,
    )
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdz2",
        description="PDZ 2 — compilateur audiovisuel.",
    )
    parser.add_argument("--version", action="version", version=f"pdz2 {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    contracts = subparsers.add_parser("contracts", help="inspecter les contrats")
    contracts_sub = contracts.add_subparsers(dest="subcommand", required=True)
    contracts_sub.add_parser("list", help="lister les contrats enregistrés").set_defaults(
        func=_cmd_contracts_list
    )
    schema = contracts_sub.add_parser("schema", help="afficher le schéma d'un contrat")
    schema.add_argument("name")
    schema.set_defaults(func=_cmd_contracts_schema)

    schemas = subparsers.add_parser("schemas", help="schémas JSON")
    schemas_sub = schemas.add_subparsers(dest="subcommand", required=True)
    export = schemas_sub.add_parser("export", help="régénérer les schémas")
    export.add_argument("--out", default=None)
    export.set_defaults(func=_cmd_schemas_export)
    schemas_sub.add_parser("check", help="vérifier que les schémas sont à jour").set_defaults(
        func=_cmd_schemas_check
    )

    state = subparsers.add_parser("state", help="machine à états")
    state_sub = state.add_subparsers(dest="subcommand", required=True)
    graph = state_sub.add_parser("graph", help="afficher le graphe d'étapes")
    graph.add_argument("-v", "--verbose", action="store_true")
    graph.set_defaults(func=_cmd_state_graph)
    show = state_sub.add_parser("show", help="afficher l'état d'un épisode")
    show.add_argument("episode", help="dossier de l'épisode")
    show.set_defaults(func=_cmd_state_show)

    from pdz2.cli import phase1, phase2, phase3, phase4, phase5, phase6, phase7, phase8, phase9

    phase1.register(subparsers)
    phase2.register(subparsers)
    phase3.register(subparsers)
    phase4.register(subparsers)
    phase5.register(subparsers)
    phase6.register(subparsers)
    phase7.register(subparsers)
    phase8.register(subparsers)
    phase9.register(subparsers)

    subparsers.add_parser("phases", help="état réel du chantier").set_defaults(func=_cmd_phases)

    create = subparsers.add_parser("create", help="produire un épisode (pas encore disponible)")
    create.add_argument("--topic", required=True)
    create.add_argument("--duration", type=float, default=45.0)
    create.add_argument("--format", default="9:16")
    create.set_defaults(func=_cmd_create)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
