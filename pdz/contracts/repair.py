"""Comment réparer — une hypothèse de cause, pas une relance de plus.

L'interdit du module tient en une ligne : **une nouvelle tentative sans
changement de cause probable n'est pas une réparation.** Relancer trois fois
le même appel avec les mêmes paramètres coûte trois fois le prix pour le même
résultat ; c'est ce que `retry 1 / retry 2 / retry 3` produit, et c'est ce que
ce contrat remplace.

Chaque branche est évaluée sur quatre axes — succès attendu, coût, latence,
risque — et le choix est TRACÉ. Sans la trace, on ne saura jamais si la
réparation choisie était la bonne, et `ExperienceMemory` n'aura rien à
apprendre.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from pdz.contracts.base import Contrat
from pdz.contracts.communs import utilite_esperee


class TypeReparation(str, Enum):
    """Du moins cher au plus cher — l'ordre a un sens, il guide l'arbitrage."""

    RECOMPILER_PROMPT = "PROMPT_FIX"
    AJUSTER_MOUVEMENT = "MOTION_FIX"
    AJUSTER_CAMERA = "CAMERA_FIX"
    RENFORCER_ANCRE = "ANCHOR_FIX"
    # Ne refaire QUE la région fautive, sous masque, en gardant le contexte
    # temporel. Jamais régénérer un plan entier quand ceci est possible.
    REPARATION_LOCALE = "LOCAL_REPAIR"
    CHANGER_STRATEGIE = "STRATEGY_FIX"
    CHANGER_BACKEND = "MODEL_FIX"
    DECOMPOSER = "DECOMPOSITION"
    # Accepter le plan tel quel. Une décision légitime : un plan secondaire
    # imparfait peut coûter moins cher qu'une réparation, et il faut pouvoir
    # le dire explicitement plutôt que d'abandonner en silence.
    ACCEPTER = "ACCEPT"
    # Rendre la main. Ni un échec ni un abandon — voir `Verdict.INCERTAIN`.
    DEMANDER_HUMAIN = "ASK_HUMAN"


class Branche(BaseModel):
    """Une réparation envisagée, avec ce qu'elle coûterait et ce qu'elle vaut."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: TypeReparation
    description: str = ""
    # 0..1 — estimé par règles au départ, par `ExperienceMemory` plus tard.
    # Jamais mesuré tant qu'aucune donnée n'existe : la valeur par défaut
    # 0 dit « on ne sait pas », et non « ça ne marchera pas ».
    succes_attendu: float = 0.0
    cout_eur: float = 0.0
    latence_ms: int = 0
    # Le risque d'AGGRAVER. Une réparation peut casser ce qui marchait —
    # changer de backend peut résoudre le mouvement et perdre l'identité.
    risque: float = 0.0
    parametres: dict[str, str] = Field(default_factory=dict)

    def utilite(self, valeur_du_plan_eur: float) -> float:
        """Le gain espéré de cette réparation, en euros.

        Voir `utilite_esperee` : un ratio « succès par euro » ferait gagner
        `ACCEPTER` contre toute réparation, y compris gratuite — l'erreur
        exacte commise puis corrigée ici.
        """
        return utilite_esperee(self.succes_attendu, self.cout_eur,
                               valeur_du_plan_eur, self.risque)


class RepairPlan(Contrat):
    VERSION = "1.0.0"

    shot_id: str = ""
    diagnostic: str = ""            # l'id du FailureDiagnosis
    branches: tuple[Branche, ...] = ()
    choisie: TypeReparation | None = None
    # Pourquoi cette branche et pas une autre. Écrit à la décision, pas
    # reconstruit après coup — un choix dont on a perdu la raison ne peut
    # être ni contesté, ni appris.
    raison: str = ""
    tentative: int = 1
    tentatives_max: int = 3

    def meilleure(self, valeur_du_plan_eur: float = 1.0) -> Branche | None:
        """La branche au meilleur gain espéré pour ce que ce plan vaut.

        Une méthode et non une propriété : le classement DÉPEND de la valeur
        du plan. Une propriété sans argument obligerait à figer cette valeur,
        et c'est précisément ce qui a produit le bug d'`ACCEPTER`.
        """
        return max(self.branches,
                   key=lambda b: b.utilite(valeur_du_plan_eur), default=None)

    @property
    def epuise(self) -> bool:
        return self.tentative >= self.tentatives_max
