"""Ce qu'une stratégie de rendu doit savoir dire d'elle-même."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from pdz.contracts.communs import utilite_esperee
from pdz.contracts.render import Strategie


@dataclass(frozen=True)
class ContexteRendu:
    """Tout ce dont une stratégie a besoin pour se prononcer, puis agir."""

    shot_id: str
    image: Path
    destination: Path
    duree_s: float
    prompt: str = ""
    profil: str = "equilibre"
    budget_restant_eur: float = 0.0
    job_id: str = ""
    # Ce que ce plan pèse dans le récit (0..1). Alimente l'arbitrage
    # coût/valeur : un plan critique mérite qu'on tente le coûteux, un plan
    # secondaire non. `animation.noter()` en est déjà la première version.
    importance: float = 0.0
    index: int = 0
    # CE QUE LE PLAN EXIGE — la dimension sans laquelle aucun arbitrage
    # honnête n'est possible. « confiance par euro » seul rendrait le gratuit
    # imbattable, et le modèle payant ne serait jamais choisi : mathématique-
    # ment cohérent, et faux. La parallaxe locale ne peut pas INVENTER un
    # mouvement de sujet — elle fait bouger ce qui est déjà dans l'image. Un
    # personnage qui tourne la tête, elle ne sait pas.
    #
    #   "sujet"       le sujet doit agir      → seul un modèle génératif sait
    #   "ambiance"    la scène doit respirer  → la parallaxe suffit, et garantit
    #   "camera"      seule la caméra bouge   → le procédural suffit, et garantit
    #   ""            rien de particulier
    #
    # Vient du `MotionProgram` en aval (PHASE 9). Vide par défaut : un plan
    # qui n'exige rien ne doit pas faire dépenser.
    mouvement_attendu: str = ""


@dataclass
class ResultatStrategie:
    """Ce qu'une stratégie a produit, et ce que ça a réellement coûté."""

    fichier: Path
    strategie: Strategie
    cout_eur: float = 0.0
    latence_ms: int = 0
    # Vrai quand un vrai fichier vidéo a été produit. Faux pour `IMAGE_FIXE`
    # et `PROCEDURAL` : là, c'est le MONTAGE qui fera bouger l'image, il n'y
    # a pas de clip à ce stade. La distinction compte pour le montage en
    # aval, qui ne traite pas les deux pareil.
    clip_produit: bool = True
    diagnostic: str = ""
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Candidate:
    """Une stratégie envisagée pour un plan, avec ce qu'elle vaut ici."""

    strategie: Strategie
    cout_eur: float
    latence_ms: int
    # 0..1 — la probabilité que le mouvement demandé soit RÉELLEMENT là.
    # Pas une estimation de beauté : une estimation de faisabilité.
    confiance: float
    # Le mouvement est-il GARANTI ou seulement espéré ? Un calcul local
    # garantit ; un modèle génératif espère. Le run #66 a mesuré un clip
    # payé, valide, de la bonne durée et parfaitement statique.
    garanti: bool
    raison: str = ""

    def utilite(self, valeur_du_plan_eur: float) -> float:
        """Le gain espéré, en euros — voir `utilite_esperee`.

        La première version calculait « confiance par euro ». Le modèle
        génératif n'aurait jamais été choisi, y compris sur un plan qu'il est
        seul à savoir rendre. Le compilateur de réparation a commis la MÊME
        erreur de son côté : d'où une formule unique, partagée, dans le
        vocabulaire commun — un seul endroit à relire, un seul à remplacer.

        `valeur_du_plan_eur` est ce qu'on accepterait de payer pour que CE
        plan soit réussi. C'est le même arbitrage que
        `animation.combien_animer()` faisait déjà pour décider COMBIEN de
        plans animer — appliqué ici au CHOIX de la stratégie.
        """
        # Une stratégie n'aggrave rien : elle produit ou non ce qu'on
        # attend. Le risque d'aggravation appartient aux réparations, qui
        # remplacent un résultat DÉJÀ obtenu.
        return utilite_esperee(self.confiance, self.cout_eur, valeur_du_plan_eur)


@runtime_checkable
class StrategieRendu(Protocol):
    """Une façon de fabriquer un plan.

    `evaluer()` doit être GRATUIT et sans effet de bord : c'est ce qui permet
    de comparer dix stratégies avant d'en exécuter une. Une stratégie dont
    l'évaluation coûterait de l'argent rendrait l'arbitrage plus cher que le
    rendu.
    """

    nom: Strategie

    def evaluer(self, contexte: ContexteRendu) -> Candidate | None:
        """La candidature de cette stratégie, ou `None` si elle ne s'applique
        pas ici. `None` n'est pas un échec : une stratégie qui refuse un plan
        hors de son domaine fait exactement son travail."""
        ...

    def executer(self, contexte: ContexteRendu) -> ResultatStrategie: ...
