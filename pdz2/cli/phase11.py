"""Commandes de la phase 11 : capacités mesurées, dépenses gouvernées.

    pdz2 capabilities  sonde l'environnement et écrit la matrice datée
    pdz2 costs         relit le registre de dépenses et autorise, ou refuse

Rien ici n'est déclaratif. `capabilities` fait tourner les outils, `costs` ne
compte que des dépenses réellement enregistrées par la machine à états — il
n'ouvre pas une seconde comptabilité à côté de la première.
"""

from __future__ import annotations

import argparse
import sys

from pdz2.contracts.capacity import (
    CapabilityMatrix,
    CostLedger,
    Provenance,
    SpendRecord,
)
from pdz2.contracts.pipeline import EpisodeSnapshot, Stage
from pdz2.engines.governance import CapabilityProbe, CostGovernor
from pdz2.storage import EpisodeStore

__all__ = ["register", "cmd_capabilities", "cmd_costs", "ledger_from_snapshot"]


def ledger_from_snapshot(snapshot: EpisodeSnapshot) -> CostLedger:
    """Relit les dépenses réellement inscrites au journal de la machine à états.

    Le registre n'invente rien et ne double rien : chaque ligne correspond à
    une transition qui a rapporté un coût. Deux comptabilités qui divergent
    valent moins qu'une seule qui tient.
    """
    return CostLedger(
        episode_id=snapshot.episode_id,
        budget_cap_usd=snapshot.budget_cap_usd,
        records=[
            SpendRecord(
                stage=transition.stage.value,
                amount_usd=transition.cost_usd,
                at=transition.at,
                detail=transition.reason,
            )
            for transition in snapshot.transitions
            if transition.cost_usd > 0
        ],
        parent_id=snapshot.id,
    )


def _open(episode: str) -> EpisodeStore | None:
    store = EpisodeStore(episode)
    if not store.has_snapshot():
        print(f"aucun épisode dans {episode}", file=sys.stderr)
        return None
    return store


def cmd_capabilities(args: argparse.Namespace) -> int:
    outcome = CapabilityProbe(measure=args.measure).run()
    for note in outcome.notes:
        print(note)

    print()
    for entry in outcome.matrix.entries:
        strategies = (
            ", ".join(strategy.value for strategy in entry.strategies) or "—"
        )
        print(f"{entry.provider}/{entry.model}  [{strategies}]")
        if entry.notes:
            print(f"    {entry.notes}")
        for value in entry.values:
            if value.provenance is Provenance.MEASURED:
                stale = " PÉRIMÉE" if value.is_stale(days=outcome.matrix.freshness_days) else ""
                print(
                    f"    {value.name:<24} {value.value:>12g} {value.unit:<18} "
                    f"MESURÉE le {value.measured_at:%Y-%m-%d}{stale}"
                )
                print(f"        méthode : {value.method}")
            elif value.provenance is Provenance.ANNOUNCED:
                print(
                    f"    {value.name:<24} {value.value:>12g} {value.unit:<18} "
                    "ANNONCÉE — jamais vérifiée"
                )
            else:
                print(f"    {value.name:<24} {'—':>12} {'':<18} INCONNUE")

    if args.episode:
        store = EpisodeStore(args.episode)
        store.initialise()
        store.save(outcome.matrix)
        print(f"\nécrit : {store.path_for('capability_matrix')}")
    return 0


def cmd_costs(args: argparse.Namespace) -> int:
    store = _open(args.episode)
    if store is None:
        return 1
    snapshot = store.load_snapshot()
    ledger = ledger_from_snapshot(snapshot)
    store.save(ledger)

    matrix: CapabilityMatrix | None = None
    if store.exists("capability_matrix"):
        matrix = store.load_as(CapabilityMatrix)
    governor = CostGovernor(ledger=ledger, matrix=matrix)

    cap = (
        f"{ledger.budget_cap_usd:.4f} USD"
        if ledger.budget_cap_usd is not None
        else "aucun plafond déclaré"
    )
    print(f"épisode {ledger.episode_id}")
    print(f"  plafond  : {cap}")
    print(f"  dépensé  : {ledger.spent_usd:.4f} USD sur {len(ledger.records)} ligne(s)")
    if ledger.remaining_usd is not None:
        print(f"  restant  : {ledger.remaining_usd:.4f} USD")
    by_stage = ledger.by_stage()
    if by_stage:
        print()
        for stage, total in sorted(by_stage.items(), key=lambda item: -item[1]):
            print(f"  {stage:<20} {total:>10.4f} USD")
    else:
        print(
            "\n  aucune dépense monétaire : cette chaîne tourne entièrement sur des "
            "outils locaux"
        )

    if args.authorize is None:
        print(f"\nécrit : {store.path_for('cost_ledger')}")
        return 0

    try:
        stage = Stage(args.stage)
    except ValueError:
        print(f"étape inconnue : {args.stage}", file=sys.stderr)
        return 1
    decision = governor.may_spend(
        args.authorize, stage=stage, provider=args.provider, model=args.model
    )
    print()
    if decision.allowed:
        print(
            f"AUTORISÉ : {args.authorize:.4f} USD à l'étape « {stage.value} » "
            f"— {decision.detail}"
        )
        return 0
    print(
        f"REFUSÉ [{decision.reason.value}] : {decision.detail}",
        file=sys.stderr,
    )
    return 1


def register(subparsers) -> None:
    capabilities = subparsers.add_parser(
        "capabilities", help="sonder l'environnement et dater ce qu'il sait faire"
    )
    capabilities.add_argument(
        "--episode", default=None, help="dossier où écrire la matrice (facultatif)"
    )
    capabilities.add_argument(
        "--measure",
        action="store_true",
        help="faire réellement travailler les outils pour chronométrer leur débit",
    )
    capabilities.set_defaults(func=cmd_capabilities)

    costs = subparsers.add_parser(
        "costs", help="relire les dépenses et demander une autorisation"
    )
    costs.add_argument("--episode", required=True)
    costs.add_argument(
        "--authorize",
        type=float,
        default=None,
        help="montant en USD dont on demande l'autorisation (ne dépense rien)",
    )
    costs.add_argument(
        "--stage", default=Stage.RENDER.value, help="étape concernée"
    )
    costs.add_argument("--provider", default=None)
    costs.add_argument("--model", default=None)
    costs.set_defaults(func=cmd_costs)
