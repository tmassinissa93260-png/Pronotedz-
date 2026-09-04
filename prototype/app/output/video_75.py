"""Le découpage à 75 secondes : huit plans de dix, taillés pour le générateur.

Deux décisions de l'auteur, prises après avoir entendu la voix d'Adrien :

  · viser 75 s. La voix dit 13,9 caractères par seconde — c'est mesuré sur sa
    piste, pas estimé — donc 1 045 caractères. Le texte en faisait 1 171.
  · des plans de dix secondes. Le générateur d'images rend toujours des clips
    de 10,24 s : un plan plus court se coupe, un plan plus long oblige à
    ralentir l'image. Chaque bloc tient donc sous 10,2 s.

Quinze phrases devenaient quinze plans de trois à douze secondes. Huit blocs
de dix secondes collent au matériel, et cinq d'entre eux ont déjà leur vidéo.
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

#: (texte, image, animation, explication, concept, fonction, intention)
def _de(i: int):
    p = _auto.PLANS[i]
    return p[2], p[3], p[7], p[4], p[5], p[6]


BLOCS = [
    ("Ta voiture récente peut se faire voler en moins de 30 secondes, "
     "et sans même casser une vitre. Bienvenue dans le monde du hacking automobile.",
     _de(2)),
    ("Première technique : l'attaque par relais. Les voleurs n'ont plus besoin "
     "de crochetage : ils volent ton signal, pas ta clé.",
     _de(3)),
    ("Un complice capte le signal de ta clé à travers ta porte d'entrée, "
     "et le retransmet à un second boîtier posé contre ta voiture.",
     (_quinze.IMAGE_5, _quinze.ANIM_5, _quinze.EXPL_SUR_MESURE[5],
      _auto.PLANS[5][4], _auto.PLANS[5][5], _auto.PLANS[5][6])),
    ("La voiture croit que tu es à côté, et se déverrouille. "
     "Aucune trace, aucune alarme, aucune vitre cassée. Trente secondes, montre en main.",
     _de(7)),
    ("Plus lourd encore : le bus CAN, le réseau interne où tout se parle. "
     "Des pirates s'y branchent et se font passer pour ta clé.",
     (_quinze.IMAGE_9, _quinze.ANIM_9, _quinze.EXPL_SUR_MESURE[9],
      _auto.PLANS[11][4], _auto.PLANS[11][5], _auto.PLANS[11][6])),
    ("Même tes pneus sont vulnérables. Le système TPMS mesure la pression "
     "via des capteurs radio non chiffrés. Non chiffrés, donc copiables.",
     _de(13)),
    ("En envoyant une fausse crevaison à distance, un hacker peut créer "
     "une erreur système, ou forcer un convoi entier à s'arrêter.",
     (_quinze.IMAGE_12, _quinze.ANIM_12, _quinze.EXPL_SUR_MESURE[12],
      _auto.PLANS[15][4], _auto.PLANS[15][5], _auto.PLANS[15][6])),
    ("Mais ce même bus sert aussi à reprendre le contrôle. Avec OpenPilot "
     "et un boîtier à 900 euros, tu ajoutes une conduite autonome niveau 2.",
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

if __name__ == "__main__":
    sb = Storyboard.from_dict(BOARD)
    total = BOARD["duration_seconds"]
    problemes = validator.validate(sb, total, len(sb.shots))
    car = sum(len(s.voice) for s in sb.shots)
    print(f"{len(sb.shots)} plans · {total:g} s · {car} caractères · "
          f"{sum(len(s.voice.split()) for s in sb.shots)} mots · "
          f"{len(problemes)} problème(s)\n")
    for p in problemes:
        print(f"  [{p.code}] {p.where} : {p.message}")
        print(f"      → {p.fix[:170]}\n")

    if "--projet" in sys.argv:
        from app import config
        config.reset_shots()
        config.ensure_dirs(len(sb.shots))
        sb.save(config.PROJECT_FILE)
        print(f"écrit : {config.PROJECT_FILE}")


def exporter(chemin: Path) -> None:
    """La feuille à lire depuis un téléphone : un bloc par prompt."""
    sb = Storyboard.from_dict(BOARD)
    lignes = [f"# {sb.subject}", "",
              f"{BOARD['duration_seconds']:g} secondes · {len(sb.shots)} plans · "
              f"{sum(len(s.voice) for s in sb.shots)} caractères", "",
              "*Découpé pour des clips de 10 s. Débit mesuré sur la voix "
              "d'Adrien : 13,9 caractères par seconde.*", "",
              "## Le code couleur", "", "| notion | couleur | sens |", "|---|---|---|"]
    lignes += [f"| {e.notion} | **{e.color}** | {e.meaning} |" for e in sb.code_couleur()]
    lignes += ["", "## Le texte à dire", "", "```", "\n\n".join(s.voice for s in sb.shots),
               "```", ""]
    for s in sb.shots:
        lignes += [f"## Plan {s.id:02d} · {s.duration_seconds:g} s", "",
                   f"**Voix :** « {s.voice} »", "", f"*{s.educational_function}*", "",
                   "**Prompt image**", "", "```", s.image_prompt, "```", "",
                   "**Prompt animation**", "", "```", s.animation_prompt, "```", ""]
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"écrit : {chemin}")


if "--export" in sys.argv:
    exporter(RACINE / "app/output/video_75.md")
