"""Commande de la phase 12 : le journal de production.

    pdz2 journal --episode DIR

Le journal ne se tient pas à la main : il se **relit**. Chaque entrée provient
d'un contrat écrit sur le disque — une dégradation citée ici est une
dégradation déclarée par un `render_spec_executable`, un constat vient d'un
`observation_report`, un refus d'un `validation_report` ou d'une transition en
échec. Un journal reconstruit ne peut pas raconter une production qui n'a pas
eu lieu.
"""

from __future__ import annotations

import argparse
import sys

from pdz2.contracts.journal import JournalEntryKind
from pdz2.engines.governance import CapabilityProbe, tool_versions
from pdz2.engines.journal import JournalBuilder
from pdz2.storage import EpisodeStore

__all__ = ["register", "cmd_journal"]

_MARKS = {
    JournalEntryKind.DECISION: "décision",
    JournalEntryKind.DEGRADATION: "DÉGRADÉ",
    JournalEntryKind.FINDING: "CONSTAT",
    JournalEntryKind.REFUSAL: "REFUS",
    JournalEntryKind.CAPABILITY: "capacité",
    JournalEntryKind.SPEND: "dépense",
    JournalEntryKind.LIMITATION: "LIMITE",
}


def cmd_journal(args: argparse.Namespace) -> int:
    store = EpisodeStore(args.episode)
    if not store.has_snapshot():
        print(f"aucun épisode dans {args.episode}", file=sys.stderr)
        return 1
    if not store.exists("topic_request"):
        print("épisode sans demande initiale : rien à raconter", file=sys.stderr)
        return 1

    capabilities = []
    if args.probe:
        capabilities = CapabilityProbe().run().capabilities

    outcome = JournalBuilder().build(
        store=store,
        capabilities=capabilities,
        tool_versions=tool_versions(),
    )
    journal = outcome.journal
    store.save(journal)

    print(f"épisode {journal.episode_id} — {journal.topic}")
    print(f"  état     : {journal.episode_status.value}")
    print(f"  début    : {journal.started_at:%Y-%m-%d %H:%M:%S}")
    if journal.ended_at is not None:
        span = (journal.ended_at - journal.started_at).total_seconds()
        print(f"  fin      : {journal.ended_at:%Y-%m-%d %H:%M:%S} ({span:.0f}s)")
    print(f"  dépensé  : {journal.total_spent_usd:.4f} USD")
    print(f"  outils   : {'; '.join(journal.tool_versions)}")

    kinds = {kind: len(journal.of_kind(kind)) for kind in JournalEntryKind}
    print()
    for kind, count in kinds.items():
        if count:
            print(f"  {_MARKS[kind]:<10} {count}")

    if not args.quiet:
        # Une production reprise le lendemain se relit mal en heures seules :
        # les entrées paraissent dans le désordre alors qu'elles sont triées.
        spans_days = (
            journal.ended_at is not None
            and journal.ended_at.date() != journal.started_at.date()
        )
        stamp_format = "%m-%d %H:%M:%S" if spans_days else "%H:%M:%S"
        print()
        for entry in journal.entries:
            stamp = format(entry.at, stamp_format)
            subject = f" {entry.subject_id}" if entry.subject_id else ""
            print(f"  {stamp} [{_MARKS[entry.kind]:<9}] {entry.stage:<16}{subject}")
            print(f"             {entry.summary}")
            if entry.detail and args.verbose:
                print(f"             · {entry.detail}")

    unresolved = journal.unresolved
    print()
    if unresolved:
        print(f"{len(unresolved)} point(s) non résolu(s) — à lire avant de publier :")
        for entry in unresolved:
            print(f"  [{_MARKS[entry.kind]}] {entry.summary}")
    else:
        print("aucun point non résolu.")

    print(f"\nécrit : {store.path_for('production_journal')}")
    return 0


def register(subparsers) -> None:
    journal = subparsers.add_parser(
        "journal", help="reconstruire le journal de production depuis les contrats"
    )
    journal.add_argument("--episode", required=True)
    journal.add_argument(
        "--probe",
        action="store_true",
        help="sonder aussi l'environnement et dater ses capacités",
    )
    journal.add_argument("-q", "--quiet", action="store_true", help="résumé seulement")
    journal.add_argument("-v", "--verbose", action="store_true", help="tout le détail")
    journal.set_defaults(func=cmd_journal)
