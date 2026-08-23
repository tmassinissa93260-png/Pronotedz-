"""Narration : du script au dossier d'audio mesuré.

Une réplique, un fichier. C'est ce qui rend le découpage exact : la durée
d'un segment est la durée de *son* fichier, mesurée sur ses trames — jamais
une part d'un total réparti au prorata.

Ce module orchestre, il ne mesure ni ne synthétise lui-même : il appelle le
port de synthèse, puis le mesureur, et refuse dès qu'un des deux se plaint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pdz2.audio.errors import AudioFormatMismatch, SynthesiserUnavailable
from pdz2.audio.ports import SpeechSynthesiser, VoiceSpec
from pdz2.audio.timeline import MeasuredLine
from pdz2.audio.wave_io import measure_wav, require_audible
from pdz2.contracts.script import ScriptState

__all__ = ["NarrationRecorder", "NarrationOutcome"]


@dataclass
class NarrationOutcome:
    lines: list[MeasuredLine]
    notes: list[str] = field(default_factory=list)
    total_latency_s: float = 0.0

    @property
    def spoken_duration_s(self) -> float:
        """Somme des durées mesurées, hors silences d'assemblage."""
        return round(sum(item.duration_s for item in self.lines), 6)


@dataclass
class NarrationRecorder:
    synthesiser: SpeechSynthesiser
    voice: VoiceSpec

    def record(self, *, script: ScriptState, into: Path) -> NarrationOutcome:
        capability = self.synthesiser.get_capabilities()
        if not capability.usable:
            raise SynthesiserUnavailable(
                f"{capability.provider} : {capability.detail} — "
                "aucune voix ne peut être produite, et rien ne le contourne"
            )

        directory = Path(into)
        directory.mkdir(parents=True, exist_ok=True)
        measured: list[MeasuredLine] = []
        latency = 0.0
        reference_format = None

        for line in script.lines:
            target = directory / f"line-{line.index:03d}.wav"
            result = self.synthesiser.synthesise(line.text, self.voice, target)
            measurement = require_audible(
                measure_wav(result.path), f"réplique {line.index}"
            )
            if reference_format is None:
                reference_format = measurement.format
            elif measurement.format != reference_format:
                raise AudioFormatMismatch(
                    f"réplique {line.index} en {measurement.format} contre "
                    f"{reference_format} pour la première — le moteur a changé "
                    "de format en cours de route"
                )
            latency += result.latency_s
            measured.append(
                MeasuredLine(
                    line=line,
                    audio_path=result.path,
                    measurement=measurement,
                    engine=result.engine,
                    engine_version=result.engine_version,
                    voice_fingerprint=result.voice.fingerprint(),
                    latency_s=result.latency_s,
                )
            )

        spoken = sum(item.duration_s for item in measured)
        return NarrationOutcome(
            lines=measured,
            total_latency_s=round(latency, 4),
            notes=[
                f"{len(measured)} répliques synthétisées par "
                f"{measured[0].engine} {measured[0].engine_version}",
                f"voix {self.voice.fingerprint()}",
                f"{spoken:.2f}s de parole MESURÉE sur {len(measured)} fichiers",
            ],
        )
