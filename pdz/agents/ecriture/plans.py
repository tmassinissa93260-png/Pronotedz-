"""L'agent qui transforme le storyboard déjà découpé en prompts d'image riches.

ScriptWriter écrit le dialogue et une action minimale par réplique — de quoi
savoir ce qui se passe, pas de quoi cadrer une image. Le découpage
(`pdz.production.storyboard`) transforme ensuite ces répliques en PLANS : une
réplique avec réaction en donne deux (celui qui parle, puis celui qui
écoute), et ce second plan n'a jamais reçu qu'une action générique codée en
dur (« reacting to what X just said »).

Cet agent prend le relais UNE FOIS le découpage fait, pas avant : à partir de
ce qui se dit et de la fonction de chaque plan (SHOT_FUNCTION), il écrit un
vrai prompt de cinéaste — cadrage, ce qui est net, ce qui reste dans l'ombre
— un par PLAN, réaction comprise. C'est ce prompt qui remplace `action` avant
la génération d'image.

Le séparer de l'écriture du dialogue n'est pas cosmétique : un modèle qui
répartit son attention entre « qu'est-ce qu'on dit » et « comment on le
filme » en même temps écrit les deux moins bien qu'un modèle qui ne
s'occupe QUE du cadrage, une fois le texte ET le montage déjà là.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import replace
from typing import Any

from pdz.agents.base import Agent
from pdz.moteur.erreurs import ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.production import cadrage, fidelite_visuelle
from pdz.production.continuite import indices_de_scene
from pdz.production.storyboard import PlanScript
from pdz.univers import Univers

log = logging.getLogger(__name__)


class ShotPromptWriter(Agent):
    nom = "shot_prompts"
    version = "2.7.0"
    prompt_ref = "ecriture/plans"

    def variables(self, entrees: dict[str, Any], ctx: Contexte) -> dict[str, Any]:
        univers: Univers = entrees["univers"]
        plans: list[PlanScript] = entrees["plans"]
        repliques_par_numero = {r["numero"]: r for r in entrees["repliques"]}
        # Un changement de décor EST un changement de scène (voir
        # pdz/production/continuite.py) : le premier plan d'une scène doit
        # établir le lieu, les suivants peuvent le supposer déjà connu.
        scenes = indices_de_scene([p.decor for p in plans])
        return {
            "contexte_univers": univers.contexte_script(),
            # En narration, personne n'est jamais montré à l'écran (voix off
            # sur des images de ce dont elle parle) — voir la consigne dans
            # plans@1.6.0.yaml. `univers.anime` distingue ce cas des séries à
            # personnages, où un humain visible est au contraire attendu.
            "anime": univers.anime,
            # ScriptWriter décrit déjà, à chaque script (CONTRAINTE ABSOLUE
            # #7), comment le dernier plan doit boucler avec le premier —
            # jamais lu par aucun agent en aval jusqu'ici (voir l'audit
            # data-flow). Vide sur un job repris d'avant ce champ.
            "derniere_image": entrees.get("derniere_image", ""),
            "plans": [
                {
                    "numero": p.numero,
                    "personnage": p.personnage,
                    "replique": repliques_par_numero.get(p.replique_numero, {}).get("replique", ""),
                    "reaction": p.reaction,
                    "action": p.action,
                    "fonction_plan": p.fonction,
                    "nouvelle_scene": i == 0 or scenes[i] != scenes[i - 1],
                    "dernier": i == len(plans) - 1,
                }
                for i, p in enumerate(plans)
            ],
        }

    def schema(self, base: dict, entrees: dict[str, Any], ctx: Contexte) -> dict:
        """Impose au moins un prompt par plan — y compris les plans de
        réaction, qui n'existent qu'après le découpage et n'ont sinon
        jamais reçu de prompt écrit pour eux."""
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
                f"Prompts d'image manquants pour les plans "
                f"{sorted(manquants)} — il en faut un par plan, "
                f"{len(attendus)} au total."
            )

        # Diagnostic seulement, jamais une relance (voir cadrage.py) : un
        # appel Groq de plus pour ça annulerait justement ce qu'on cherche à
        # réduire cette nuit.
        par_numero = sorted(plans_ecrits, key=lambda p: p["numero"])
        avertissements = cadrage.verifier_diversite(
            [p.get("cadrage", "") for p in par_numero]
        )
        for a in avertissements:
            log.info("Cadrage : %s", a)

        return sortie

    def fusionner(self, plans: list[PlanScript], sortie: dict) -> list[PlanScript]:
        """Remplace `action` et `cadrage` par ceux écrits ici, plan par plan.

        Sépare exprès de `apres()` : `apres()` valide ce que le modèle a
        renvoyé, `fusionner()` l'applique au storyboard. Un plan dont le
        numéro n'a pas de prompt correspondant — ne devrait plus arriver
        après `apres()`, mais un appelant qui saute la validation ne doit
        pas planter pour autant — garde son action d'origine plutôt que de
        perdre toute description.
        """
        par_numero = {p["numero"]: p for p in sortie.get("plans", [])}
        fusionnes = []
        renforces = 0
        for p in plans:
            ecrit = par_numero.get(p.numero)
            if ecrit is None:
                fusionnes.append(p)
                continue
            prompt, manquants = fidelite_visuelle.renforcer(
                ecrit["prompt_image"], ecrit.get("elements_obligatoires", [])
            )
            if manquants:
                renforces += 1
                log.info("Plan %d : élément(s) manquant(s) rajouté(s) — %s",
                         p.numero, ", ".join(manquants))
            prompt = fidelite_visuelle.exclure(
                prompt, ecrit.get("elements_a_exclure", [])
            )
            fusionnes.append(replace(
                p, action=prompt, cadrage=ecrit.get("cadrage", p.cadrage),
                registre_visuel=ecrit.get("registre_visuel", p.registre_visuel),
                elements_obligatoires=ecrit.get("elements_obligatoires", []),
                elements_a_exclure=ecrit.get("elements_a_exclure", []),
                elements_secondaires=ecrit.get("elements_secondaires", []),
                corrections_fidelite=manquants,
            ))
        if renforces:
            log.info("Fidélité visuelle : %d/%d plan(s) complété(s) après coup",
                     renforces, len(fusionnes))
        return fusionnes
