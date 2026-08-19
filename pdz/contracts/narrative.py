"""Le pendant fiction de `ResearchState` — ce qui tient le récit debout.

Une fiction n'a pas de sources : elle a des personnages qui veulent quelque
chose, un conflit, des règles de monde qu'elle s'interdit d'enfreindre. Ces
objets-là jouent, pour la mise en scène, exactement le rôle que jouent les
claims dans l'explicatif : ils disent ce qui doit être montré et pourquoi.

Les deux profils convergent ensuite sur le même `DirectorState`. C'est là que
la divergence s'arrête — et elle s'arrête AVANT le compilateur, ce qui est
tout l'intérêt de la décision (voir docs/GAP_ANALYSIS.md § 1).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from pdz.contracts.base import Contrat


class Personnage(BaseModel):
    """Vue MISE EN SCÈNE d'un personnage — pas sa fiche d'univers.

    `pdz.univers.Personnage` porte l'apparence, la voix, l'espèce : ce qui
    sert à le FABRIQUER. Ici on porte ce qui sert à le RACONTER. Fusionner
    les deux ferait dépendre les contrats de l'univers, donc du métier, ce
    que la règle d'import interdit — et pour une bonne raison : un même
    personnage peut être mis en scène de dix façons sans changer d'apparence.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    role: str = ""              # « protagoniste », « antagoniste »…
    objectif: str = ""
    obstacle: str = ""


class Evenement(BaseModel):
    """Ce qui se passe, et ce que ça change."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    description: str
    acteurs: tuple[str, ...] = ()
    consequence: str = ""


class NarrativeState(Contrat):
    """Ce que la fiction pose comme vrai, dans son propre monde."""

    VERSION = "1.0.0"

    situation: str = ""
    personnages: tuple[Personnage, ...] = ()
    conflit: str = ""
    evenements: tuple[Evenement, ...] = ()
    # Ce que l'univers s'interdit — « aucun visage humain net », « pas de
    # texte lisible ». Contraintes de MONDE, pas de rendu : elles valent
    # même si le fournisseur savait parfaitement les rendre.
    regles_du_monde: tuple[str, ...] = ()

    def par_id(self, personnage_id: str) -> Personnage | None:
        return next((p for p in self.personnages if p.id == personnage_id), None)
