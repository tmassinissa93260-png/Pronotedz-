"""Réparer, c'est changer la cause probable — pas relancer.

L'interdit du paquet tient en une ligne : **une nouvelle tentative sans
changement de cause probable n'est pas une réparation.** Relancer trois fois
le même appel avec les mêmes paramètres coûte trois fois le prix pour le même
résultat. C'est ce que `retry 1 / retry 2 / retry 3` produit, et c'est ce que
ce paquet remplace.

    FailureDiagnosis  →  branches possibles  →  arbitrage  →  RepairPlan

Chaque branche est évaluée sur quatre axes — succès attendu, coût, latence,
risque — et le choix est **tracé**. Sans la trace, on ne saura jamais si la
réparation choisie était la bonne, et `ExperienceMemory` n'aura rien à
apprendre.
"""

from pdz.repair.compilateur import CATALOGUE, PAR_CAUSE, branches_pour, compiler

__all__ = ["compiler", "branches_pour", "CATALOGUE", "PAR_CAUSE"]
