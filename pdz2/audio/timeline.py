"""Construction de la VoiceTimeline — la source temporelle officielle.

    TTS réel → audio réel → durée mesurée → découpage temporel

Ce module ne connaît pas `estimated_duration_s`. Il ne peut pas : sa seule
entrée temporelle est une liste de `MeasuredLine`, dont chaque durée sort de
`measure_wav`, c'est-à-dire du décompte des trames d'un fichier. Un test
d'architecture vérifie qu'aucun module de `pdz2/audio/` ne mentionne
l'estimation — l'accident est ainsi rendu impossible, pas seulement interdit.

Le découpage est exact par construction : chaque réplique est synthétisée
dans son propre fichier, mesurée, puis les fichiers sont assemblés avec des
silences de durée connue. Les bornes de segment sont donc des sommes de
durées mesurées — jamais une répartition d'un total.

L'assemblage est enfin **re-mesuré** et confronté à la somme attendue. Un
écart signifie qu'un fichier a menti ou qu'un octet s'est perdu : c'est une
`DurationInconsistent`, pas un arrondi qu'on absorbe.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pdz2.audio.errors import DurationInconsistent
from pdz2.audio.wave_io import (
    AudioMeasurement,
    concatenate,
    measure_wav,
    read_wav,
    require_audible,
    silence,
    write_wav,
)
from pdz2.contracts.enums import NarrativeFunction
from pdz2.contracts.script import (
    ScriptLine,
    ScriptState,
    TimingSource,
    VoiceSegment,
    VoiceTimeline,
)

__all__ = [
    "MeasuredLine",
    "VoiceTimelineBuilder",
    "AssembledVoice",
    "FUNCTION_PAUSE_S",
    "ASSEMBLY_TOLERANCE_S",
]

FUNCTION_PAUSE_S: dict[NarrativeFunction, float] = {
    NarrativeFunction.HOOK: 0.45,
    NarrativeFunction.SETUP: 0.30,
    NarrativeFunction.QUESTION: 0.50,
    NarrativeFunction.MECHANISM: 0.30,
    NarrativeFunction.EVIDENCE: 0.30,
    NarrativeFunction.CONTRAST: 0.40,
    NarrativeFunction.CONSEQUENCE: 0.35,
    NarrativeFunction.PAYOFF: 0.00,
    NarrativeFunction.TRANSITION: 0.20,
    NarrativeFunction.CTA: 0.00,
}
"""Silence après une réplique, selon ce qu'elle vient de faire.

Une accroche a besoin qu'on la laisse retomber ; un mécanisme enchaîne. Ces
silences sont *écrits*, donc de durée exacte au nombre d'échantillons près —
ils ne sont pas estimés eux non plus.
"""

ASSEMBLY_TOLERANCE_S = 0.002
"""Écart toléré entre l'assemblage attendu et l'assemblage mesuré.

Une trame à 22 050 Hz dure 45 µs : deux millisecondes couvrent l'arrondi de
l'écriture des silences, et rien de plus.
"""


@dataclass(frozen=True)
class MeasuredLine:
    """Une réplique et l'audio réel qui la dit.

    `measurement` vient de `measure_wav`. Il n'y a pas de champ « durée
    annoncée » : la seule durée disponible est celle du fichier.
    """

    line: ScriptLine
    audio_path: Path
    measurement: AudioMeasurement
    engine: str
    engine_version: str
    voice_fingerprint: str
    latency_s: float = 0.0
    """Temps réellement pris par la synthèse. Mesuré, pour le Cost Governor."""

    @property
    def duration_s(self) -> float:
        return self.measurement.duration_s


@dataclass(frozen=True)
class AssembledVoice:
    """L'audio complet et la timeline qui le décrit."""

    timeline: VoiceTimeline
    audio_path: Path
    measurement: AudioMeasurement
    lines: list[MeasuredLine]

    @property
    def total_duration_s(self) -> float:
        return self.measurement.duration_s


@dataclass
class VoiceTimelineBuilder:
    """Assemble des répliques mesurées en une timeline officielle."""

    tail_silence_s: float = 0.35
    """Silence final, pour que le montage ne coupe pas sur le dernier mot."""

    def build(
        self,
        *,
        script: ScriptState,
        measured: list[MeasuredLine],
        out_path: Path,
    ) -> AssembledVoice:
        self._check_coverage(script, measured)

        fragments = []
        segments: list[VoiceSegment] = []
        cursor = 0.0

        for position, item in enumerate(measured):
            require_audible(item.measurement, f"réplique {item.line.index}")
            fragment = read_wav(item.audio_path)
            fragments.append(fragment)

            start = cursor
            end = start + item.duration_s
            segments.append(
                VoiceSegment(
                    line_id=item.line.id,
                    line_index=item.line.index,
                    start_s=round(start, 6),
                    end_s=round(end, 6),
                    words=[],  # non mesuré : voir la note de phase.
                )
            )
            cursor = end

            pause = self._pause_after(item.line, is_last=position == len(measured) - 1)
            if pause > 0:
                fragments.append(silence(fragment.format, pause))
                cursor += pause

        if self.tail_silence_s > 0:
            fragments.append(silence(fragments[0].format, self.tail_silence_s))
            cursor += self.tail_silence_s

        write_wav(concatenate(fragments), out_path)
        assembled = measure_wav(out_path)

        drift = abs(assembled.duration_s - cursor)
        if drift > ASSEMBLY_TOLERANCE_S:
            raise DurationInconsistent(
                f"assemblage incohérent : {assembled.duration_s:.4f}s mesurées "
                f"contre {cursor:.4f}s attendues (écart {drift * 1000:.1f} ms, "
                f"tolérance {ASSEMBLY_TOLERANCE_S * 1000:.0f} ms)"
            )
        if segments[-1].end_s > assembled.duration_s:
            raise DurationInconsistent(
                f"le dernier segment finit à {segments[-1].end_s:.4f}s, "
                f"au-delà de l'audio mesuré ({assembled.duration_s:.4f}s)"
            )

        engines = {item.engine for item in measured}
        voices = {item.voice_fingerprint for item in measured}
        if len(engines) > 1 or len(voices) > 1:
            raise DurationInconsistent(
                "répliques synthétisées par des moteurs ou des voix différents : "
                f"moteurs={sorted(engines)} voix={sorted(voices)}"
            )

        timeline = VoiceTimeline(
            script_state_id=script.id,
            audio_path=str(out_path),
            sample_rate=assembled.format.sample_rate,
            total_duration_s=round(assembled.duration_s, 6),
            timing_source=TimingSource.MEASURED_TTS,
            segments=segments,
            voice_id=next(iter(voices)),
            engine=f"{next(iter(engines))} {measured[0].engine_version}",
            parent_id=script.id,
        )
        return AssembledVoice(
            timeline=timeline,
            audio_path=Path(out_path),
            measurement=assembled,
            lines=list(measured),
        )

    # ------------------------------------------------------------------ règles

    @staticmethod
    def _check_coverage(script: ScriptState, measured: list[MeasuredLine]) -> None:
        """Une timeline partielle serait pire qu'une absence de timeline."""
        if not measured:
            raise DurationInconsistent("aucune réplique synthétisée")
        indexes = [item.line.index for item in measured]
        if indexes != sorted(indexes):
            raise DurationInconsistent(f"répliques mesurées dans le désordre : {indexes}")
        expected = [line.index for line in script.lines]
        if indexes != expected:
            missing = sorted(set(expected) - set(indexes))
            extra = sorted(set(indexes) - set(expected))
            raise DurationInconsistent(
                "les répliques synthétisées ne couvrent pas le script — "
                f"manquantes {missing}, en trop {extra}"
            )
        known = {line.id for line in script.lines}
        strangers = [item.line.id for item in measured if item.line.id not in known]
        if strangers:
            raise DurationInconsistent(
                f"répliques étrangères à ce script : {strangers}"
            )

    @staticmethod
    def _pause_after(line: ScriptLine, is_last: bool) -> float:
        if is_last:
            return 0.0
        return FUNCTION_PAUSE_S[line.function]
