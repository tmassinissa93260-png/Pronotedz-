"""Le contrat central de mise en scène — là où les deux profils se rejoignent.

`ResearchState` (explicatif) et `NarrativeState` (fiction) produisent chacun
leur matière ; tout ce qui suit dans le compilateur ne connaît plus que le
`DirectorState`. C'est la frontière de la décision prise en
docs/GAP_ANALYSIS.md § 1 : la divergence s'arrête ici, et ce qui vient après
(ShotGraph, RenderSpec, exécution, observation) est écrit une seule fois.

Structuré en sous-états plutôt qu'en un objet de deux cents champs : un
`DirectorState` plat serait illisible, impossible à faire évoluer par
morceaux, et forcerait à versionner l'ensemble pour un changement local.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from pdz.contracts.base import Contrat
from pdz.contracts.communs import Profil


class NarrativeIntention(BaseModel):
    """Ce que la vidéo veut faire, indépendamment de ce qu'elle raconte."""

    model_config = ConfigDict(extra="forbid")

    these: str = ""             # la phrase que le spectateur doit repartir avec
    accroche: str = ""
    payoff: str = ""
    # Les temps forts, dans l'ordre. Le dépôt les appelle déjà « beats »
    # (BriefWriter, `agents/ecriture/brief.py`) — même mot, même sens.
    beats: tuple[str, ...] = ()
    # Les identifiants de claims (explicatif) ou d'événements (fiction) que
    # la vidéo s'engage à porter. Un seul champ pour les deux : à ce niveau,
    # « ce qu'il faut faire passer » a la même forme dans les deux profils.
    points_a_porter: tuple[str, ...] = ()


class EtatSpectateur(BaseModel):
    """Ce que le spectateur est censé savoir, et quand.

    Sans cet état, un plan ne peut pas savoir s'il EXPLIQUE ou s'il RAPPELLE,
    et le montage répète des choses déjà acquises ou en saute d'essentielles.
    """

    model_config = ConfigDict(extra="forbid")

    audience: str = "grand_public"
    # Ce qu'on suppose déjà connu au démarrage. Une supposition, jamais une
    # mesure — et nommée comme telle.
    connaissances_supposees: tuple[str, ...] = ()
    # Étapes T0..T5 : ignorance → question → première explication →
    # mécanisme → compréhension causale → payoff. Chaque entrée dit ce qui
    # doit être acquis à ce palier. Vide = le Director n'a rien planifié,
    # pas « le spectateur ne sait rien ».
    paliers: tuple[str, ...] = ()


class EtatEmotionnel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    courbe: tuple[str, ...] = ()      # une émotion visée par beat
    # Les moments où l'attention doit être rattrapée. Le dépôt les mesure
    # déjà (`relance`, toutes les 15–20 s) — même notion, portée ici comme
    # décision de mise en scène plutôt que comme champ de script.
    relances: tuple[int, ...] = ()


class LangageVisuel(BaseModel):
    """La Visual Bible de cette production précise.

    Hérite de l'univers pour une fiction, du style demandé pour un
    explicatif — mais une fois ici, plus rien en aval n'a besoin de savoir
    d'où ça vient.
    """

    model_config = ConfigDict(extra="forbid")

    registre: str = ""          # le plancher non négociable
    ambiance: str = ""
    palette: tuple[str, ...] = ()
    grammaire_camera: tuple[str, ...] = ()
    interdits: tuple[str, ...] = ()


class Continuite(BaseModel):
    """Ce qui doit rester identique d'un plan au suivant."""

    model_config = ConfigDict(extra="forbid")

    ancres: tuple[str, ...] = ()          # entités dont l'identité est tenue
    decor_courant: str = ""
    # Ce que le système sait ne PAS avoir résolu. Explicite, parce qu'une
    # continuité oubliée et une continuité assumée se ressemblent beaucoup
    # dans un journal, et pas du tout à l'écran.
    non_resolues: tuple[str, ...] = ()


class ContraintesProduction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duree_cible_s: float = 45.0
    budget_max_eur: float = 0.0
    langue: str = "fr"
    plateformes: tuple[str, ...] = ()


class DirectorState(Contrat):
    """Ce qu'il faut raconter, dans quel ordre, avec quel langage.

    Ne contient AUCUN prompt et AUCUN nom de fournisseur : c'est une
    décision de mise en scène, pas une instruction d'exécution. Le jour où
    un champ de ce contrat ressemble à un prompt, c'est que la frontière a
    bougé au mauvais endroit.
    """

    VERSION = "1.0.0"

    profil: Profil = Profil.FICTION
    intention: NarrativeIntention = Field(default_factory=NarrativeIntention)
    spectateur: EtatSpectateur = Field(default_factory=EtatSpectateur)
    emotion: EtatEmotionnel = Field(default_factory=EtatEmotionnel)
    visuel: LangageVisuel = Field(default_factory=LangageVisuel)
    continuite: Continuite = Field(default_factory=Continuite)
    contraintes: ContraintesProduction = Field(default_factory=ContraintesProduction)
