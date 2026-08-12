"""L'agent qui corrige, en amont, ce qu'un modèle d'image rate toujours.

ShotPromptWriter écrit déjà un bon prompt par plan — cadrage, netteté,
fonction. Mais certains de ces prompts demandent, sans le savoir, un détail
que les modèles de génération d'image actuels ne savent PAS rendre : du
texte lisible, un logo, un visage net là où l'univers l'interdit. Le
résultat n'est jamais « raté proprement » — c'est une bouillie de
caractères ou un visage plein qui apparaît malgré la consigne.

Deux façons de traiter ça : vérifier APRÈS coup avec un agent de vision (ça
double la consommation — l'image ratée, puis sa vérification, puis sa
regénération), ou corriger la cause AVANT, en texte seul. Cet agent fait le
second choix : aucun appel image, juste une relecture technique qui
remplace ce qui ne marche jamais par un équivalent qui garde le même sens.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from typing import Any

from pdz.agents.base import Agent
from pdz.moteur.erreurs import ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.production.storyboard import PlanScript
from pdz.univers import Univers


class RealismWriter(Agent):
    nom = "realisme"
    version = "1.0.0"
    prompt_ref = "ecriture/realisme"

    def variables(self, entrees: dict[str, Any], ctx: Contexte) -> dict[str, Any]:
        univers: Univers = entrees["univers"]
        plans: list[PlanScript] = entrees["plans"]
        return {
            "contexte_univers": univers.contexte_script(),
            "plans": [{"numero": p.numero, "prompt_image": p.action} for p in plans],
        }

    def schema(self, base: dict, entrees: dict[str, Any], ctx: Contexte) -> dict:
        """Impose un prompt corrigé par plan — même raison que `minItems`
        chez ShotPromptWriter : un plan sans réponse garderait son prompt
        d'origine sans qu'on le sache, silencieusement."""
        schema = copy.deepcopy(base)
        schema["properties"]["plans"]["minItems"] = len(entrees["plans"])
        return schema

    def apres(self, sortie: dict, entrees: dict, ctx: Contexte) -> dict:
        plans_ecrits = sortie.get("plans", [])
        attendus = {p.numero for p in entrees["plans"]}
        obtenus = {p.get("numero") for p in plans_ecrits}
        manquants = attendus - obtenus
        if manquants:
            raise ErreurValidation(
                f"Prompts corrigés manquants pour les plans "
                f"{sorted(manquants)} — il en faut un par plan, "
                f"{len(attendus)} au total."
            )
        return sortie

    def fusionner(self, plans: list[PlanScript], sortie: dict) -> list[PlanScript]:
        """Remplace `action` par le prompt corrigé, plan par plan.

        Un plan dont le numéro n'a pas de correction correspondante — ne
        devrait plus arriver après `apres()`, mais un appelant qui saute la
        validation ne doit pas planter pour autant — garde son prompt
        d'origine plutôt que de perdre toute description.
        """
        par_numero = {p["numero"]: p["prompt_image"] for p in sortie.get("plans", [])}
        return [
            replace(p, action=par_numero[p.numero]) if p.numero in par_numero else p
            for p in plans
        ]
