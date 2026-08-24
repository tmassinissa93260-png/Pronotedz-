"""Script et timeline de voix.

RÈGLE VOICE FIRST : la timeline officielle vient du TTS réellement produit.
`ScriptLine.estimated_duration_s` n'est qu'une estimation ; une `VoiceTimeline`
dont la source de timing n'est pas mesurée est refusée par le contrat.
"""

from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import Field, model_validator

from pdz2.contracts.base import Contract, Element, contract
from pdz2.contracts.enums import Emotion, NarrativeFunction

__all__ = [
    "TimingSource",
    "ScriptLine",
    "ScriptState",
    "WordTiming",
    "VoiceSegment",
    "VoiceTimeline",
]


class TimingSource(str, Enum):
    """Origine d'une durée."""

    ESTIMATED = "estimated"
    """Comptage de mots. Interdit dans une VoiceTimeline."""

    MEASURED_TTS = "measured_tts"
    """Mesuré sur l'audio rendu par le moteur de synthèse."""

    MEASURED_FILE = "measured_file"
    """Mesuré sur un fichier audio fourni."""


MEASURED_SOURCES = frozenset({TimingSource.MEASURED_TTS, TimingSource.MEASURED_FILE})


@contract("script_line", "1.0.0")
class ScriptLine(Contract):
    index: int = Field(ge=0)
    text: str = Field(min_length=1)
    function: NarrativeFunction
    emotion: Emotion = Emotion.NEUTRAL
    energy: float = Field(default=0.5, ge=0.0, le=1.0)
    emphasis_words: list[str] = Field(default_factory=list)
    visual_requirement: str = Field(min_length=1)
    claim_id: str | None = None
    shot_intent_order: int | None = Field(default=None, ge=0)

    estimated_duration_s: float = Field(gt=0.0)
    """Estimation seulement. La durée officielle vient du TTS réel."""

    @model_validator(mode="after")
    def _emphasis_is_in_the_text(self) -> Self:
        lowered = self.text.lower()
        missing = [word for word in self.emphasis_words if word.lower() not in lowered]
        if missing:
            raise ValueError(
                f"réplique {self.index} : mots à accentuer absents du texte {missing}"
            )
        return self


@contract("script_state", "1.0.0")
class ScriptState(Contract):
    director_state_id: str = Field(min_length=1)
    language: str = Field(default="fr", min_length=2, max_length=8)
    lines: list[ScriptLine] = Field(min_length=1)

    @model_validator(mode="after")
    def _lines_are_ordered(self) -> Self:
        indexes = [line.index for line in self.lines]
        if indexes != list(range(len(indexes))):
            raise ValueError(f"répliques non contiguës depuis 0 : {indexes}")
        return self

    @property
    def estimated_total_s(self) -> float:
        """Somme des estimations. Jamais utilisée pour découper la timeline."""
        return sum(line.estimated_duration_s for line in self.lines)

    def line(self, index: int) -> ScriptLine:
        return self.lines[index]


class WordTiming(Element):
    word: str = Field(min_length=1)
    start_s: float = Field(ge=0.0)
    end_s: float = Field(gt=0.0)

    @model_validator(mode="after")
    def _forward(self) -> Self:
        if self.end_s <= self.start_s:
            raise ValueError(f"mot {self.word!r} : fin avant début")
        return self


class VoiceSegment(Element):
    """Portion d'audio réellement occupée par une réplique."""

    line_id: str = Field(min_length=1)
    line_index: int = Field(ge=0)
    start_s: float = Field(ge=0.0)
    end_s: float = Field(gt=0.0)
    words: list[WordTiming] = Field(default_factory=list)

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if self.end_s <= self.start_s:
            raise ValueError(f"segment {self.line_index} : fin avant début")
        for word in self.words:
            if word.start_s < self.start_s - 1e-6 or word.end_s > self.end_s + 1e-6:
                raise ValueError(
                    f"segment {self.line_index} : mot {word.word!r} hors du segment"
                )
        return self

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


@contract("voice_timeline", "1.0.0")
class VoiceTimeline(Contract):
    """Vérité temporelle de l'épisode, mesurée sur l'audio réel."""

    script_state_id: str = Field(min_length=1)
    audio_path: str = Field(min_length=1)
    sample_rate: int = Field(gt=0)
    total_duration_s: float = Field(gt=0.0)
    timing_source: TimingSource
    segments: list[VoiceSegment] = Field(min_length=1)
    voice_id: str | None = None
    engine: str | None = None
    """Moteur ayant produit l'audio. Renseigné par l'exécution, pas par le Director."""

    @model_validator(mode="after")
    def _voice_first(self) -> Self:
        if self.timing_source not in MEASURED_SOURCES:
            raise ValueError(
                "VOICE FIRST : une timeline de voix se mesure sur l'audio réel, "
                f"pas sur une estimation (timing_source={self.timing_source.value})"
            )
        return self

    @model_validator(mode="after")
    def _segments_are_a_partition(self) -> Self:
        previous_end = 0.0
        seen_indexes: list[int] = []
        for segment in self.segments:
            if segment.start_s < previous_end - 1e-6:
                raise ValueError(
                    f"segment {segment.line_index} : chevauche le précédent"
                )
            if segment.end_s > self.total_duration_s + 1e-6:
                raise ValueError(
                    f"segment {segment.line_index} : dépasse la durée totale"
                )
            previous_end = segment.end_s
            seen_indexes.append(segment.line_index)
        if seen_indexes != sorted(seen_indexes):
            raise ValueError("segments de voix dans le désordre")
        if len(set(seen_indexes)) != len(seen_indexes):
            raise ValueError("deux segments pour la même réplique")
        return self

    def segment_for_line(self, line_index: int) -> VoiceSegment:
        for segment in self.segments:
            if segment.line_index == line_index:
                return segment
        raise KeyError(line_index)

    @property
    def speech_duration_s(self) -> float:
        return sum(segment.duration_s for segment in self.segments)


class DurationDecision(str, Enum):
    """Ce que le compilateur a décidé face à la durée commandée."""

    NO_TARGET = "no_target"
    """Aucune durée commandée : rien à tenir."""

    ON_TARGET = "on_target"
    """Le débit habituel tombe déjà dans la tolérance."""

    RATE_ADJUSTED = "rate_adjusted"
    """Le débit a été ajusté, dans la bande naturelle, pour tenir la commande."""

    CONTENT_TOO_SHORT = "content_too_short"
    """La commande exigerait un débit sous la bande : il manque du contenu."""

    CONTENT_TOO_LONG = "content_too_long"
    """La commande exigerait un débit au-dessus de la bande : il y a trop de texte."""


@contract("duration_policy", "1.0.0")
class DurationPolicy(Contract):
    """Décision de compilation sur la durée, adossée à une mesure réelle.

    Quatre grandeurs que rien ne doit confondre, et que ce contrat sépare :

        requested_s    ce qui a été commandé          — une intention
        calibrated_s   ce que ce texte dure vraiment  — une MESURE
        tolerance      l'écart acceptable             — une règle
        decision       ce que le compilateur en fait  — un choix assumé

    La durée estimée du script n'apparaît pas ici, et c'est délibéré : elle
    n'entre dans aucune décision. `calibrated_s` sort d'une synthèse réellement
    exécutée au débit de référence, puis mesurée sur les trames du WAV. Le
    débit retenu s'en déduit, et la durée officielle restera celle que
    `VoiceTimeline` mesurera sur l'audio définitif.

    Ce contrat existe parce que l'incohérence était silencieuse : un épisode
    commandé à 40 s en livrait 27,4 sans qu'aucune décision ne soit prise ni
    inscrite nulle part.
    """

    script_state_id: str = Field(min_length=1)
    requested_s: float | None = Field(default=None, gt=0.0)
    calibrated_s: float = Field(gt=0.0)
    """Durée mesurée d'une synthèse réelle au débit de référence."""

    calibration_rate_wpm: int = Field(gt=0)
    chosen_rate_wpm: int = Field(gt=0)
    """Débit que la synthèse définitive doit employer."""

    tolerance: float = Field(default=0.15, ge=0.0, le=1.0)
    decision: DurationDecision
    rationale: str = Field(min_length=1)
    projected_s: float = Field(gt=0.0)
    """Durée attendue au débit retenu. Projection, jamais une autorité."""

    @model_validator(mode="after")
    def _the_decision_matches_its_numbers(self) -> Self:
        if self.decision is DurationDecision.NO_TARGET:
            if self.requested_s is not None:
                raise ValueError("NO_TARGET avec une durée commandée")
            return self
        if self.requested_s is None:
            raise ValueError(f"{self.decision.value} sans durée commandée")
        if self.decision is DurationDecision.ON_TARGET:
            if self.chosen_rate_wpm != self.calibration_rate_wpm:
                raise ValueError(
                    "ON_TARGET mais le débit a bougé : c'est un ajustement"
                )
        if self.decision is DurationDecision.RATE_ADJUSTED:
            ecart = abs(self.projected_s - self.requested_s) / self.requested_s
            if ecart > self.tolerance + 1e-9:
                raise ValueError(
                    f"RATE_ADJUSTED mais la projection reste à {ecart:.0%} "
                    f"de la commande, au-delà de {self.tolerance:.0%} — "
                    "la cible n'est pas atteinte, la décision doit le dire"
                )
        return self

    @property
    def within_tolerance(self) -> bool:
        if self.requested_s is None:
            return True
        return abs(self.projected_s - self.requested_s) <= self.requested_s * self.tolerance
