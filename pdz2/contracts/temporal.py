"""Plan temporel : le découpage du temps **mesuré** en créneaux de plan.

Le Temporal Director produit ce contrat à partir du `DirectorState` et de la
`VoiceTimeline`. Toutes ses durées viennent de la timeline mesurée ; aucune
durée théorique n'y entre.

Règle de recouvrement, explicite et vérifiée par le contrat : **les créneaux
pavent exactement l'audio**. Pas de trou, pas de chevauchement, et le dernier
finit sur la dernière trame. Un fondu enchaîné se déclare *à l'intérieur* de
la durée d'un plan (le contrat `ShotSpec` le vérifie), il ne déborde jamais
sur le créneau voisin — sans quoi la somme des plans cesserait d'égaler la
durée de l'audio, et le montage n'aurait plus de vérité à laquelle se tenir.

Les quatre courbes dérivées sont des **cibles**, pas des mesures. Elles disent
ce que le rendu devra viser ; l'observateur déterministe (phase 8) dira ce
qu'il a réellement obtenu. Chaque règle de dérivation est nommée et documentée
dans `pdz2.engines.temporal.curves`.
"""

from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import Field, model_validator

from pdz2.contracts.base import Contract, Element, contract
from pdz2.contracts.common import Curve

__all__ = [
    "SAMPLE_PRECISION",
    "SlotOrigin",
    "ShotSlot",
    "sample_position",
    "RhythmFindingKind",
    "RhythmFinding",
    "TemporalPlan",
    "TILING_TOLERANCE_S",
]

TILING_TOLERANCE_S = 0.002
"""Tolérance de pavage, en secondes. Une trame à 22 050 Hz dure 45 µs."""

SAMPLE_PRECISION = 6
"""Décimales de la position normalisée d'un créneau sur la courbe.

Les courbes sont échantillonnées au milieu de chaque créneau. Relire une
courbe à cette même position doit rendre **exactement** la valeur stockée, et
non une interpolation entre deux points voisins : à 10⁻⁷ près, une cible de
mouvement de 0,30 devient 0,2999998 et la caméra se verrouille en silence.
L'échantillonnage et la lecture arrondissent donc au même rang.
"""


class SlotOrigin(str, Enum):
    VOICE_SEGMENT = "voice_segment"
    """Un créneau pour une réplique : le cas normal."""

    SPLIT = "split"
    """Part d'une réplique trop longue pour tenir en un seul plan."""


class ShotSlot(Element):
    """Fenêtre temporelle d'un plan, découpée dans l'audio mesuré."""

    shot_id: str = Field(min_length=1)
    line_id: str = Field(min_length=1)
    line_index: int = Field(ge=0)
    part: int = Field(default=0, ge=0)
    part_count: int = Field(default=1, ge=1)
    origin: SlotOrigin = SlotOrigin.VOICE_SEGMENT

    start_s: float = Field(ge=0.0)
    end_s: float = Field(gt=0.0)
    speech_start_s: float = Field(ge=0.0)
    speech_end_s: float = Field(gt=0.0)
    """Bornes de la parole dans le créneau. Le reste est le silence qui suit."""

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if self.end_s <= self.start_s:
            raise ValueError(f"{self.shot_id} : créneau à l'envers")
        if self.speech_end_s <= self.speech_start_s:
            raise ValueError(f"{self.shot_id} : parole à l'envers")
        if self.speech_start_s < self.start_s - TILING_TOLERANCE_S:
            raise ValueError(f"{self.shot_id} : la parole commence avant le créneau")
        if self.speech_end_s > self.end_s + TILING_TOLERANCE_S:
            raise ValueError(f"{self.shot_id} : la parole déborde du créneau")
        if self.part >= self.part_count:
            raise ValueError(
                f"{self.shot_id} : part {self.part} sur {self.part_count} parts"
            )
        if self.part_count > 1 and self.origin is not SlotOrigin.SPLIT:
            raise ValueError(f"{self.shot_id} : réplique découpée sans origine 'split'")
        return self

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    @property
    def speech_duration_s(self) -> float:
        return self.speech_end_s - self.speech_start_s


def sample_position(slot: ShotSlot, total_duration_s: float) -> float:
    """Position normalisée du milieu d'un créneau. Une seule définition.

    Échantillonnage et lecture passent par cette fonction : c'est ce qui
    garantit qu'ils tombent sur la même valeur.
    """
    middle = (slot.start_s + slot.duration_s / 2) / total_duration_s
    return round(min(1.0, middle), SAMPLE_PRECISION)


class RhythmFindingKind(str, Enum):
    """Ce que le Temporal Director constate sans le corriger en silence."""

    SHOT_TOO_SHORT = "shot_too_short"
    SHOT_SPLIT = "shot_split"
    MONOTONOUS_CADENCE = "monotonous_cadence"
    DENSITY_SATURATED = "density_saturated"
    VISUAL_REPETITION = "visual_repetition"
    ATTENTION_TROUGH = "attention_trough"


class RhythmFinding(Element):
    kind: RhythmFindingKind
    shot_id: str | None = None
    detail: str = Field(min_length=1)
    measured: float | None = None
    threshold: float | None = None


@contract("temporal_plan", "1.0.0")
class TemporalPlan(Contract):
    """Découpage temporel et courbes cibles, dérivés de l'audio mesuré."""

    director_state_id: str = Field(min_length=1)
    voice_timeline_id: str = Field(min_length=1)
    total_duration_s: float = Field(gt=0.0)
    """Reprise exacte de la durée mesurée de la `VoiceTimeline`."""

    slots: list[ShotSlot] = Field(min_length=1)

    emotional_curve: Curve
    """Décision du Director, ré-échantillonnée sur le temps mesuré."""

    attention_curve: Curve
    information_curve: Curve
    motion_curve: Curve
    visual_novelty_curve: Curve
    findings: list[RhythmFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def _slots_tile_the_audio_exactly(self) -> Self:
        ids = [slot.shot_id for slot in self.slots]
        if len(set(ids)) != len(ids):
            raise ValueError("plan temporel : shot_id en double")

        cursor = 0.0
        for slot in self.slots:
            if abs(slot.start_s - cursor) > TILING_TOLERANCE_S:
                raise ValueError(
                    f"{slot.shot_id} : commence à {slot.start_s:.4f}s alors que le "
                    f"créneau précédent finit à {cursor:.4f}s — les plans doivent "
                    "paver l'audio sans trou ni chevauchement"
                )
            cursor = slot.end_s
        if abs(cursor - self.total_duration_s) > TILING_TOLERANCE_S:
            raise ValueError(
                f"les créneaux couvrent {cursor:.4f}s pour un audio de "
                f"{self.total_duration_s:.4f}s"
            )
        return self

    @model_validator(mode="after")
    def _curves_are_named_as_expected(self) -> Self:
        expected = {
            "emotional": self.emotional_curve,
            "attention": self.attention_curve,
            "information": self.information_curve,
            "motion": self.motion_curve,
            "visual_novelty": self.visual_novelty_curve,
        }
        wrong = [
            f"{name} nommée {curve.name!r}"
            for name, curve in expected.items()
            if curve.name != name
        ]
        if wrong:
            raise ValueError(f"courbes mal nommées : {wrong}")
        return self

    def slot(self, shot_id: str) -> ShotSlot:
        for item in self.slots:
            if item.shot_id == shot_id:
                return item
        raise KeyError(shot_id)

    def position_of(self, shot_id: str) -> float:
        """Position normalisée du milieu du créneau, dans [0, 1].

        Arrondie au même rang que l'échantillonnage des courbes, pour que la
        lecture retombe sur le point stocké au lieu d'interpoler.
        """
        return sample_position(self.slot(shot_id), self.total_duration_s)

    def targets_for(self, shot_id: str) -> dict[str, float]:
        """Valeurs des courbes au milieu du créneau. Lecture, pas décision."""
        position = self.position_of(shot_id)
        return {
            "emotional": self.emotional_curve.value_at(position),
            "attention": self.attention_curve.value_at(position),
            "information": self.information_curve.value_at(position),
            "motion": self.motion_curve.value_at(position),
            "visual_novelty": self.visual_novelty_curve.value_at(position),
        }
