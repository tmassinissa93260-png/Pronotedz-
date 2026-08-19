"""Ce que le système CROIT SAVOIR du sujet — et à quel titre.

N'existe que pour le profil explicatif. Le pendant fiction est
`NarrativeState` (voir `pdz/contracts/narrative.py`) : demander ses sources
à « Strawberina trahit Bananito » produirait un graphe vide de sens sur la
totalité des productions actuelles du dépôt.

La règle qui gouverne ce module : **une information incertaine ne devient
jamais certaine.** Ni parce qu'un modèle l'a reformulée avec assurance, ni
parce qu'elle est pratique pour le récit, ni parce qu'aucune source ne la
contredit — l'absence de contradiction n'est pas une preuve.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from pdz.contracts.base import Contrat
from pdz.contracts.communs import Certitude


class Source(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str = ""
    titre: str = ""
    editeur: str = ""
    date: str = ""              # ISO si connue, vide sinon — jamais devinée
    extrait: str = ""


class Claim(BaseModel):
    """Une affirmation, avec ce qui la soutient et ce qui la limite."""

    model_config = ConfigDict(extra="forbid")

    id: str
    enonce: str
    certitude: Certitude = Certitude.INCONNU
    # 0..1. N'a de sens QUE lue avec `certitude` : une confiance de 0,9 sur
    # un `HEURISTIQUE` reste un heuristique. Le nombre ne promeut jamais le
    # statut — c'est l'erreur exacte que ce contrat existe pour empêcher.
    confiance: float = 0.0
    sources: tuple[Source, ...] = ()
    # Les identifiants d'autres claims qui CONTREDISENT celui-ci. Non vide
    # = le système sait qu'il y a désaccord, et doit le dire plutôt que de
    # choisir en silence.
    conflits: tuple[str, ...] = ()
    # « actuel » | « date » | « obsolete » | "" si on ne sait pas. Une
    # information vraie en 2019 et fausse aujourd'hui n'est pas une erreur
    # de source, c'est une propriété de l'information.
    statut_temporel: str = ""
    # Peut-on le MONTRER ? Un claim invisualisable peut être vrai et n'avoir
    # aucune place dans une vidéo — c'est une décision de mise en scène,
    # pas de véracité, et les deux ne doivent pas se contaminer.
    visualisabilite: float = 0.0

    @property
    def utilisable_comme_fait(self) -> bool:
        """Affirmable à l'écran sans réserve.

        Exige une source ET un statut fiable : un `FAIT` sans source est une
        contradiction dans les termes, et le laisser passer viderait toute
        la distinction de son sens.
        """
        return self.certitude.est_fiable and bool(self.sources) and not self.conflits


class ResearchState(Contrat):
    """Le graphe de connaissance d'un sujet explicatif."""

    VERSION = "1.0.0"

    sujet: str = ""
    claims: tuple[Claim, ...] = ()
    # Ce que la recherche n'a PAS trouvé. Vide n'est pas « rien ne manque » :
    # c'est « on n'a pas cherché à savoir ce qui manque ». Les deux méritent
    # d'être distinguables, d'où un champ explicite.
    lacunes: tuple[str, ...] = ()
    requetes: tuple[str, ...] = Field(default_factory=tuple)

    def par_id(self, claim_id: str) -> Claim | None:
        return next((c for c in self.claims if c.id == claim_id), None)

    @property
    def contradictions(self) -> tuple[Claim, ...]:
        return tuple(c for c in self.claims if c.conflits)

    @property
    def affirmables(self) -> tuple[Claim, ...]:
        return tuple(c for c in self.claims if c.utilisable_comme_fait)
