"""Lecture, mesure et écriture de WAV — bibliothèque standard seule.

Aucune dépendance : `wave`, `array`, `struct`. La durée d'un fichier se
calcule sur ses **trames**, jamais sur le texte qui l'a produit. C'est le
point d'appui de toute la règle VOICE FIRST : ici, le texte n'existe pas.
"""

from __future__ import annotations

import contextlib
import struct
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path

from pdz2.audio.errors import AudioCorrupt, AudioFormatMismatch, AudioSilent

__all__ = [
    "AudioFormat",
    "AudioMeasurement",
    "PcmAudio",
    "read_wav",
    "measure_wav",
    "write_wav",
    "concatenate",
    "silence",
    "SILENCE_RMS_FLOOR",
]

SILENCE_RMS_FLOOR = 1e-4
"""RMS normalisé en dessous duquel un fragment est considéré muet.

Un moteur de synthèse qui échoue à mi-parcours rend souvent un fichier
parfaitement lisible et parfaitement vide. Sans ce seuil, une telle sortie
passerait pour de la parole et sa durée deviendrait officielle.
"""

_WIDTH_TO_TYPECODE = {1: "b", 2: "h", 4: "i"}


@dataclass(frozen=True)
class AudioFormat:
    sample_rate: int
    channels: int
    sample_width: int
    """Octets par échantillon : 1, 2 ou 4."""

    def __str__(self) -> str:
        return (
            f"{self.sample_rate} Hz / {self.channels} canal(aux) / "
            f"{self.sample_width * 8} bits"
        )

    @property
    def full_scale(self) -> float:
        return float(2 ** (self.sample_width * 8 - 1))


@dataclass(frozen=True)
class PcmAudio:
    """Échantillons décodés, avec leur format."""

    format: AudioFormat
    samples: array

    @property
    def frame_count(self) -> int:
        return len(self.samples) // self.format.channels

    @property
    def duration_s(self) -> float:
        return self.frame_count / self.format.sample_rate


@dataclass(frozen=True)
class AudioMeasurement:
    """Ce qu'on sait d'un fichier audio après l'avoir réellement lu."""

    path: str
    format: AudioFormat
    frame_count: int
    duration_s: float
    peak: float
    """Amplitude crête normalisée dans [0, 1]."""

    rms: float
    """Énergie efficace normalisée dans [0, 1]."""

    leading_silence_s: float
    trailing_silence_s: float
    size_bytes: int

    @property
    def is_silent(self) -> bool:
        return self.rms < SILENCE_RMS_FLOOR

    @property
    def speech_duration_s(self) -> float:
        """Durée hors silences de bord."""
        return max(
            0.0, self.duration_s - self.leading_silence_s - self.trailing_silence_s
        )


def read_wav(path: Path | str) -> PcmAudio:
    """Décode un WAV PCM. Toute anomalie est une erreur, jamais un silence."""
    target = Path(path)
    if not target.is_file():
        raise AudioCorrupt(f"fichier audio absent : {target}")
    try:
        with contextlib.closing(wave.open(str(target), "rb")) as handle:
            channels = handle.getnchannels()
            width = handle.getsampwidth()
            rate = handle.getframerate()
            frames = handle.getnframes()
            raw = handle.readframes(frames)
    except (wave.Error, EOFError, struct.error) as error:
        raise AudioCorrupt(f"{target.name} : WAV illisible ({error})") from error

    if frames == 0 or not raw:
        raise AudioCorrupt(f"{target.name} : aucune trame audio")
    if width not in _WIDTH_TO_TYPECODE:
        raise AudioCorrupt(f"{target.name} : largeur d'échantillon {width} non gérée")
    if rate <= 0 or channels <= 0:
        raise AudioCorrupt(f"{target.name} : format déclaré incohérent")

    samples = array(_WIDTH_TO_TYPECODE[width])
    samples.frombytes(raw[: len(raw) - len(raw) % (width * channels)])
    if samples.itemsize != width:  # pragma: no cover - dépend de la plateforme
        raise AudioCorrupt(f"{target.name} : largeur native inattendue")
    import sys

    if sys.byteorder == "big":  # pragma: no cover - le WAV est petit-boutiste
        samples.byteswap()
    return PcmAudio(
        format=AudioFormat(sample_rate=rate, channels=channels, sample_width=width),
        samples=samples,
    )


def measure_wav(path: Path | str) -> AudioMeasurement:
    """Mesure un fichier audio. Le texte d'origine n'entre pas dans le calcul."""
    target = Path(path)
    audio = read_wav(target)
    scale = audio.format.full_scale
    samples = audio.samples

    peak = max(abs(value) for value in samples) / scale
    total = 0.0
    for value in samples:
        normalised = value / scale
        total += normalised * normalised
    rms = (total / len(samples)) ** 0.5

    leading, trailing = _edge_silences(audio, rms)
    return AudioMeasurement(
        path=str(target),
        format=audio.format,
        frame_count=audio.frame_count,
        duration_s=audio.duration_s,
        peak=round(peak, 6),
        rms=round(rms, 8),
        leading_silence_s=round(leading, 4),
        trailing_silence_s=round(trailing, 4),
        size_bytes=target.stat().st_size,
    )


def _edge_silences(audio: PcmAudio, rms: float) -> tuple[float, float]:
    """Silences de tête et de queue, seuillés relativement à l'énergie du tout."""
    if rms <= 0.0:
        return audio.duration_s, 0.0
    threshold = max(rms * 0.08, 2.0 / audio.format.full_scale)
    scale = audio.format.full_scale
    channels = audio.format.channels
    frames = audio.frame_count
    samples = audio.samples

    def loud(frame: int) -> bool:
        base = frame * channels
        return any(
            abs(samples[base + channel]) / scale >= threshold
            for channel in range(channels)
        )

    first = 0
    while first < frames and not loud(first):
        first += 1
    if first == frames:
        return audio.duration_s, 0.0
    last = frames - 1
    while last > first and not loud(last):
        last -= 1
    rate = audio.format.sample_rate
    return first / rate, (frames - 1 - last) / rate


def require_audible(measurement: AudioMeasurement, label: str) -> AudioMeasurement:
    """Refuse un fragment muet. Un fichier lisible n'est pas un fichier parlant."""
    if measurement.is_silent:
        raise AudioSilent(
            f"{label} : audio muet (rms {measurement.rms:.2e} sous le plancher "
            f"{SILENCE_RMS_FLOOR:.0e}) — la synthèse n'a rien produit d'audible"
        )
    return measurement


def silence(audio_format: AudioFormat, duration_s: float) -> PcmAudio:
    """Fragment silencieux d'une durée exacte, au format demandé."""
    if duration_s < 0:
        raise ValueError("durée de silence négative")
    frames = round(duration_s * audio_format.sample_rate)
    typecode = _WIDTH_TO_TYPECODE[audio_format.sample_width]
    return PcmAudio(
        format=audio_format,
        samples=array(typecode, [0] * (frames * audio_format.channels)),
    )


def concatenate(fragments: list[PcmAudio]) -> PcmAudio:
    """Assemble des fragments de format identique. Un écart est une erreur."""
    if not fragments:
        raise ValueError("aucun fragment à assembler")
    reference = fragments[0].format
    for index, fragment in enumerate(fragments[1:], start=1):
        if fragment.format != reference:
            raise AudioFormatMismatch(
                f"fragment {index} en {fragment.format} contre {reference} "
                "pour le premier — assemblage impossible sans rééchantillonnage"
            )
    typecode = _WIDTH_TO_TYPECODE[reference.sample_width]
    merged = array(typecode)
    for fragment in fragments:
        merged.extend(fragment.samples)
    return PcmAudio(format=reference, samples=merged)


def write_wav(audio: PcmAudio, path: Path | str) -> Path:
    """Écrit un WAV PCM. Le fichier produit est relisible par `read_wav`."""
    import sys

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = audio.samples
    if sys.byteorder == "big":  # pragma: no cover - le WAV est petit-boutiste
        payload = array(audio.samples.typecode, audio.samples)
        payload.byteswap()
    with contextlib.closing(wave.open(str(target), "wb")) as handle:
        handle.setnchannels(audio.format.channels)
        handle.setsampwidth(audio.format.sample_width)
        handle.setframerate(audio.format.sample_rate)
        handle.writeframes(payload.tobytes())
    return target
