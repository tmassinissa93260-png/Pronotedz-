"""L'agent qui transforme une phrase en squelette narratif.

Une phrase seule (« un homme entre dans une pièce sombre... ») laisse le
scénariste inventer sa propre structure à chaque fois, avec une variance
énorme sur un modèle plus faible (Llama) : trop de temps forts entassés, ou
une ligne droite sans relance. BriefWriter fait un seul travail, avant que
la moindre réplique soit écrite : découper le sujet en temps forts (hook,
mise en place, tension, payoff...). C'est exactement le squelette
`beats` que `ScriptWriter` sait déjà lire (voir SQUELETTE NARRATIF dans
ecriture/script.yaml) — rien ne le remplissait automatiquement jusqu'ici.
"""

from __future__ import annotations

import copy
from typing import Any

from pdz.agents.base import Agent, nb_beats_pour
from pdz.moteur.erreurs import ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.univers import Univers


class BriefWriter(Agent):
    nom = "brief"
    version = "1.0.0"
    prompt_ref = "ecriture/brief"

    def variables(self, entrees: dict[str, Any], ctx: Contexte) -> dict[str, Any]:
        univers: Univers = entrees["univers"]
        duree = entrees.get("duree_s") or univers.duree_cible_s
        return {
            "situation": entrees["situation"],
            "contexte_univers": univers.contexte_script(),
            "duree_s": duree,
            "nb_beats": nb_beats_pour(duree),
        }

    def schema(self, base: dict, entrees: dict[str, Any], ctx: Contexte) -> dict:
        """Impose le nombre de temps forts, au lieu de le suggérer en texte
        libre — même raison que `minItems` sur les répliques du script
        (voir ScriptWriter.schema) : un nombre laissé au texte seul n'est
        pas fiable avec Llama."""
        univers: Univers = entrees["univers"]
        duree = entrees.get("duree_s") or univers.duree_cible_s
        schema = copy.deepcopy(base)
        schema["properties"]["beats"]["minItems"] = nb_beats_pour(duree)
        return schema

    def apres(self, sortie: dict, entrees: dict, ctx: Contexte) -> dict:
        beats = sortie.get("beats", [])
        if not beats:
            raise ErreurValidation("Brief vide : aucun temps fort produit.")

        univers: Univers = entrees["univers"]
        duree = entrees.get("duree_s") or univers.duree_cible_s
        attendus = nb_beats_pour(duree)
        if len(beats) < attendus:
            raise ErreurValidation(
                f"Brief incomplet : {len(beats)} temps fort(s) pour {attendus} "
                f"demandés. Ajoute-en, répartis sur toute la durée (position_pct "
                "de 0 à 100), sans changer ceux déjà écrits."
            )

        # Toujours croissant : un squelette narratif qui revient en arrière
        # dans le temps n'a pas de sens pour ScriptWriter, qui le lit dans
        # l'ordre.
        positions = [b.get("position_pct", 0) for b in beats]
        if positions != sorted(positions):
            raise ErreurValidation(
                "Les temps forts doivent être dans l'ordre chronologique "
                "(position_pct croissant du premier au dernier)."
            )
        return sortie
