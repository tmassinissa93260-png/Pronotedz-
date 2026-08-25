"""Adaptateur ElevenLabs — synthèse vocale distante.

    ⚠️ JAMAIS EXÉCUTÉ DANS L'ENVIRONNEMENT OÙ CE CODE A ÉTÉ ÉCRIT.

`api.elevenlabs.io` y est injoignable. Comme pour fal.ai, la structure est
correcte et la forme exacte de l'API n'a pas été vérifiée. Premier vrai test :
le workflow GitHub Actions.

Ce qui reste vrai quoi qu'il arrive : ce module **ne rend jamais une durée**.
Il rend un chemin, comme le port l'exige, et `pdz2.audio.wave_io` mesurera les
trames du fichier. La règle VOICE FIRST ne se négocie pas avec le fournisseur.

Le service rend du MP3 par défaut ; on demande explicitement du PCM WAV, parce
que toute la chaîne de mesure lit des trames WAV.
"""

from __future__ import annotations

import os
import time
import wave
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from pdz2.audio.errors import SynthesiserUnavailable, SynthesisFailed
from pdz2.audio.ports import SynthesisResult, VoiceSpec
from pdz2.audio.wave_io import measure_wav, require_audible
from pdz2.contracts.capability import CapabilityState, ProviderCapability

__all__ = ["ElevenLabsSynthesiser", "ELEVENLABS_KEY_ENV"]

ELEVENLABS_KEY_ENV = "ELEVENLABS_API_KEY"
BASE_URL = "https://api.elevenlabs.io/v1"
_PROBE_TIMEOUT_S = 15.0
_SYNTHESIS_TIMEOUT_S = 180.0
_SAMPLE_RATE = 24000
"""PCM 24 kHz : le format brut que le service expose et que `wave` sait lire."""


@dataclass
class ElevenLabsSynthesiser:
    """Voix distante. Rend un fichier ; la durée sera mesurée ailleurs."""

    name: str = "elevenlabs"
    model: str = "eleven_multilingual_v2"

    def _cle(self) -> str | None:
        return os.environ.get(ELEVENLABS_KEY_ENV, "").strip() or None

    def get_capabilities(self) -> ProviderCapability:
        cle = self._cle()
        if cle is None:
            return self._capacite(
                False, f"{ELEVENLABS_KEY_ENV} absente de l'environnement"
            )
        try:
            reponse = httpx.get(
                f"{BASE_URL}/voices",
                headers={"xi-api-key": cle},
                timeout=_PROBE_TIMEOUT_S,
            )
        except httpx.HTTPError as erreur:
            return self._capacite(False, f"{BASE_URL} injoignable : {erreur}")
        if reponse.status_code >= 400:
            return self._capacite(
                False, f"clé refusée ou service en erreur ({reponse.status_code})"
            )
        voix = len((reponse.json() or {}).get("voices", []))
        return self._capacite(True, f"{voix} voix disponibles sur {BASE_URL}")

    def _capacite(self, joignable: bool, detail: str) -> ProviderCapability:
        return ProviderCapability(
            provider=self.name,
            state=CapabilityState.AVAILABLE if joignable else CapabilityState.UNAVAILABLE,
            measured_at=datetime.now(UTC),
            measurement_method=f"GET {BASE_URL}/voices",
            detail=detail,
            requires_network=True,
            requires_credentials=True,
        )

    def synthesise(self, text: str, voice: VoiceSpec, out_path: Path) -> SynthesisResult:
        capacite = self.get_capabilities()
        if not capacite.usable:
            raise SynthesiserUnavailable(f"{self.name} : {capacite.detail}")
        if not text.strip():
            raise SynthesisFailed("texte vide : rien à synthétiser")

        cible = Path(out_path)
        cible.parent.mkdir(parents=True, exist_ok=True)
        debut = time.monotonic()
        try:
            reponse = httpx.post(
                f"{BASE_URL}/text-to-speech/{voice.voice_id}",
                headers={"xi-api-key": self._cle(), "Content-Type": "application/json"},
                params={"output_format": f"pcm_{_SAMPLE_RATE}"},
                json={"text": text, "model_id": self.model},
                timeout=_SYNTHESIS_TIMEOUT_S,
            )
        except httpx.HTTPError as erreur:
            raise SynthesisFailed(f"{self.name} : appel impossible ({erreur})") from erreur
        if reponse.status_code >= 400:
            raise SynthesisFailed(
                f"{self.name} : code {reponse.status_code} — {reponse.text[:300]}"
            )

        # Le service rend du PCM nu : on l'habille d'un en-tête WAV pour que la
        # chaîne de mesure le lise comme n'importe quel autre fichier.
        with wave.open(str(cible), "wb") as sortie:
            sortie.setnchannels(1)
            sortie.setsampwidth(2)
            sortie.setframerate(_SAMPLE_RATE)
            sortie.writeframes(reponse.content)

        # Un moteur qui rend un WAV muet a échoué, même s'il annonce un succès.
        require_audible(measure_wav(cible), f"{self.name} / {cible.name}")
        return SynthesisResult(
            path=cible,
            engine=self.name,
            engine_version=self.model,
            voice=voice,
            latency_s=round(time.monotonic() - debut, 4),
            cost_usd=0.0,
        )
