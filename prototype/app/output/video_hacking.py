"""Les 75 secondes du hacking automobile — LE texte de la voix, mot pour mot.

Le decoupage precedent retouchait cinq phrases pour tenir les regles du
systeme : l'ouverture coupee en deux, « ne touchent plus a la serrure », les
pronoms remplaces par leur acteur. L'auteur a tranche : c'est SON texte, et il
ne bouge pas.

Une phrase, un plan. Les prompts image et animation viennent de
hacking_auto.py ; les trois phrases longues portent deux temps dans leur
animation, parce qu'elles durent dix secondes et qu'un plan de dix secondes a
la place d'en montrer deux.
"""

import importlib.util
import sys
from pathlib import Path

RACINE = Path("/home/user/Pronotedz-/prototype")
sys.path.insert(0, str(RACINE))

_spec = importlib.util.spec_from_file_location("hacking_auto",
                                               RACINE / "app/output/hacking_auto.py")
_h = importlib.util.module_from_spec(_spec)
_argv, sys.argv = sys.argv, ["hacking_auto"]
_spec.loader.exec_module(_h)
sys.argv = _argv

from app import prompts, validator  # noqa: E402
from app.models import Storyboard  # noqa: E402

PLANS = _h.PLANS
FIN = _h.FIN

#: (phrase de l'auteur, duree, plan d'origine dans hacking_auto)
DECOUPAGE = [
    ("Ta voiture récente peut se faire voler en moins de 30 secondes chrono, "
     "et sans même casser une vitre.", 6.5, 0),
    ("Bienvenue dans le monde du hacking automobile.", 2.5, 2),
    ("Première technique : l'attaque par relais.", 2.0, 3),
    ("Les voleurs n'ont plus besoin de crochetage.", 2.5, 4),
    ("Un premier complice capte le signal de ta clé à travers ta porte d'entrée "
     "et le retransmet à un second boîtier près du véhicule.", 8.5, 5),
    ("La voiture croit que tu es à côté et se déverrouille.", 4.0, 7),
    ("Plus lourd encore : le bus CAN.", 2.5, 8),
    ("C'est le réseau informatique interne où tous les composants de ta voiture "
     "se parlent.", 5.0, 9),
    ("Des pirates percent sous l'aile avant pour se brancher directement sur le "
     "câble du phare, injectent des trames de données, et font croire au "
     "calculateur qu'ils ont la vraie clé.", 10.5, 11),
    ("Même tes pneus sont vulnérables !", 2.0, 13),
    ("Le système TPMS mesure la pression via des capteurs radio non chiffrés.", 4.5, 14),
    ("En envoyant de fausses données de crevaison ou de surchauffe à distance, un "
     "hacker peut créer une erreur système ou forcer un convoi à s'arrêter.", 9.0, 15),
    ("Heureusement, ce même bus CAN sert aussi à reprendre le contrôle !", 4.5, 17),
    ("Avec un logiciel open-source comme OpenPilot et un boîtier à 900 €, tu peux "
     "ajouter une vraie conduite autonome niveau 2 sur ta voiture.", 8.5, 18),
    ("Abonne-toi pour la partie 2 !", 2.5, 19),
]

# ---------------------------------------------------------------------------
# Les trois phrases longues durent dix secondes : leur plan porte deux temps,
# et l'image doit contenir les deux, sinon l'animation fait apparaitre un
# objet hors cadre.
# ---------------------------------------------------------------------------

IMAGE_5 = (
    "Medium night shot of the building's front door from outside, mannequin 2 in "
    "the heather grey hoodie pressing a flat black box against the painted wood at "
    "chest height. Position: the car key hangs on its hook inside, framed through "
    "the glazed panel just above the box; the antenna face is pressed flat to the "
    "door, and beyond the figure, eight metres away at frame right, the dark "
    "near-black car waits at the kerb with a second identical box held against its "
    "driver door. Blue luminous pulses leave the key, cross the wood, and are drawn "
    "into the antenna face, clearly representing the key's own signal being picked "
    "up; a red luminous beam runs from that box across the courtyard to the second "
    "one. Camera: static medium view at chest height, deep enough focus to hold "
    "both the door and the car, the gate falling into bokeh. Lighting: warm hallway "
    "glow behind the glazed panel, cold street lamp from above left, deep shadow on "
    "the wood. Materials: painted wood, glass, matte black plastic housings, brass "
    "key, matte near-black paint, wet cobblestone."
)
ANIM_5 = (
    "The blue pulses leave the key, cross the wood one after another, and are drawn "
    "into the antenna face, and as each one enters, the red beam across the "
    "courtyard steadily brightens; then the blue pulses begin to travel along that "
    "beam from left to right until they reach the second box at the car and enter "
    "its door handle unchanged. The door, the key, the boxes and the car stay "
    "perfectly rigid. The camera holds still." + FIN
)

IMAGE_9 = (
    "Macro shot of the twisted pair of the car's internal network inside the front "
    "left wheel arch of the dark near-black car, its braided sheath ghosted to "
    "transparency so both copper conductors read clearly. Position: the pair "
    "crosses the frame from the lower left to the upper right and ends at the "
    "control unit connector at the top right, its row of copper pins visible "
    "through the ghosted aluminium lid; the edge of the wheel arch runs along the "
    "lower border. Blue luminous pulses already travel rightwards along the pair; "
    "red luminous pulses enter from beyond the lower left corner of the frame and "
    "join the same pair, travelling in the same direction and the same shape, "
    "clearly representing frames added from outside. Camera: static macro at low "
    "angle, shallow depth of field so the conductors are sharp and the arch falls "
    "into bokeh. Lighting: hard cold neon key raking across the sheath, warm street "
    "lamp rim on the conductors, deep shadow behind. Materials: braided grey cable "
    "sheath around the pair, copper conductors, brushed aluminium lid, textured "
    "black plastic liner."
)
ANIM_9 = (
    "The red pulses enter from beyond the lower left corner, gradually build in "
    "number, and travel rightwards along the twisted pair mixed in with the blue "
    "ones, while the blue pulses keep travelling at their own spacing; then red and "
    "blue reach the connector together and its copper pins light up identically for "
    "both, until the whole row is glowing. The pair, the sheath and the connector "
    "stay perfectly rigid. The camera holds still." + FIN
)

IMAGE_12 = (
    "Medium night shot of mannequin 2 in the heather grey hoodie kneeling at the "
    "kerb beside the dark near-black car, a small handheld radio unit held toward "
    "the front wheel. Position: the figure fills frame left, the wheel and its arch "
    "fill frame right, the side indicator repeater sits on the wing just above the "
    "arch, half a metre of wet cobblestone between the unit and the tyre. Red "
    "luminous pulses leave the handheld unit and travel toward the wheel arch in "
    "exactly the same shape and spacing as the blue ones still leaving the sensor "
    "inside the rim, clearly representing a second reading sent from outside the "
    "wheel. Camera: static medium view at hub height, shallow depth of field so the "
    "unit and the tyre are sharp and the street falls into bokeh. Lighting: warm "
    "street lamp from above right, cold LED glow from the handheld unit, deep "
    "shadow in the arch. Materials: matte white plastic skin, grey brushed-cotton "
    "hoodie, matte black plastic unit, black rubber tyre, brushed aluminium rim."
)
ANIM_12 = (
    "The red pulses begin to leave the handheld unit, gradually matching the "
    "spacing of the blue ones, and travel steadily toward the wheel arch beside "
    "them; as they rise through the arch together the side indicator repeater above "
    "it lights up and holds, and the wheel slows until it stops turning. The "
    "figure, the unit and the car stay perfectly rigid. The camera holds still." + FIN
)

SUR_MESURE = {5: (IMAGE_5, ANIM_5), 9: (IMAGE_9, ANIM_9), 12: (IMAGE_12, ANIM_12)}

EXPL_SUR_MESURE = {
    5: {"information": "le signal de la clé est capté puis reporté jusqu'à la voiture",
        "physical_element": "the flat black box pressed against the front door",
        "secondary_elements": "la clé au crochet, le panneau vitré, le second "
                              "boîtier contre la voiture au fond",
        "visual_behavior": "les impulsions bleues traversent le bois, entrent dans "
                           "l'antenne, puis longent le faisceau rouge",
        "animation_movement": "les impulsions bleues traversent le bois et gagnent "
                              "l'antenne, puis parcourent le faisceau rouge jusqu'à "
                              "la poignée de la voiture",
        "camera_position": "moyen statique à hauteur de poitrine, foyer profond",
        "composition": "la porte et le boîtier au centre, la voiture au fond à droite"},
    9: {"information": "les fausses trames prennent le même fil que les vraies et "
                       "arrivent au calculateur",
        "physical_element": "the twisted pair ending at the control unit connector",
        "secondary_elements": "la gaine tressée, les broches de cuivre, le passage "
                              "de roue",
        "visual_behavior": "des impulsions rouges rejoignent les bleues puis "
                           "allument les mêmes broches",
        "animation_movement": "les impulsions rouges entrent par le coin du cadre, "
                              "parcourent la paire mêlées aux bleues, et les broches "
                              "du connecteur s'allument pareil pour les deux",
        "camera_position": "macro statique en contre-plongée, faible profondeur de champ",
        "composition": "la paire en diagonale, le connecteur en haut à droite"},
    12: {"information": "un faux signal envoyé de loin suffit à arrêter la voiture",
         "physical_element": "the handheld radio unit in the mannequin's hand",
         "secondary_elements": "la roue, le passage de roue, le répétiteur de "
                               "clignotant sur l'aile",
         "visual_behavior": "des impulsions rouges quittent le boîtier au rythme "
                            "des bleues, puis le répétiteur s'allume",
         "animation_movement": "les impulsions rouges parcourent le passage de roue "
                               "à côté des bleues, le répétiteur s'allume et la roue "
                               "s'arrête de tourner",
         "camera_position": "moyen statique à hauteur de moyeu, faible profondeur de champ",
         "composition": "le mannequin à gauche, la roue à droite, le répétiteur au-dessus"},
}


def construire() -> dict:
    board = dict(_h.BOARD)
    shots = []
    for i, (voix, duree, source) in enumerate(DECOUPAGE, start=1):
        p = PLANS[source]
        image, anim = SUR_MESURE.get(i, (p[2], p[3]))
        shots.append({
            "id": i, "duration_seconds": duree, "voice": voix,
            "visual_description": f"Parisian street at night, the dark car, shot {i}.",
            "educational_function": p[5],
            "visual_concept": p[4],
            "image_prompt": prompts.enforce_style(image),
            "animation_prompt": anim,
            "motion_intent": p[6],
            "visual_explanation": EXPL_SUR_MESURE.get(i, p[7]),
        })
    board["shots"] = shots
    board["shot_count"] = len(shots)
    board["duration_seconds"] = round(sum(d for _, d, _ in DECOUPAGE), 3)
    board["script"] = " ".join(v for v, _, _ in DECOUPAGE)
    return board


BOARD = construire()

if __name__ == "__main__":
    sb = Storyboard.from_dict(BOARD)
    total = BOARD["duration_seconds"]
    problemes = validator.validate(sb, total, len(sb.shots))
    mots = sum(len(s.voice.split()) for s in sb.shots)
    print(f"{len(sb.shots)} plans · {total:g} s · {mots} mots · "
          f"{len(problemes)} problème(s)\n")
    for p in problemes:
        print(f"  [{p.code}] {p.where} : {p.message}")
        print(f"      → {p.fix[:190]}\n")

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
              f"{sum(len(s.voice.split()) for s in sb.shots)} mots",
              "", "*Le texte de la voix est celui de l'auteur, mot pour mot.*", "",
              "## La direction artistique", "", "```",
              BOARD["style_directive"], "```", "",
              "Elle est déjà collée à la fin de chaque prompt image.", "",
              "## Le code couleur", "", "| notion | couleur | sens |", "|---|---|---|"]
    lignes += [f"| {e.notion} | **{e.color}** | {e.meaning} |" for e in sb.code_couleur()]
    lignes += ["", "## Le script", "", "> " + sb.script, ""]
    for s in sb.shots:
        lignes += [f"## Plan {s.id:02d} · {s.duration_seconds:g} s", "",
                   f"**Voix :** « {s.voice} »", "", f"*{s.educational_function}*", "",
                   "**Prompt image**", "", "```", s.image_prompt, "```", "",
                   "**Prompt animation**", "", "```", s.animation_prompt, "```", ""]
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"écrit : {chemin}")


if "--export" in sys.argv:
    exporter(RACINE / "app/output/video_hacking.md")
