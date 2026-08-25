"""Port de synthèse vocale.

La chaîne audio ne connaît aucun moteur nommé : elle connaît ce protocole.
Un adaptateur déclare sa capacité — mesurée et datée — et rend un fichier
audio **réel** dont la durée sera mesurée sur les trames, pas déduite du
texte.

Le port ne rend jamais une durée : il rend un chemin. La durée est ensuite
lue sur le fichier par `pdz2.audio.wave_io`. Cette séparation est ce qui rend
impossible qu'un moteur « annonce » une durée qui deviendrait officielle.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import Field, model_validator

from pdz2.contracts.base import Element
from pdz2.contracts.capability import ProviderCapability

__all__ = ["VoiceSpec", "SynthesisResult", "SpeechSynthesiser"]


class VoiceSpec(Element):
    """Réglages de voix. Typés : aucun dictionnaire de paramètres opaques."""

    voice_id: str = Field(min_length=1)
    """Identifiant de voix propre à l'adaptateur, par exemple « fr »."""

    rate_wpm: int = Field(default=165, ge=60, le=450)
    """Débit visé. C'est un réglage du moteur, jamais une prédiction de durée."""

    pitch: int = Field(default=50, ge=0, le=99)
    amplitude: int = Field(default=100, ge=0, le=200)
    gap_ms: int = Field(default=0, ge=0, le=500)
    """Pause insérée par le moteur entre les mots."""

    @model_validator(mode="after")
    def _identifier_is_plain(self):
        if any(char.isspace() for char in self.voice_id):
            raise ValueError(f"identifiant de voix invalide : {self.voice_id!r}")
        return self

    def fingerprint(self) -> str:
        """Empreinte lisible des réglages. Change dès qu'un réglage change."""
        return (
            f"{self.voice_id}@{self.rate_wpm}wpm/p{self.pitch}"
            f"/a{self.amplitude}/g{self.gap_ms}"
        )


@dataclass(frozen=True)
class SynthesisResult:
    """Ce qu'un adaptateur rend : un fichier, et de quoi le tracer."""

    path: Path
    engine: str
    engine_version: str
    voice: VoiceSpec
    latency_s: float
    cost_usd: float = 0.0


@runtime_checkable
class SpeechSynthesiser(Protocol):
    """Interface commune des moteurs de synthèse."""

    name: str

    def get_capabilities(self) -> ProviderCapability:
        """Sonde réellement le moteur. Ne jamais deviner l'état."""

    def synthesise(self, text: str, voice: VoiceSpec, out_path: Path) -> SynthesisResult:
        """Écrit l'audio de `text` dans `out_path`.

        Lève `SynthesiserUnavailable` si le moteur n'est pas là, et
        `SynthesisFailed` s'il a été appelé sans rendre d'audio exploitable.
        Ne rend jamais de durée : c'est au mesureur de la lire.
        """
