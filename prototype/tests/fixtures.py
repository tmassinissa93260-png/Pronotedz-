"""Un storyboard conforme, dont chaque test degrade un point precis."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.prompts import STYLE_DIRECTIVE  # noqa: E402

# Un prompt photo qui satisfait les cinq familles de specificite ET rend
# visible un phenomene invisible, avec sa couleur du code.
IMAGE = (
    "Macro shot of the battery pack beneath the floor of the dark near-black compact electric sedan, "
    "prismatic cells running left to right at centre frame, copper busbars above them "
    "leading forward toward the electric motor, its stator windings and the central rotor "
    "they surround. Controlled yellow "
    "luminous energy streams travel along the busbars, clearly representing the electrical "
    "current leaving the pack. Camera at low angle, 50mm lens feel, shallow depth so the "
    "nearest module is sharp and the rear of the pack falls off. Cool key lighting from the "
    "upper left with soft volumetric haze in the dark studio. Materials: matte near-black paint, "
    "brushed aluminium casing, dark composite tray. Preserve the cell geometry. No text. "
    f"{STYLE_DIRECTIVE}"
)

ANIMATION = (
    "Animate the yellow energy streams travelling continuously along the copper busbars "
    "from the battery pack toward the motor. As the pulses reach the stator windings, the "
    "central rotor progressively begins to rotate. The cells, the busbars and the chassis "
    "stay perfectly rigid. The camera performs a slow secondary macro tracking move. "
    "Preserve exact geometry, proportions and materials. No deformation, no floating parts."
)

VOIX = [
    "La batterie stocke l'énergie et la libère vers le moteur électrique.",
    "Le courant quitte les cellules et parcourt le câble jusqu'au moteur.",
    "Dans le moteur, ce courant traverse le stator et fait tourner le rotor.",
    "La batterie se vide peu à peu, son énergie devenue mouvement.",
]

INTENTS = ["energy_flow", "electromagnetic_rotation", "energy_transfer", "cause_effect"]


def shot(i=1, **over):
    base = {
        "id": i,
        "duration_seconds": 4.0,
        "voice": VOIX[i - 1],
        "visual_description": f"Battery pack and motor of the dark sedan, shot {i}.",
        "educational_function": f"Montre le maillon {i} de la chaîne causale, "
                               f"et pourquoi il alimente le suivant.",
        "visual_concept": "yellow energy flow travelling along the busbars into the "
                          "stator windings, and the rotor it sets in motion",
        "image_prompt": IMAGE,
        "animation_prompt": ANIMATION,
        "motion_intent": INTENTS[i - 1],
        "visual_explanation": {
            "information": "l'énergie stockée quitte la batterie et rejoint le moteur",
            "physical_element": "les busbars en cuivre reliant le pack au stator",
            "secondary_elements": "le pack de cellules, le stator et son rotor",
            "visual_behavior": "un flux jaune lumineux parcourt les busbars vers l'avant",
            "animation_movement": "le flux jaune travels along the busbars toward the "
                                  "stator, puis le rotor commence à tourner",
            "camera_position": "macro en contre-plongée, assez près pour lire "
                               "tout le trajet dans un seul cadre",
            "composition": "le pack à gauche, le moteur à droite, les busbars "
                           "entre les deux au centre du cadre",
        },
    }
    base.update(over)
    return base


def board(n=4, **over):
    base = {
        "subject": "Fonctionnement d'une voiture électrique",
        "duration_seconds": 16,
        "shot_count": n,
        "script": "Une voiture électrique ne brûle rien. Elle transporte son énergie, "
                  "la libère au bon moment, et la transforme en mouvement.",
        "visual_bible": {
            "main_subject": "the powertrain of a dark near-black compact electric sedan",
            "characters_objects": "no characters, only the vehicle and its components",
            "vehicle": "dark near-black compact electric sedan, modern design, realistic proportions",
            "colors": "yellow and orange for electrical energy, blue for the battery, "
                      "green for recovered energy, grey for mechanics",
            "environment": "dark technical studio, night-blue grey backdrop, concrete floor",
            "materials": "matte near-black paint, brushed aluminium, dark composite, visible copper",
            "lighting": "cinematic key light, high contrast, subtle volumetric haze",
            "camera": "slow controlled moves, 35-85mm feel",
            "style_3d": "premium engineering visualization, physically accurate",
            "realism": "photorealistic, no stylisation",
            "invisible_phenomena": "electrical energy shown as controlled yellow luminous "
                                   "streams travelling along the conductors",
        },
        "shots": [shot(i) for i in range(1, n + 1)],
        "quality_check": {
            "narrative_quality": 0.92, "visual_quality": 0.9,
            "scientific_accuracy": 0.94, "voice_visual_alignment": 0.91,
            "visual_continuity": 0.93, "pedagogical_clarity": 0.9,
            "animation_potential": 0.95,
        },
    }
    base.update(over)
    return base
