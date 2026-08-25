"""Commandes de la phase 1 : recherche et réalisation.

Chaque commande fait avancer la machine à états et écrit ses contrats dans le
dossier d'épisode. Une commande qui échoue laisse l'étape en `failed` avec son
motif : l'épisode reste reprenable, et le journal dit ce qui s'est passé.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pdz2.contracts.pipeline import Stage
from pdz2.contracts.research import TopicRequest
from pdz2.engines.direction import BriefRejected, DirectorCompiler, load_brief
from pdz2.engines.direction.ports import brief_template
from pdz2.engines.research import LocalCorpusProvider, ResearchEngine, SearchUnavailable
from pdz2.state import EpisodeStateMachine, TransitionRefused
from pdz2.storage import EpisodeStore

__all__ = [
    "register",
    "cmd_research",
    "cmd_brief_template",
    "cmd_brief_draft",
    "cmd_direct",
]


def _machine(store: EpisodeStore, request: TopicRequest | None = None):
    if store.has_snapshot():
        return EpisodeStateMachine.resume(store.load_snapshot())
    if request is None:
        raise FileNotFoundError(
            f"aucun épisode dans {store.root} — commencer par `pdz2 research`"
        )
    return EpisodeStateMachine.create(
        episode_id=store.root.name,
        topic_request_id=request.id,
        budget_cap_usd=request.budget_cap_usd,
    )


def cmd_research(args: argparse.Namespace) -> int:
    corpus = Path(args.corpus)
    store = EpisodeStore(args.episode)
    store.initialise()

    if store.exists("topic_request"):
        request = store.load_as(TopicRequest)
        print(f"question déjà posée dans cet épisode : {request.topic}")
    else:
        request = TopicRequest(
            topic=args.topic,
            target_duration_s=args.duration,
            language=args.language,
        )
        store.save(request)

    machine = _machine(store, request)
    try:
        machine.start(Stage.RESEARCH, reason=f"corpus {corpus}")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        print("rejouer implique un rembobinage explicite.", file=sys.stderr)
        return 1

    engine = ResearchEngine(providers=[LocalCorpusProvider(corpus)])
    try:
        outcome = engine.run(request)
    except SearchUnavailable as failure:
        machine.fail(Stage.RESEARCH, reason=str(failure))
        store.save_snapshot(machine.snapshot)
        print(f"recherche impossible : {failure}", file=sys.stderr)
        return 1

    store.save(outcome.state)
    machine.complete(Stage.RESEARCH, artifact_ids=[outcome.state.id])
    store.save_snapshot(machine.snapshot)

    for capability in outcome.capabilities:
        print(f"fournisseur {capability.provider} : {capability.state.value} — {capability.detail}")
    for note in outcome.notes:
        print(note)
    print(f"couverture du sujet : {outcome.state.coverage}")
    if outcome.state.open_questions:
        print("\nquestions ouvertes :")
        for question in outcome.state.open_questions:
            print(f"  - {question}")
    print(f"\nécrit : {store.path_for('research_state')}")
    return 0


def cmd_brief_template(args: argparse.Namespace) -> int:
    store = EpisodeStore(args.episode)
    if not store.exists("research_state"):
        print(f"pas de recherche dans {args.episode}", file=sys.stderr)
        return 1
    from pdz2.contracts.research import ResearchState

    request = store.load_as(TopicRequest)
    research = store.load_as(ResearchState)
    template = brief_template(request, research, max_proofs=args.max_proofs)
    target = Path(args.out) if args.out else store.root / "director_brief.template.json"
    target.write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"gabarit écrit : {target}")
    print(
        f"{len(template['visual_proofs'])} affirmations proposées, classées par "
        "démontrabilité mesurée. Les champs vides sont à rédiger."
    )
    return 0


def cmd_brief_draft(args: argparse.Namespace) -> int:
    """Fait rédiger le brief par le raisonneur, et l'écrit sur le disque.

    La décision reste un **fichier**, relu et modifiable, exactement comme un
    brief humain : `direct` ne fait aucune différence entre les deux, et le
    contrat porte la signature de qui a décidé. Sans raisonneur actif la
    commande refuse — elle n'écrit pas un gabarit vide en prétendant avoir
    décidé.
    """
    from pdz2.contracts.research import ResearchState
    from pdz2.engines.direction.ports import ReasonerUnavailable, save_brief
    from pdz2.providers import active_providers

    store = EpisodeStore(args.episode)
    if not store.exists("research_state"):
        print(f"pas de recherche dans {args.episode}", file=sys.stderr)
        return 1

    raisonneur = active_providers().reasoner
    if raisonneur is None:
        print(
            "aucun raisonneur actif : `pdz2 brief-template` produit le gabarit "
            "à remplir à la main.",
            file=sys.stderr,
        )
        return 2

    request = store.load_as(TopicRequest)
    research = store.load_as(ResearchState)
    capacite = raisonneur.get_capabilities()
    print(f"raisonneur {capacite.provider} : {capacite.state.value} — {capacite.detail}")

    try:
        brief = raisonneur.draft_brief(request, research)
    except ReasonerUnavailable as refus:
        print(f"aucune décision obtenue : {refus}", file=sys.stderr)
        return 1

    target = Path(args.out) if args.out else store.root / "director_brief.json"
    save_brief(brief, target)
    print(f"brief écrit : {target}")
    print(f"  thèse   : {brief.thesis}")
    print(f"  chute   : {brief.ending_payoff}")
    print(f"  registre: {brief.visual_language.visual_register}")
    print(
        f"  {len(brief.visual_proofs)} preuve(s) visuelle(s), "
        f"{len(brief.anchors)} ancre(s), décidé par « {brief.author} »"
    )
    print(
        "\nCe brief est un fichier : le relire et le corriger avant `pdz2 direct` "
        "reste la meilleure chose à en faire."
    )
    return 0


def cmd_direct(args: argparse.Namespace) -> int:
    from pdz2.contracts.research import ResearchState

    store = EpisodeStore(args.episode)
    if not store.exists("research_state"):
        print(f"pas de recherche dans {args.episode}", file=sys.stderr)
        return 1

    request = store.load_as(TopicRequest)
    research = store.load_as(ResearchState)
    try:
        brief = load_brief(args.brief)
    except Exception as error:  # noqa: BLE001 — message rendu lisible ci-dessous
        print(f"brief invalide : {error}", file=sys.stderr)
        print(
            "un gabarit non rempli est refusé : rédiger thèse, chute, registre "
            "visuel et chaque preuve visuelle.",
            file=sys.stderr,
        )
        return 1

    machine = _machine(store)
    try:
        machine.start(Stage.DIRECTION, reason=f"brief {brief.id} par {brief.author}")
    except TransitionRefused as refusal:
        print(f"étape refusée : {refusal}", file=sys.stderr)
        return 1

    try:
        outcome = DirectorCompiler().compile(
            request=request, research=research, brief=brief
        )
    except BriefRejected as rejection:
        machine.fail(Stage.DIRECTION, reason=str(rejection))
        store.save_snapshot(machine.snapshot)
        print(f"brief refusé : {rejection}", file=sys.stderr)
        return 1

    store.save(brief)
    store.save(outcome.state)
    machine.complete(
        Stage.DIRECTION, artifact_ids=[brief.id, outcome.state.id]
    )
    store.save_snapshot(machine.snapshot)

    for note in outcome.notes:
        print(note)
    for drop in outcome.dropped:
        print(f"écartée — {drop}")
    print(f"\n{len(outcome.state.shot_intents)} plans :")
    for intent in outcome.state.shot_intents:
        print(
            f"  {intent.order}. [{intent.narrative_function.value:<11} "
            f"{intent.target_duration_s:>5.2f}s] {intent.what_the_viewer_must_see[:70]}"
        )
    print(f"\nécrit : {store.path_for('director_state')}")
    return 0


def register(subparsers) -> None:
    research = subparsers.add_parser(
        "research", help="chercher les faits et construire le Fact Graph"
    )
    research.add_argument("--episode", required=True, help="dossier de l'épisode")
    research.add_argument("--topic", required=True)
    research.add_argument("--corpus", required=True, help="dossier de documents sourcés")
    research.add_argument("--duration", type=float, default=45.0)
    research.add_argument("--language", default="fr")
    research.set_defaults(func=cmd_research)

    template = subparsers.add_parser(
        "brief-template", help="produire un gabarit de brief à remplir"
    )
    template.add_argument("--episode", required=True)
    template.add_argument("--out", default=None)
    template.add_argument("--max-proofs", type=int, default=6, dest="max_proofs")
    template.set_defaults(func=cmd_brief_template)

    draft = subparsers.add_parser(
        "brief-draft", help="faire rédiger le brief par le raisonneur"
    )
    draft.add_argument("--episode", required=True)
    draft.add_argument("--out", default=None)
    draft.set_defaults(func=cmd_brief_draft)

    direct = subparsers.add_parser(
        "direct", help="compiler un brief en DirectorState"
    )
    direct.add_argument("--episode", required=True)
    direct.add_argument("--brief", required=True)
    direct.set_defaults(func=cmd_direct)
