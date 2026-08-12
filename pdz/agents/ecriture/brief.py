"""L'agent qui transforme une phrase en stratégie créative et en squelette narratif.

Une phrase seule (« un homme entre dans une pièce sombre... ») laisse le
scénariste inventer sa propre structure à chaque fois, avec une variance
énorme sur un modèle plus faible (Llama) : trop de temps forts entassés, ou
une ligne droite sans relance. BriefWriter fait deux choses, avant que la
moindre réplique soit écrite :

  1. `strategie` — la direction créative d'ensemble (mécanisme du hook, arc
     narratif, ce qui retient l'attention, un piège à éviter pour CE sujet).
     Un travail longtemps dispersé entre BriefWriter et ScriptWriter, qui
     redécidait implicitement sa propre stratégie à chaque réplique plutôt
     que d'en exécuter une déjà choisie.
  2. `beats` — le squelette narratif (hook, mise en place, tension,
     payoff...) que `ScriptWriter` sait déjà lire (SQUELETTE NARRATIF,
     ecriture/script.yaml).

Quand l'univers porte l'empreinte créative d'une vidéo de référence (voir
`analyse/charte`), elle façonne la stratégie ET le squelette ici — pas
seulement le dialogue plus tard : un mécanisme de hook mesuré sur une
référence doit déjà orienter le TEMPS FORT choisi, pas juste la façon dont
il est raconté.
"""

from __future__ import annotations

import copy
from typing import Any

from pdz.agents.base import Agent, nb_beats_pour, texte_empreinte
from pdz.moteur.erreurs import ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.univers import Univers


class BriefWriter(Agent):
    nom = "brief"
    version = "1.1.0"
    prompt_ref = "ecriture/brief"

    def variables(self, entrees: dict[str, Any], ctx: Contexte) -> dict[str, Any]:
        univers: Univers = entrees["univers"]
        duree = entrees.get("duree_s") or univers.duree_cible_s
        empreinte_texte = ""
        if univers.empreinte_creative is not None:
            empreinte_texte = texte_empreinte(univers.empreinte_creative)
        return {
            "situation": entrees["situation"],
            "contexte_univers": univers.contexte_script(),
            "duree_s": duree,
            "nb_beats": nb_beats_pour(duree),
            "empreinte_texte": empreinte_texte,
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
