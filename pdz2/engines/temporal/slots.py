"""Découpage du temps mesuré en créneaux de plan.

Une règle, une seule, et elle est arithmétique : **un créneau par réplique,
allant du début de sa parole au début de la parole suivante**. Le dernier
créneau va jusqu'à la dernière trame. Les créneaux pavent donc exactement
l'audio — leur somme *est* la durée mesurée, par construction et pas par
ajustement.

Deux écarts à cette règle, tous deux explicites :

* **Découpe** — une réplique dont le créneau dépasse le plafond de durée du
  rythme est découpée en parts égales. C'est une opération purement
  temporelle : même réplique, même affirmation, plusieurs plans. Rien de
  narratif ne change.

* **Créneau trop court** — il est *constaté*, jamais fusionné avec le voisin.
  Fusionner deux répliques en un plan ferait disparaître un temps visuel
  décidé par la réalisation : ce serait une décision narrative prise en
  silence par le compilateur. Le constat remonte, la réalisation tranche.
"""

from __future__ import annotations

from dataclasses import dataclass

from pdz2.contracts.enums import Pacing
from pdz2.contracts.script import ScriptState, VoiceTimeline
from pdz2.contracts.temporal import (
    RhythmFinding,
    RhythmFindingKind,
    ShotSlot,
    SlotOrigin,
)

__all__ = ["SlotRules", "carve_slots", "SlotCarving"]


@dataclass(frozen=True)
class SlotRules:
    """Bornes de durée d'un plan, par rythme. Reprend celles de la réalisation."""

    bounds: dict[Pacing, tuple[float, float]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.bounds is None:
            from pdz2.engines.direction.rhythm import PACING_SHOT_SECONDS

            object.__setattr__(self, "bounds", dict(PACING_SHOT_SECONDS))

    def floor(self, pacing: Pacing) -> float:
        return self.bounds[pacing][0]

    def ceiling(self, pacing: Pacing) -> float:
        return self.bounds[pacing][1]


@dataclass
class SlotCarving:
    slots: list[ShotSlot]
    findings: list[RhythmFinding]


def carve_slots(
    *,
    timeline: VoiceTimeline,
    script: ScriptState,
    pacing: Pacing,
    rules: SlotRules | None = None,
) -> SlotCarving:
    """Découpe l'audio mesuré en créneaux de plan, sans trou ni chevauchement."""
    rules = rules or SlotRules()
    floor, ceiling = rules.floor(pacing), rules.ceiling(pacing)
    total = timeline.total_duration_s
    segments = list(timeline.segments)
    by_index = {line.index: line for line in script.lines}

    slots: list[ShotSlot] = []
    findings: list[RhythmFinding] = []
    counter = 0

    for position, segment in enumerate(segments):
        line = by_index.get(segment.line_index)
        if line is None:
            raise KeyError(
                f"segment {segment.line_index} sans réplique correspondante"
            )
        window_start = segment.start_s
        window_end = (
            segments[position + 1].start_s if position + 1 < len(segments) else total
        )
        span = window_end - window_start

        parts = 1
        if span > ceiling:
            parts = int(span // ceiling) + (1 if span % ceiling > 1e-9 else 0)
            findings.append(
                RhythmFinding(
                    kind=RhythmFindingKind.SHOT_SPLIT,
                    detail=(
                        f"réplique {line.index} : {span:.2f}s au-delà du plafond "
                        f"{ceiling:g}s du rythme « {pacing.value} », découpée en "
                        f"{parts} plans — même affirmation, plusieurs images"
                    ),
                    measured=round(span, 4),
                    threshold=ceiling,
                )
            )

        step = span / parts
        for part in range(parts):
            start = window_start + part * step
            end = window_end if part == parts - 1 else window_start + (part + 1) * step
            shot_id = f"S{counter:02d}"
            counter += 1
            speech_start = max(segment.start_s, start)
            speech_end = min(segment.end_s, end)
            if speech_end <= speech_start:
                # La part ne contient que du silence : la parole y est réduite à
                # un instant, mais le créneau reste réel et doit être rempli.
                speech_start, speech_end = start, min(end, start + 1e-3)
            slots.append(
                ShotSlot(
                    shot_id=shot_id,
                    line_id=line.id,
                    line_index=line.index,
                    part=part,
                    part_count=parts,
                    origin=SlotOrigin.SPLIT if parts > 1 else SlotOrigin.VOICE_SEGMENT,
                    start_s=round(start, 6),
                    end_s=round(end, 6),
                    speech_start_s=round(speech_start, 6),
                    speech_end_s=round(speech_end, 6),
                )
            )
            if end - start < floor:
                findings.append(
                    RhythmFinding(
                        kind=RhythmFindingKind.SHOT_TOO_SHORT,
                        shot_id=shot_id,
                        detail=(
                            f"{end - start:.2f}s sous le plancher {floor:g}s du "
                            f"rythme « {pacing.value} » — le plan risque d'être "
                            "illisible. Fusionner reviendrait à supprimer un temps "
                            "visuel décidé par la réalisation : c'est à elle de "
                            "trancher, pas au compilateur"
                        ),
                        measured=round(end - start, 4),
                        threshold=floor,
                    )
                )

    if slots:
        slots[-1] = ShotSlot(
            **(slots[-1].model_dump() | {"end_s": round(total, 6)})
        )
    return SlotCarving(slots=slots, findings=findings)
