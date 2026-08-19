"""La chronologie officielle de la production.

**C'est le contrat le plus important du système**, et le seul dont le dépôt
avait déjà entièrement raison : la durée d'un plan vient de la parole
RÉELLEMENT prononcée, jamais d'une estimation. `pdz/production/voix.py`
recale les timings ElevenLabs mot à mot sur la piste complète, et
`storyboard.point_de_coupe()` place la coupe sur une vraie pause mesurée.

Ce contrat ne change rien à ce mécanisme. Il lui donne une forme typée, et
ajoute les pistes que le système ne remplit pas encore (musique, ambiance,
SFX) — déclarées vides plutôt qu'absentes, pour que leur absence soit une
information et non un oubli.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from pdz.contracts.base import Contrat


class Mot(BaseModel):
    """Un mot, daté sur la piste COMPLÈTE — pas sur son fichier d'origine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    texte: str
    debut_ms: int
    fin_ms: int

    @property
    def duree_ms(self) -> int:
        return self.fin_ms - self.debut_ms


class Replique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numero: int
    personnage: str
    texte: str
    debut_ms: int = 0
    duree_ms: int = 0
    mots: tuple[Mot, ...] = ()
    # Le claim (explicatif) ou l'événement (fiction) que cette ligne porte.
    porte: str = ""
    emotion: str = ""
    relance: bool = False

    @property
    def fin_ms(self) -> int:
        return self.debut_ms + self.duree_ms


class EvenementAudio(BaseModel):
    """Un son ponctuel, RATTACHÉ à ce qui le cause.

    `cause` est l'identifiant d'un maillon causal ou d'un mouvement — pas
    une description textuelle. C'est ce qui distingue un bruitage motivé
    d'un bruitage d'ambiance choisi par ressemblance de vocabulaire.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    debut_ms: int
    description: str = ""
    cause: str = ""
    piste: str = "sfx"          # sfx | ambiance | musique


class AudioTimeline(Contrat):
    """La bande son complète, et la référence de temps de tout le reste."""

    VERSION = "1.0.0"

    fichier_voix: str = ""
    duree_ms: int = 0
    repliques: tuple[Replique, ...] = ()
    # Vides tant que le système ne les produit pas. Le champ existe pour que
    # « pas de musique » soit lisible comme une décision plutôt que comme
    # une couche oubliée.
    evenements: tuple[EvenementAudio, ...] = Field(default_factory=tuple)
    fichier_musique: str = ""
    fichier_ambiance: str = ""
    # Vrai quand la voix n'a pas pu être synthétisée et qu'une piste
    # silencieuse de la bonne durée la remplace. Le dépôt gère déjà ce mode
    # (voir `voix.py`) ; le porter ici évite qu'un aval le prenne pour une
    # vraie voix.
    muet: bool = False

    @property
    def mots(self) -> tuple[Mot, ...]:
        return tuple(m for r in self.repliques for m in r.mots)

    @property
    def durees_repliques_s(self) -> tuple[float, ...]:
        return tuple(r.duree_ms / 1000 for r in self.repliques)

    @property
    def debuts_de_replique_ms(self) -> frozenset[int]:
        """Les frontières que les sous-titres ne doivent jamais enjamber :
        une carte à cheval mêle les paroles de deux personnages."""
        return frozenset(r.mots[0].debut_ms for r in self.repliques if r.mots)
