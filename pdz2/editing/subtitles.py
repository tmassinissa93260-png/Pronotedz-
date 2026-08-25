"""Compilation des sous-titres, calés sur la voix mesurée.

Un sous-titre se pose sur un segment de `VoiceTimeline` — donc sur de l'audio
réellement mesuré, jamais sur une estimation. Les répliques trop longues pour
une ligne sont découpées en plusieurs cartons, au **temps proportionnel au
nombre de caractères** : c'est une approximation, et elle est dite.

Le calage à la syllabe demanderait des timings de mots, qui ne sont pas
mesurés (voir la limite déclarée en phase 2). Un aligneur approximatif
produirait des sous-titres faux avec l'air d'être justes.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field

from pdz2.contracts.delivery import SubtitleCue, SubtitleTrack
from pdz2.contracts.script import ScriptState, VoiceTimeline
from pdz2.contracts.visual import Typography

__all__ = ["SubtitleCompiler", "SubtitleOutcome", "SubtitleRejected", "to_srt"]

MIN_CUE_S = 0.7
"""Durée minimale d'un carton : en deçà, il n'est pas lu."""


class SubtitleRejected(ValueError):
    """Les sous-titres ne peuvent pas être calés sur cette voix."""


@dataclass
class SubtitleOutcome:
    track: SubtitleTrack
    notes: list[str] = field(default_factory=list)


@dataclass
class SubtitleCompiler:
    def compile(
        self,
        *,
        script: ScriptState,
        voice_timeline: VoiceTimeline,
        typography: Typography,
    ) -> SubtitleOutcome:
        if voice_timeline.script_state_id != script.id:
            raise SubtitleRejected("la voix ne décrit pas ce script")

        by_index = {line.index: line for line in script.lines}
        cues: list[SubtitleCue] = []
        split_count = 0

        for segment in voice_timeline.segments:
            line = by_index.get(segment.line_index)
            if line is None:
                raise SubtitleRejected(
                    f"segment {segment.line_index} sans réplique"
                )
            chunks = textwrap.wrap(
                line.text,
                width=typography.max_chars_per_line * 2,
                break_long_words=False,
            ) or [line.text]
            if len(chunks) > 1:
                split_count += 1
            total_chars = sum(len(chunk) for chunk in chunks) or 1
            cursor = segment.start_s
            for position, chunk in enumerate(chunks):
                share = len(chunk) / total_chars
                span = segment.duration_s * share
                end = (
                    segment.end_s
                    if position == len(chunks) - 1
                    else cursor + span
                )
                cues.append(
                    SubtitleCue(
                        index=len(cues),
                        text=chunk,
                        start_s=round(cursor, 3),
                        end_s=round(max(end, cursor + 0.05), 3),
                    )
                )
                cursor = end

        short = sum(1 for cue in cues if cue.end_s - cue.start_s < MIN_CUE_S)
        track = SubtitleTrack(
            voice_timeline_id=voice_timeline.id,
            language=script.language,
            cues=cues,
            max_chars_per_line=typography.max_chars_per_line,
            parent_id=voice_timeline.id,
        )
        notes = [
            f"{len(cues)} cartons calés sur la voix mesurée",
            f"{split_count} réplique(s) découpée(s) en plusieurs cartons",
        ]
        if short:
            notes.append(
                f"{short} carton(s) sous {MIN_CUE_S:g}s : à peine lisibles — le "
                "calage à la syllabe exigerait des timings de mots, non mesurés"
            )
        return SubtitleOutcome(track=track, notes=notes)


def to_srt(track: SubtitleTrack) -> str:
    """Rend la piste au format SRT, lisible par n'importe quel lecteur."""
    blocks = []
    for cue in track.cues:
        blocks.append(
            f"{cue.index + 1}\n"
            f"{_timestamp(cue.start_s)} --> {_timestamp(cue.end_s)}\n"
            f"{cue.text}\n"
        )
    return "\n".join(blocks)


def _timestamp(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
