"""Cinq plans, cinquante secondes : le découpage suit ce qui est produit.

Cinq clips existent, ils font 10,24 s chacun, et le script tient en cinq
paragraphes — un par technique. Le découpage colle donc à ces trois faits en
même temps : un paragraphe, un plan, un clip.

Le texte est ramené à ce que cinq plans de dix secondes peuvent porter :
706 caractères au débit mesuré sur la voix d'Adrien (13,9 car./s). Ce qui
tombe n'est jamais un fait, seulement sa deuxième formulation.
"""

import importlib.util
import sys
from pathlib import Path

RACINE = Path("/home/user/Pronotedz-/prototype")
sys.path.insert(0, str(RACINE))


def _charger(nom: str):
    spec = importlib.util.spec_from_file_location(nom, RACINE / f"app/output/{nom}.py")
    module = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, [nom]
    spec.loader.exec_module(module)
    sys.argv = argv
    return module


_auto = _charger("hacking_auto")
_quinze = _charger("video_hacking")

from app import prompts, validator  # noqa: E402
from app.models import Storyboard  # noqa: E402

#: Mesure sur la piste d'Adrien : 1 187 caracteres en 85,343 s.
CAR_PAR_S = 1187 / 85.343
#: L'image utile d'un clip. Le conteneur annonce 10,24 s ; la piste video,
#: elle, s'arrete a 10,00 s.
IMAGE_UTILE = 10.0
#: On ne remplit pas les dix secondes : le debit d'une voix varie d'une phrase
#: a l'autre, et un plan qui deborde oblige a ralentir l'image. Huit dixiemes
#: de marge, c'est une phrase qui traine sans que rien ne casse.
MARGE = 0.8


def _de(i: int):
    p = _auto.PLANS[i]
    return p[2], p[3], p[7], p[4], p[5], p[6]


def _sur_mesure(image, anim, expl, source: int):
    p = _auto.PLANS[source]
    return image, anim, expl, p[4], p[5], p[6]


BLOCS = [
    # 1 — la rue : le crochet et l'annonce
    ("Ta voiture récente peut se faire voler en moins de 30 secondes, "
     "sans casser une vitre. Bienvenue dans le hacking automobile.",
     _de(2)),
    # 2 — la porte : l'attaque par relais, de la clé à la voiture
    ("Première technique : l'attaque par relais. Un complice capte le signal "
     "de ta clé à travers la porte, et ta voiture s'ouvre.",
     _sur_mesure(_quinze.IMAGE_5, _quinze.ANIM_5, _quinze.EXPL_SUR_MESURE[5], 5)),
    # 3 — le faisceau : le bus CAN
    ("Plus lourd : le bus CAN, le réseau où tous les composants de ta voiture "
     "se parlent. Des pirates s'y branchent et imitent ta clé.",
     _sur_mesure(_quinze.IMAGE_9, _quinze.ANIM_9, _quinze.EXPL_SUR_MESURE[9], 11)),
    # 4 — la roue : le TPMS
    ("Même tes pneus sont vulnérables : leurs capteurs radio sont en clair. "
     "Une fausse crevaison peut arrêter un convoi entier.",
     _sur_mesure(_quinze.IMAGE_12, _quinze.ANIM_12, _quinze.EXPL_SUR_MESURE[12], 15)),
    # 5 — l'habitacle : la reprise de contrôle
    ("Mais ce bus sert aussi à reprendre le contrôle. Avec OpenPilot et un "
     "boîtier à 900 euros, tu ajoutes une conduite autonome.",
     _de(18)),
]


def construire() -> dict:
    board = dict(_auto.BOARD)
    shots = []
    for i, (voix, (image, anim, expl, concept, fonction, intention)) in enumerate(
            BLOCS, start=1):
        shots.append({
            "id": i,
            "duration_seconds": round(len(voix) / CAR_PAR_S, 3),
            "voice": voix,
            "visual_description": f"Parisian street at night, the dark car, shot {i}.",
            "educational_function": fonction,
            "visual_concept": concept,
            "image_prompt": prompts.enforce_style(image),
            "animation_prompt": anim,
            "motion_intent": intention,
            "visual_explanation": expl,
        })
    board["shots"] = shots
    board["shot_count"] = len(shots)
    board["duration_seconds"] = round(sum(s["duration_seconds"] for s in shots), 3)
    board["script"] = " ".join(v for v, _ in BLOCS)
    return board


BOARD = construire()


def exporter(chemin: Path) -> None:
    sb = Storyboard.from_dict(BOARD)
    lignes = [f"# {sb.subject}", "",
              f"{BOARD['duration_seconds']:g} secondes · {len(sb.shots)} plans · "
              f"{sum(len(s.voice) for s in sb.shots)} caractères", "",
              "*Un paragraphe, un plan, un clip de 10 s.*", "",
              "## Le code couleur", "", "| notion | couleur | sens |", "|---|---|---|"]
    lignes += [f"| {e.notion} | **{e.color}** | {e.meaning} |" for e in sb.code_couleur()]
    lignes += ["", "## Le texte à dire", "", "```",
               "\n\n".join(s.voice for s in sb.shots), "```", ""]
    for s in sb.shots:
        lignes += [f"## Plan {s.id:02d} · {s.duration_seconds:g} s", "",
                   f"**Voix :** « {s.voice} »", "", f"*{s.educational_function}*", "",
                   "**Prompt image**", "", "```", s.image_prompt, "```", "",
                   "**Prompt animation**", "", "```", s.animation_prompt, "```", ""]
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"écrit : {chemin}")


if __name__ == "__main__":
    sb = Storyboard.from_dict(BOARD)
    total = BOARD["duration_seconds"]
    problemes = validator.validate(sb, total, len(sb.shots))
    car = sum(len(s.voice) for s in sb.shots)
    print(f"{len(sb.shots)} plans · {total:g} s · {car} caractères · "
          f"{sum(len(s.voice.split()) for s in sb.shots)} mots · "
          f"{len(problemes)} problème(s)")
    for s in sb.shots:
        print(f"  {s.id:02d}  {len(s.voice):3d} car.  {s.duration_seconds:5.2f}s")
    print()
    for p in problemes:
        print(f"  [{p.code}] {p.where} : {p.message}")

    if "--projet" in sys.argv:
        from app import config
        config.reset_shots()
        config.ensure_dirs(len(sb.shots))
        sb.save(config.PROJECT_FILE)
        print(f"écrit : {config.PROJECT_FILE}")
    if "--export" in sys.argv:
        exporter(RACINE / "app/output/video_50.md")
