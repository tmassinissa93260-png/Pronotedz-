"""Sonde de capacités : ce que cet environnement sait vraiment faire.

Le §14 pose une règle qui a l'air pédante et qui ne l'est pas :

    ANNOUNCED ≠ MEASURED ≠ UNKNOWN

La matrice ne recopie donc aucune brochure. Elle **sonde** : elle cherche les
binaires, lit leur version, et — quand on le lui demande — les fait réellement
travailler pour chronométrer ce qu'ils rendent. Tout ce qui n'a pas été
vérifié ici reste `UNKNOWN`, sans valeur chiffrée, et le gouverneur de coût
refusera de dépenser dessus.

Une remarque sur le coût des outils locaux. `cost_per_second_usd = 0` y est
enregistré comme MEASURED, et c'est exact : il n'y a ni compte, ni jeton, ni
facturation — la sonde constate un binaire local, pas un service distant. Le
temps machine, lui, n'est pas nul : c'est ce que mesure `encode_fps`.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from pdz2.audio.espeak import EspeakSynthesiser
from pdz2.audio.ports import VoiceSpec
from pdz2.audio.wave_io import measure_wav
from pdz2.contracts.capability import ProviderCapability
from pdz2.contracts.capacity import (
    CapabilityEntry,
    CapabilityMatrix,
    CapacityValue,
    Provenance,
)
from pdz2.providers.video import NO_VIDEO_PROVIDERS
from pdz2.renderers.deterministic import SUPPORTED_STRATEGIES
from pdz2.renderers.ffmpeg import encode_raw_frames, ffmpeg_capability, probe_video

__all__ = ["CapabilityProbe", "ProbeOutcome", "COST_PER_SECOND"]

COST_PER_SECOND = "cost_per_second_usd"
"""Nom de la capacité que le gouverneur de coût exige avant d'autoriser."""

ENCODE_FPS = "encode_fps"
SPEECH_REALTIME_RATIO = "speech_realtime_ratio"

_MEASURE_WIDTH = 320
_MEASURE_HEIGHT = 180
_MEASURE_FRAMES = 60
_MEASURE_FPS = 30
_MEASURE_SENTENCE = (
    "Une phrase de calibrage, lue à voix haute, pour chronométrer la synthèse."
)

_LOCAL_TOOL_METHOD = (
    "binaire local sondé sur le PATH : aucun compte, aucun jeton, aucune "
    "facturation — le coût monétaire est nul, le coût machine ne l'est pas"
)


@dataclass
class ProbeOutcome:
    matrix: CapabilityMatrix
    capabilities: list[ProviderCapability] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class CapabilityProbe:
    """Interroge l'environnement réel et en tire une matrice datée."""

    measure: bool = False
    """Faire réellement travailler les outils pour chronométrer leur débit.

    Sans cela, la matrice sait qu'un outil existe et ce qu'il coûte ; elle ne
    sait pas encore à quelle vitesse il rend. Deux niveaux de connaissance,
    tous deux honnêtes, jamais confondus.
    """

    def run(self) -> ProbeOutcome:
        notes: list[str] = []
        capabilities: list[ProviderCapability] = []
        entries: list[CapabilityEntry] = []

        video = self._ffmpeg(notes)
        capabilities.append(video[0])
        entries.append(video[1])

        speech = self._espeak(notes)
        capabilities.append(speech[0])
        entries.append(speech[1])

        entries.extend(self._declared_video_providers(capabilities, notes))

        matrix = CapabilityMatrix(entries=entries)
        stale = matrix.stale_values()
        if stale:
            notes.append(
                f"{len(stale)} capacité(s) périmée(s) : à re-mesurer avant d'y compter"
            )
        unknown = sum(
            1
            for entry in entries
            for value in entry.values
            if value.provenance is not Provenance.MEASURED
        )
        notes.append(
            f"{len(entries)} entrée(s), "
            f"{sum(len(e.values) for e in entries) - unknown} capacité(s) mesurée(s), "
            f"{unknown} non mesurée(s)"
        )
        return ProbeOutcome(matrix=matrix, capabilities=capabilities, notes=notes)

    # ------------------------------------------------------------------ ffmpeg

    def _ffmpeg(self, notes: list[str]) -> tuple[ProviderCapability, CapabilityEntry]:
        capability = ffmpeg_capability()
        strategies = sorted(SUPPORTED_STRATEGIES, key=lambda item: item.value)
        if not capability.usable:
            notes.append(f"ffmpeg injoignable : {capability.detail}")
            return capability, CapabilityEntry(
                provider="ffmpeg",
                model="libx264",
                strategies=strategies,
                values=[
                    CapacityValue(name=COST_PER_SECOND, provenance=Provenance.UNKNOWN),
                    CapacityValue(name=ENCODE_FPS, provenance=Provenance.UNKNOWN),
                ],
                notes=capability.detail,
            )

        now = datetime.now(UTC)
        values = [
            CapacityValue(
                name=COST_PER_SECOND,
                value=0.0,
                unit="USD/s",
                provenance=Provenance.MEASURED,
                measured_at=now,
                method=_LOCAL_TOOL_METHOD,
            )
        ]
        if self.measure:
            values.append(self._measure_encoding(notes))
        else:
            values.append(
                CapacityValue(name=ENCODE_FPS, provenance=Provenance.UNKNOWN)
            )
            notes.append(
                "débit d'encodage non mesuré : relancer avec --measure pour le chiffrer"
            )
        return capability, CapabilityEntry(
            provider="ffmpeg",
            model="libx264",
            strategies=strategies,
            values=values,
            notes=capability.detail,
        )

    @staticmethod
    def _measure_encoding(notes: list[str]) -> CapacityValue:
        """Encode réellement un court plan et chronomètre le résultat."""
        frame = bytes(_MEASURE_WIDTH * _MEASURE_HEIGHT * 3)
        with TemporaryDirectory(prefix="pdz2-probe-") as directory:
            out = Path(directory) / "probe.mp4"
            started = time.monotonic()
            try:
                encode_raw_frames(
                    frames=(frame for _ in range(_MEASURE_FRAMES)),
                    width=_MEASURE_WIDTH,
                    height=_MEASURE_HEIGHT,
                    fps=_MEASURE_FPS,
                    out_path=out,
                )
            except Exception as error:  # noqa: BLE001 — la sonde ne doit pas tomber
                notes.append(f"mesure d'encodage impossible : {error}")
                return CapacityValue(name=ENCODE_FPS, provenance=Provenance.UNKNOWN)
            elapsed = time.monotonic() - started
            written = probe_video(out)
        if elapsed <= 0 or written.frame_count <= 0:
            return CapacityValue(name=ENCODE_FPS, provenance=Provenance.UNKNOWN)
        notes.append(
            f"encodage mesuré : {written.frame_count} images "
            f"{_MEASURE_WIDTH}×{_MEASURE_HEIGHT} en {elapsed:.2f}s"
        )
        return CapacityValue(
            name=ENCODE_FPS,
            value=round(written.frame_count / elapsed, 3),
            unit="images/s",
            provenance=Provenance.MEASURED,
            measured_at=datetime.now(UTC),
            method=(
                f"{written.frame_count} images {_MEASURE_WIDTH}×{_MEASURE_HEIGHT} "
                f"RGB brutes encodées en H.264, images relues par ffprobe"
            ),
        )

    # -------------------------------------------------------------- espeak-ng

    def _espeak(self, notes: list[str]) -> tuple[ProviderCapability, CapabilityEntry]:
        synthesiser = EspeakSynthesiser()
        capability = synthesiser.get_capabilities()
        if not capability.usable:
            notes.append(f"eSpeak NG injoignable : {capability.detail}")
            return capability, CapabilityEntry(
                provider="espeak-ng",
                model="fr",
                values=[
                    CapacityValue(name=COST_PER_SECOND, provenance=Provenance.UNKNOWN),
                    CapacityValue(
                        name=SPEECH_REALTIME_RATIO, provenance=Provenance.UNKNOWN
                    ),
                ],
                notes=capability.detail,
            )

        values = [
            CapacityValue(
                name=COST_PER_SECOND,
                value=0.0,
                unit="USD/s",
                provenance=Provenance.MEASURED,
                measured_at=datetime.now(UTC),
                method=_LOCAL_TOOL_METHOD,
            )
        ]
        if self.measure:
            values.append(self._measure_speech(synthesiser, notes))
        else:
            values.append(
                CapacityValue(name=SPEECH_REALTIME_RATIO, provenance=Provenance.UNKNOWN)
            )
        return capability, CapabilityEntry(
            provider="espeak-ng",
            model="fr",
            values=values,
            notes=capability.detail,
        )

    @staticmethod
    def _measure_speech(
        synthesiser: EspeakSynthesiser, notes: list[str]
    ) -> CapacityValue:
        """Synthétise vraiment une phrase et compare audio produit / temps passé."""
        with TemporaryDirectory(prefix="pdz2-probe-") as directory:
            out = Path(directory) / "probe.wav"
            try:
                result = synthesiser.synthesise(
                    _MEASURE_SENTENCE, VoiceSpec(voice_id="fr"), out
                )
                measured = measure_wav(out)
            except Exception as error:  # noqa: BLE001 — la sonde ne doit pas tomber
                notes.append(f"mesure de synthèse impossible : {error}")
                return CapacityValue(
                    name=SPEECH_REALTIME_RATIO, provenance=Provenance.UNKNOWN
                )
            audio_s = measured.duration_s
            latency = result.latency_s
        if latency <= 0 or audio_s <= 0:
            return CapacityValue(
                name=SPEECH_REALTIME_RATIO, provenance=Provenance.UNKNOWN
            )
        notes.append(
            f"synthèse mesurée : {audio_s:.2f}s d'audio en {latency:.3f}s"
        )
        return CapacityValue(
            name=SPEECH_REALTIME_RATIO,
            value=round(audio_s / latency, 3),
            unit="s audio / s machine",
            provenance=Provenance.MEASURED,
            measured_at=datetime.now(UTC),
            method=(
                f"phrase de calibrage de {len(_MEASURE_SENTENCE)} caractères "
                "synthétisée, durée lue sur les trames du WAV"
            ),
        )

    # ------------------------------------------------------- fournisseurs vidéo

    @staticmethod
    def _declared_video_providers(
        capabilities: list[ProviderCapability], notes: list[str]
    ) -> list[CapabilityEntry]:
        """Sonde les adaptateurs vidéo réellement déclarés — aujourd'hui aucun.

        Le chemin de code existe et sera emprunté dès qu'un adaptateur sera
        branché. Inventer une entrée pour un fournisseur absent reviendrait à
        recopier une brochure, ce que cette matrice existe pour empêcher.
        """
        entries: list[CapabilityEntry] = []
        for provider in NO_VIDEO_PROVIDERS:
            declared = provider.get_capabilities()
            capabilities.append(declared.capability)
            entries.append(
                CapabilityEntry(
                    provider=declared.capability.provider,
                    model=getattr(provider, "model", "inconnu"),
                    strategies=list(declared.strategies),
                    values=_video_values(declared),
                    notes=declared.capability.detail,
                )
            )
        if not entries:
            notes.append(
                "aucun adaptateur vidéo déclaré : la matrice n'en invente pas — "
                "les stratégies déterministes locales sont le seul chemin réel"
            )
        return entries


def _video_values(declared) -> list[CapacityValue]:
    """Traduit une capacité d'adaptateur vidéo en valeurs datées.

    Le coût annoncé par un adaptateur reste `ANNOUNCED` tant que personne ne
    l'a facturé et relevé : c'est exactement ce que le gouverneur refusera.
    """
    if declared.cost_per_second_usd is None:
        return [CapacityValue(name=COST_PER_SECOND, provenance=Provenance.UNKNOWN)]
    return [
        CapacityValue(
            name=COST_PER_SECOND,
            value=declared.cost_per_second_usd,
            unit="USD/s",
            provenance=Provenance.ANNOUNCED,
        )
    ]


def which(binary: str) -> str | None:
    """Exposé pour les tests : localise un binaire sans deviner."""
    return shutil.which(binary)


def tool_versions() -> list[str]:
    """Versions réelles des outils système, pour le journal de production."""
    versions: list[str] = []
    for binary, argv in (("ffmpeg", ["-version"]), ("espeak-ng", ["--version"])):
        path = shutil.which(binary)
        if path is None:
            versions.append(f"{binary} : absent")
            continue
        try:
            run = subprocess.run(
                [binary, *argv], capture_output=True, text=True, timeout=10, check=False
            )
        except (OSError, subprocess.SubprocessError) as error:
            versions.append(f"{binary} : injoignable ({error})")
            continue
        first = (run.stdout or run.stderr or "").splitlines()
        versions.append(f"{binary} : {first[0].strip() if first else 'version illisible'}")
    return versions
