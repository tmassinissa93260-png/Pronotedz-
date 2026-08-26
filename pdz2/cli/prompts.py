"""`pdz2 prompts` — reconstituer ce qui a été dit aux fournisseurs.

Le prompt n'est stocké nulle part, et c'est délibéré : il est une compilation
secondaire du contrat, jamais une source de vérité. Le corollaire embarrassant,
c'est qu'après coup plus personne ne sait exactement ce qui est parti — alors
que c'est précisément ce qu'on veut relire quand une image déçoit.

Cette commande lève la contradiction sans la trahir. Elle ne lit aucun prompt
enregistré : elle **recompile** depuis les contrats de l'épisode, avec le même
compilateur que l'adaptateur emploie. Le résultat est donc exact par
construction — si les deux divergeaient un jour, ce serait un bogue du
compilateur, pas un décalage d'archive.

Elle ne touche pas au réseau, ne dépense rien, et se rejoue autant de fois
qu'on veut.
"""

from __future__ import annotations

import argparse
import sys

from pdz2.contracts.visual import ImageSpec, VisualBible
from pdz2.providers.prompting import animation_prompt, image_prompt, negative_prompt
from pdz2.storage import EpisodeStore

__all__ = ["register", "cmd_prompts"]


def cmd_prompts(args: argparse.Namespace) -> int:
    store = EpisodeStore(args.episode)
    if not store.exists("visual_bible"):
        print(f"pas de bible visuelle dans {args.episode}", file=sys.stderr)
        return 1

    bible = store.load_as(VisualBible)
    specs: list[ImageSpec] = sorted(
        store.load_collection("image_spec"), key=lambda spec: spec.shot_id
    )
    if not specs:
        print("aucune spécification d'image — lancer `pdz2 specs`", file=sys.stderr)
        return 1

    executables = {
        item.shot_id: item for item in store.load_collection("render_spec_executable")
    }
    # Indexés par plan, pas par identifiant : `RenderSpecExecutable.requested`
    # est un `RequestedEcho` — une copie des champs demandés — et il ne porte
    # pas `motion_program_id`. L'y chercher levait une `AttributeError` qui
    # coupait la commande au premier plan, run #8 compris.
    motions = {item.shot_id: item for item in store.load_collection("motion_program")}

    voulus = set(args.shot or [])
    retenus = [spec for spec in specs if not voulus or spec.shot_id in voulus]
    if not retenus:
        connus = ", ".join(spec.shot_id for spec in specs)
        print(f"plan inconnu : {', '.join(sorted(voulus))} (connus : {connus})",
              file=sys.stderr)
        return 1

    print(f"épisode {store.root.name} — bible {bible.id}")
    print(
        f"{len(retenus)} plan(s), recompilés depuis les contrats. "
        "Aucun prompt n'est lu sur le disque : ils n'y sont pas."
    )

    for spec in retenus:
        print()
        print("─" * 78)
        print(f"{spec.shot_id}  ·  {spec.resolution.width}×{spec.resolution.height}"
              f"  ·  graine {spec.seed}  ·  {len(spec.layers)} calque(s)")
        print("─" * 78)

        interdits = negative_prompt(spec, bible)

        # Un appel par calque : c'est ce que fait l'adaptateur d'images, pour
        # que les plans restent séparables en profondeur au moment du rendu.
        for calque in sorted(spec.layers, key=lambda item: item.depth):
            print()
            print(f"  ── calque « {calque.role.value} » (profondeur {calque.depth})")
            # Le même appel que l'adaptateur, calque compris. Reconstruire la
            # phrase à la main ici avait produit un ordre différent du réel :
            # le calque arrivait après la palette au lieu de la précéder.
            print(f"  prompt : {image_prompt(spec, bible, calque)}")
        if interdits:
            print()
            print(f"  interdits : {interdits}")

        executable = executables.get(spec.shot_id)
        if executable is not None and args.animation:
            motion = motions.get(spec.shot_id)
            print()
            print(f"  ── animation ({executable.strategy.value})")
            print(f"  prompt : {animation_prompt(executable, motion)}")

    print()
    print(
        "Ces phrases sont une traduction du contrat, à sens unique. Les corriger "
        "se fait dans `pdz2/providers/prompting.py` — jamais dans un contrat."
    )
    return 0


def register(subparsers) -> None:
    prompts = subparsers.add_parser(
        "prompts", help="recompiler les prompts envoyés aux fournisseurs"
    )
    prompts.add_argument("--episode", required=True)
    prompts.add_argument(
        "--shot",
        action="append",
        default=None,
        help="limiter à un plan (répétable), par exemple --shot S05",
    )
    prompts.add_argument(
        "--animation",
        action="store_true",
        help="afficher aussi la consigne de mouvement",
    )
    prompts.set_defaults(func=cmd_prompts)
