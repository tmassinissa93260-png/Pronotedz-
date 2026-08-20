"""Ce plan est-il FABRICABLE ? — avant de dépenser pour l'apprendre.

`HIGH` / `MEDIUM` / `LOW` est une estimation de **faisabilité technique**.
Ce n'est PAS une note esthétique : « difficile à fabriquer » et « sera moche »
sont deux jugements sans rapport, et les mélanger dans un score unique est
exactement ce que ce système refuse (voir `Faisabilite` dans les contrats).

Le dépôt en avait déjà la moitié : `risque_prompt.py` filtre, sans aucun
appel IA, les prompts qui demandent ce qu'un modèle d'image rate toujours
(texte lisible, logo, visage interdit). Ce paquet garde ce filtre comme
validation statique et lui ajoute ce qui manquait — l'estimation de
complexité, et la décision de décomposer.

── Ce que `LOW` déclenche ───────────────────────────────────────────────

Jamais un abandon. Un plan `LOW` part en décomposition (`pdz/renderability/
decomposition.py`) ou change de stratégie. Le refuser sans alternative
supprimerait des plans que le récit exige.
"""

from pdz.renderability.analyse import (
    SEUIL_DECOMPOSITION,
    Complexite,
    analyser,
    valider_statiquement,
)
from pdz.renderability.decomposition import decomposer, doit_decomposer

__all__ = [
    "analyser", "Complexite", "SEUIL_DECOMPOSITION", "valider_statiquement",
    "decomposer", "doit_decomposer",
]
