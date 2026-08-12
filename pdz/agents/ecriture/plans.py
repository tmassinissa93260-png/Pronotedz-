"""L'agent qui transforme un script déjà écrit en prompts d'image riches.

ScriptWriter écrit le dialogue et une action minimale par réplique — de
quoi savoir ce qui se passe, pas de quoi cadrer une image. Cet agent prend
le relais UNE FOIS le script figé : à partir de ce qui se dit et de la
fonction de chaque plan (SHOT_FUNCTION), il écrit un vrai prompt de
cinéaste — cadrage, ce qui est net, ce qui reste dans l'ombre — un par
réplique. C'est ce prompt qui remplace `action` avant la génération
d'image, jamais celui écrit par ScriptWriter en même temps que le dialogue.

Le séparer de l'écriture du dialogue n'est pas cosmétique : un modèle qui
répartit son attention entre « qu'est-ce qu'on dit » et « comment on le
filme » en même temps écrit les deux moins bien qu'un modèle qui ne
s'occupe QUE du cadrage, une fois le texte déjà là.
"""

from __future__ import annotations

import copy
from typing import Any

from pdz.agents.base import Agent
from pdz.moteur.erreurs import ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.univers import Univers


class ShotPromptWriter(Agent):
    nom = "shot_prompts"
    version = "1.0.0"
    prompt_ref = "ecriture/plans"

    def variables(self, entrees: dict[str, Any], ctx: Contexte) -> dict[str, Any]:
        univers: Univers = entrees["univers"]
        return {
            "contexte_univers": univers.contexte_script(),
            "repliques": [
                {
                    "numero": r["numero"],
                    "personnage": r.get("personnage", ""),
                    "replique": r["replique"],
                    "action": r.get("action", ""),
                    "fonction_plan": r.get("fonction_plan", ""),
                }
                for r in entrees["repliques"]
            ],
        }

    def schema(self, base: dict, entrees: dict[str, Any], ctx: Contexte) -> dict:
        """Impose au moins un prompt par réplique — même raison que
        `minItems` sur les répliques de ScriptWriter : un script à 8
        répliques qui ne reçoit que 5 prompts d'image laisse 3 plans sans
        rien pour les illustrer, sans qu'aucune règle du schéma ne le
        remarque."""
        schema = copy.deepcopy(base)
        schema["properties"]["plans"]["minItems"] = len(entrees["repliques"])
        return schema

    def apres(self, sortie: dict, entrees: dict, ctx: Contexte) -> dict:
        plans = sortie.get("plans", [])
        attendus = {r["numero"] for r in entrees["repliques"]}
        obtenus = {p.get("numero") for p in plans}
        manquants = attendus - obtenus
        if manquants:
            raise ErreurValidation(
                f"Prompts d'image manquants pour les répliques "
                f"{sorted(manquants)} — il en faut un par réplique, "
                f"{len(attendus)} au total."
            )
        return sortie

    def fusionner(self, repliques: list[dict], sortie: dict) -> list[dict]:
        """Remplace `action` par le prompt riche, réplique par réplique.

        Sépare exprès de `apres()` : `apres()` valide ce que le modèle a
        renvoyé, `fusionner()` l'applique aux répliques du script. Les
        répliques dont le numéro n'a pas de prompt correspondant — ne
        devrait plus arriver après `apres()`, mais un appelant qui saute la
        validation ne doit pas planter pour autant — gardent leur action
        d'origine plutôt que de perdre toute description.
        """
        par_numero = {p["numero"]: p["prompt_image"] for p in sortie.get("plans", [])}
        fusionnees = []
        for r in repliques:
            r = dict(r)
            if r["numero"] in par_numero:
                r["action"] = par_numero[r["numero"]]
            fusionnees.append(r)
        return fusionnees
