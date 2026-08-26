"""`pdz2 create` — la chaîne complète, en une commande.

L'orchestrateur n'a aucune intelligence propre : il appelle les commandes de
phase, dans l'ordre du graphe d'étapes, et s'arrête à la première qui refuse.
Il ne rattrape rien, il ne contourne rien — un refus d'étape est un refus de
production.

Il s'arrête aussi, volontairement, devant le brief de réalisation — sauf si
un raisonneur est branché. Le brief est la décision qu'aucun *compilateur* de
cette chaîne ne sait prendre : quelle thèse défendre, sur quel ton, pour qui.
Sans raisonneur, `create` prépare le gabarit, le remplit d'éléments réellement
trouvés, et rend la main.

    HUMANS JUDGE WHAT MACHINES CANNOT MEASURE

La règle n'est pas contournée par `brief-draft` : elle est déplacée d'un cran.
Le raisonneur décide, et sa décision reste un fichier relisible, signé de son
nom dans `DirectorBrief.author`, refusable par le contrat comme n'importe quel
brief. Ce qui reste interdit, ici comme avant, c'est qu'un compilateur
déterministe invente une thèse parce que personne ne lui en a donné.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pdz2.contracts.pipeline import Stage, StageStatus
from pdz2.storage import EpisodeStore

__all__ = ["cmd_create", "STEPS", "STAGE_OF"]

STEPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("capabilities", ("--measure",)),
    ("script", ()),
    ("voice", ()),
    ("timeline", ()),
    ("bible", ()),
    ("shots", ()),
    ("motion", ()),
    ("specs", ()),
    ("validate", ()),
    ("route", ()),
    ("assets", ()),
    ("render", ()),
    ("observe", ()),
    ("diagnose", ()),
    ("edit", ()),
    ("master", ()),
    ("subtitle", ()),
    ("deliver", ()),
    ("costs", ()),
    ("journal", ()),
)
"""Étapes enchaînées après la direction, dans l'ordre du graphe."""

STAGE_OF: dict[str, Stage] = {
    "research": Stage.RESEARCH,
    "direct": Stage.DIRECTION,
    "script": Stage.SCRIPT,
    "voice": Stage.VOICE,
    "timeline": Stage.TIMELINE,
    "bible": Stage.VISUAL_BIBLE,
    "shots": Stage.SHOT_GRAPH,
    "motion": Stage.MOTION,
    "specs": Stage.RENDER_SPEC,
    "validate": Stage.STATIC_VALIDATION,
    "route": Stage.ROUTING,
    "assets": Stage.ASSETS,
    "render": Stage.RENDER,
    "observe": Stage.OBSERVATION,
    "diagnose": Stage.DIAGNOSIS,
    "edit": Stage.EDIT,
    "master": Stage.AUDIO_MASTER,
    "subtitle": Stage.SUBTITLES,
    "deliver": Stage.DELIVERY,
}
"""Étape du graphe couverte par chaque commande.

`capabilities`, `costs` et `journal` n'y figurent pas : ce sont des lectures,
elles ne font avancer aucune étape et se rejouent sans conséquence.
"""

_DONE = {StageStatus.DONE, StageStatus.SKIPPED}


def _already_done(episode: str, command: str) -> bool:
    """Une étape terminée ne se rejoue pas en silence.

    Reprendre `create` après avoir rempli le brief est le parcours normal : la
    recherche a déjà eu lieu, et la relancer serait refusée par la machine à
    états — à juste titre, puisque rejouer une étape faite exige un
    rembobinage explicite. L'orchestrateur la saute donc, et le dit.
    """
    stage = STAGE_OF.get(command)
    if stage is None:
        return False
    store = EpisodeStore(episode)
    if not store.has_snapshot():
        return False
    return store.load_snapshot().state(stage).status in _DONE


def _run(command: str, arguments: list[str]) -> int:
    from pdz2.cli.main import main as dispatch

    print(f"\n=== pdz2 {command} " + " ".join(arguments), flush=True)
    return dispatch([command, *arguments])


def _step(episode: str, command: str, arguments: list[str]) -> int:
    if _already_done(episode, command):
        print(f"\n=== pdz2 {command} — déjà fait, sauté", flush=True)
        return 0
    return _run(command, arguments)


def cmd_create(args: argparse.Namespace) -> int:
    episode = args.episode
    brief = Path(args.brief) if args.brief else None

    code = _step(
        episode,
        "research",
        [
            "--episode", episode,
            "--topic", args.topic,
            "--corpus", args.corpus,
            "--duration", str(args.duration),
            "--language", args.language,
            "--animated-shots", str(args.animated_shots),
        ],
    )
    if code != 0:
        return code

    if brief is None or not brief.is_file():
        target = brief or Path(episode) / "brief.json"
        # Un raisonneur actif est le seul cas où la chaîne franchit cette
        # marche seule. Il ne remplace pas le jugement humain : il produit un
        # fichier signé de son nom, que `direct` traite comme n'importe quel
        # brief et que le contrat juge de la même façon.
        code = _run("brief-draft", ["--episode", episode, "--out", str(target)])
        if code == 2:
            code = _run("brief-template", ["--episode", episode, "--out", str(target)])
            if code != 0:
                return code
            print(
                "\nLa chaîne s'arrête ici, et c'est voulu.\n"
                f"Le brief de réalisation attend une décision : {target}\n"
                "Thèse, ton, public, angle — aucune mesure de ce système ne les "
                "remplace, et aucun raisonneur n'est branché pour les décider.\n"
                f"Reprendre ensuite avec :\n"
                f"  pdz2 create --episode {episode} --topic \"{args.topic}\" "
                f"--corpus {args.corpus} --brief {target}",
                file=sys.stderr,
            )
            return 3
        if code != 0:
            return code
        brief = target

    code = _step(episode, "direct", ["--episode", episode, "--brief", str(brief)])
    if code != 0:
        return code

    for command, extra in STEPS:
        code = _step(episode, command, ["--episode", episode, *extra])
        if code != 0:
            print(
                f"\nPRODUCTION INTERROMPUE à l'étape « {command} ».\n"
                f"L'état est sur le disque : `pdz2 state show {episode}`.",
                file=sys.stderr,
            )
            return code

    print(f"\nÉPISODE PRODUIT : {Path(episode) / 'final.mp4'}")
    return 0


def register(subparsers) -> None:
    create = subparsers.add_parser(
        "create", help="produire un épisode de bout en bout"
    )
    create.add_argument("--episode", required=True, help="dossier de l'épisode")
    create.add_argument("--topic", required=True)
    create.add_argument("--corpus", required=True, help="dossier de documents sourcés")
    create.add_argument(
        "--brief",
        default=None,
        help="brief de réalisation rempli ; sans lui, la chaîne s'arrête au gabarit",
    )
    create.add_argument("--duration", type=float, default=45.0)
    create.add_argument("--language", default="fr")
    # `create` enchaîne les phases : toute option que `research` accepte et qui
    # décide de l'épisode doit exister ici aussi, sinon elle est inatteignable
    # depuis le seul point d'entrée que le workflow emploie. Le run #9 est mort
    # là-dessus en deux secondes — « unrecognized arguments: --animated-shots ».
    create.add_argument(
        "--animated-shots",
        type=int,
        default=0,
        dest="animated_shots",
        help=(
            "combien de plans, au plus, peuvent être animés par un modèle "
            "payant. Zéro par défaut : aucune dépense."
        ),
    )
    create.set_defaults(func=cmd_create)
