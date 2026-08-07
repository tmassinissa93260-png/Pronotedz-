"""L'agent qui transforme la forme d'une vidéo en situation à jouer.

Il ne fait qu'une chose, et volontairement une seule : proposer **quoi
raconter** pour épouser une forme déjà mesurée. Tout ce qui est chiffrable —
nombre de répliques, mots par réplique, durée des plans, position des
relances — est calculé dans `pdz.analyse.adn`, sans modèle et sans coût.

La séparation n'est pas cosmétique. Un modèle à qui on demande « combien de
répliques pour 45 secondes à 190 mots/minute ? » répond un nombre plausible
et faux une fois sur trois. Une division ne se trompe jamais.
"""

from __future__ import annotations

from typing import Any

from pdz.agents.base import Agent
from pdz.analyse.adn import Adn
from pdz.moteur.erreurs import ErreurValidation
from pdz.moteur.pipeline import Contexte
from pdz.univers import Univers


class AdnTransfert(Agent):
    nom = "adn"
    version = "1.0.0"
    prompt_ref = "analyse/adn"

    def variables(self, entrees: dict[str, Any], ctx: Contexte) -> dict[str, Any]:
        univers: Univers = entrees["univers"]
        adn: Adn = entrees["adn"]
        return {
            "contexte_univers": univers.contexte_script(),
            "mesures_adn": adn.bloc_pour_prompt(),
            "limites": adn.limites(),
            "sujet_vise": entrees["sujet"],
            "situation_source": entrees.get("situation_source", ""),
        }

    def apres(self, sortie: dict, entrees: dict, ctx: Contexte) -> dict:
        beats = sortie.get("beats") or []
        if len(beats) < 3:
            raise ErreurValidation(
                f"{len(beats)} beat(s) seulement : il en faut au moins une "
                "accroche, une relance et une chute."
            )

        roles = {b["role"] for b in beats}
        if "accroche" not in roles:
            raise ErreurValidation(
                "Aucun beat « accroche ». Les trois premières secondes ne "
                "peuvent pas être laissées au hasard."
            )

        # Un squelette dont tous les beats sont dans la première moitié
        # laisse la fin vide : c'est le défaut le plus courant, et le plus
        # visible à l'écran.
        if beats and max(b["position_pct"] for b in beats) < 70:
            raise ErreurValidation(
                "Le dernier beat tombe avant 70 % de la durée : la fin de la "
                "vidéo n'a rien à jouer. Étale le découpage jusqu'à la chute."
            )

        adn: Adn = entrees["adn"]
        sortie["contraintes"] = adn.contraintes(entrees.get("duree_s"))
        sortie["limites"] = adn.limites()
        return sortie
