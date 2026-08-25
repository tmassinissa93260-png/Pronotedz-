"""Conception sonore : les évènements décidés, et ce qu'on peut en faire.

`ShotSpec.audio_events` était produit par la grammaire de plans — une
ponctuation d'impact sur la chute, un souffle sur une opposition, une ambiance
quand le mouvement le porte — validé par le contrat, puis jeté. Aucune piste
sonore n'en portait la trace, et rien ne disait pourquoi.

Ce module donne à ces décisions un aboutissement honnête. Il ne fabrique aucun
son : il place les évènements sur la timeline de l'épisode, cherche une source
réelle pour chacun, et **déclare** ceux qui n'en ont pas.

    ÉVÈNEMENT DÉCIDÉ → SOURCE CHERCHÉE → RÉSOLU ou DÉCLARÉ MANQUANT

Dans cet environnement, aucune bibliothèque sonore n'est disponible : tous les
repères ressortent `UNRESOLVED`, et c'est ce que le journal de production
rapporte. Le jour où des sons réels seront branchés, le seul changement sera
qu'une source répondra — la chaîne, elle, est déjà écrite.
"""

from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import Field, model_validator

from pdz2.contracts.base import Contract, Element, contract
from pdz2.contracts.enums import AudioEventKind

__all__ = ["CueState", "AudioCue", "AudioDesign"]


class CueState(str, Enum):
    """Ce qu'on sait faire de ce repère sonore."""

    RESOLVED = "resolved"
    """Une source réelle existe et sera montée."""

    UNRESOLVED = "unresolved"
    """Aucune source : le repère est décidé mais restera silencieux."""

    REFUSED = "refused"
    """Le repère ne tient pas dans le plan : il est écarté, avec sa raison."""


class AudioCue(Element):
    """Un évènement sonore placé sur la timeline de l'épisode."""

    shot_id: str = Field(min_length=1)
    kind: AudioEventKind
    timeline_at_s: float = Field(ge=0.0)
    """Instant absolu dans l'épisode, dérivé du créneau du plan."""

    duration_s: float = Field(gt=0.0)
    gain_db: float = Field(default=0.0, ge=-60.0, le=12.0)
    hint: str = ""
    state: CueState
    source_path: str | None = None
    detail: str = ""

    @model_validator(mode="after")
    def _a_resolved_cue_has_a_source(self) -> Self:
        if self.state is CueState.RESOLVED and not self.source_path:
            raise ValueError(
                f"{self.shot_id}/{self.kind.value} : déclaré résolu sans source — "
                "un repère sans fichier ne se monte pas"
            )
        if self.state is not CueState.RESOLVED and self.source_path:
            raise ValueError(
                f"{self.shot_id}/{self.kind.value} : source renseignée sur un "
                f"repère {self.state.value}"
            )
        if self.state is not CueState.RESOLVED and not self.detail.strip():
            raise ValueError(
                f"{self.shot_id}/{self.kind.value} : {self.state.value} sans "
                "raison — un repère muet doit dire pourquoi"
            )
        return self


@contract("audio_design", "1.0.0")
class AudioDesign(Contract):
    """Tous les repères sonores de l'épisode, résolus ou déclarés muets."""

    episode_id: str = Field(min_length=1)
    shot_graph_id: str = Field(min_length=1)
    total_duration_s: float = Field(gt=0.0)
    cues: list[AudioCue] = Field(default_factory=list)
    library: str = Field(default="", max_length=200)
    """Bibliothèque interrogée. Vide : aucune n'était disponible."""

    @model_validator(mode="after")
    def _cues_fit_inside_the_episode(self) -> Self:
        for cue in self.cues:
            if cue.timeline_at_s + cue.duration_s > self.total_duration_s + 0.05:
                raise ValueError(
                    f"{cue.shot_id}/{cue.kind.value} : repère hors de l'épisode "
                    f"({cue.timeline_at_s + cue.duration_s:.3f}s pour "
                    f"{self.total_duration_s:.3f}s)"
                )
        return self

    @property
    def resolved(self) -> list[AudioCue]:
        return [cue for cue in self.cues if cue.state is CueState.RESOLVED]

    @property
    def unresolved(self) -> list[AudioCue]:
        return [cue for cue in self.cues if cue.state is CueState.UNRESOLVED]

    @property
    def silent(self) -> bool:
        """Vrai quand aucun repère n'a de source : l'épisode reste sans habillage."""
        return not self.resolved
