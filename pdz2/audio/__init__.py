"""Chaîne audio de PDZ 2 — phase 2 : synthèse réelle et mesure.

    TTS réel → audio réel → durée mesurée → découpage temporel

La durée officielle d'un épisode sort d'ici, et de nulle part ailleurs. Aucun
module de ce paquet ne connaît `estimated_duration_s`.

Implémenté : port de synthèse, adaptateur eSpeak NG, mesure de WAV en
bibliothèque standard, construction de la `VoiceTimeline`, et le mastering
EBU R128 en deux passes (phase 10).
À venir : sound design et diarisation.
"""

from pdz2.audio.errors import (
    AudioCorrupt,
    AudioError,
    AudioFormatMismatch,
    AudioSilent,
    DurationInconsistent,
    SynthesiserUnavailable,
    SynthesisFailed,
)
from pdz2.audio.espeak import EspeakSynthesiser
from pdz2.audio.mastering import (
    LOUDNESS_TOLERANCE_LU,
    TARGET_LUFS,
    TARGET_TRUE_PEAK_DBTP,
    AudioMasterer,
    MasteringFailed,
    MasteringOutcome,
    measure_loudness,
)
from pdz2.audio.narration import NarrationOutcome, NarrationRecorder
from pdz2.audio.ports import SpeechSynthesiser, SynthesisResult, VoiceSpec
from pdz2.audio.timeline import (
    AssembledVoice,
    MeasuredLine,
    VoiceTimelineBuilder,
)
from pdz2.audio.wave_io import (
    AudioFormat,
    AudioMeasurement,
    PcmAudio,
    concatenate,
    measure_wav,
    read_wav,
    require_audible,
    silence,
    write_wav,
)

__all__ = [
    "SpeechSynthesiser",
    "VoiceSpec",
    "SynthesisResult",
    "EspeakSynthesiser",
    "AudioFormat",
    "AudioMeasurement",
    "PcmAudio",
    "measure_wav",
    "read_wav",
    "write_wav",
    "concatenate",
    "silence",
    "require_audible",
    "NarrationRecorder",
    "NarrationOutcome",
    "MeasuredLine",
    "AssembledVoice",
    "VoiceTimelineBuilder",
    "AudioError",
    "SynthesiserUnavailable",
    "SynthesisFailed",
    "AudioCorrupt",
    "AudioSilent",
    "AudioFormatMismatch",
    "DurationInconsistent",
    "AudioMasterer",
    "MasteringOutcome",
    "MasteringFailed",
    "measure_loudness",
    "TARGET_LUFS",
    "TARGET_TRUE_PEAK_DBTP",
    "LOUDNESS_TOLERANCE_LU",
]
