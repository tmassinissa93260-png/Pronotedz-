"""COMMENT fabriquer un plan — jamais AVEC QUEL moteur.

La distinction est tout le sujet. `2.5D` peut être rendu par le module local
`pdz/video/vie.py` comme par un service tiers ; `DIRECT_I2V` par n'importe
quel fournisseur image→vidéo. Les confondre est ce qui a produit la cascade
en dur de `animation.py` :

    modèle payant  →  si échec, `vie`  →  si échec, `camera`

Trois stratégies, en `if/else`, sans jamais avoir été nommées. Impossible
d'arbitrer coût/risque/latence, ni d'ajouter `START_END_FRAME` ou
`MASKED_EDIT` sans toucher au cœur.

── Ce que ce paquet ajoute, et qui manquait ─────────────────────────────

Chaque stratégie déclare ce qu'elle EXIGE, ce qu'elle COÛTE, et surtout ce
qu'elle GARANTIT. Cette dernière propriété est la plus utile et n'existait
nulle part : le repli local produit un mouvement **certain** (c'est du
calcul), là où un modèle image→vidéo produit un mouvement **espéré** — le
run #66 a mesuré un clip payé, valide, de la bonne durée, et parfaitement
statique.

Un système qui ignore cette différence paie un modèle pour obtenir moins
qu'un traitement gratuit.
"""

from pdz.strategies.base import (
    Candidate,
    ContexteRendu,
    ResultatStrategie,
    StrategieRendu,
)
from pdz.strategies.graphe import candidates, choisir, executer
from pdz.strategies.locales import (
    StrategieDirectI2V,
    StrategieImageFixe,
    StrategieProcedurale,
    StrategieTwoPointFiveD,
)

__all__ = [
    "StrategieRendu", "ContexteRendu", "ResultatStrategie", "Candidate",
    "StrategieDirectI2V", "StrategieTwoPointFiveD", "StrategieProcedurale",
    "StrategieImageFixe",
    "candidates", "choisir", "executer",
]
