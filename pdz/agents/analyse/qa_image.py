"""Vérifie une image RÉELLEMENT générée contre la checklist de son plan.

Ne tourne jamais sur tous les plans, et jamais avant que l'image existe —
voir `pdz/production/qa_images.py` pour le déclenchement (seulement les
plans qui ont déjà montré un signe de dérive côté texte). Ne renvoie jamais
de score : PASS, FAIL ou UNCERTAIN, et une liste précise de ce qui ne va
pas — voir la discussion qui a précédé cet agent sur pourquoi un score
auto-évalué ne mesure rien de vérifiable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pdz.agents.base import Agent
from pdz.moteur.pipeline import Contexte


class ImageQA(Agent):
    nom = "qa_image"
    version = "1.0.0"
    prompt_ref = "analyse/qa_image"

    def variables(self, entrees: dict[str, Any], ctx: Contexte) -> dict[str, Any]:
        return {
            "replique": entrees.get("replique", ""),
            "action": entrees["action"],
            "elements_obligatoires": entrees.get("elements_obligatoires", []),
            "elements_a_exclure": entrees.get("elements_a_exclure", []),
        }

    def images(self, entrees: dict[str, Any], ctx: Contexte) -> list[Path] | None:
        return [entrees["image"]]
