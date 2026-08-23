"""Adaptateur eSpeak NG — synthèse réelle, hors-ligne, déterministe.

eSpeak NG n'est pas une voix de production : c'est un synthétiseur à
formants, et cela s'entend. Il est ici pour une raison précise — il est
**réel**, **hors-ligne**, **reproductible au bit près**, et son débit se
règle. Il permet donc de vérifier pour de bon la règle qui compte :

    si le TTS change, la VoiceTimeline change.

Un moteur de meilleure qualité s'ajoutera derrière le même port, sans que
rien en aval ne bouge : la durée officielle sortira toujours de la mesure du
fichier, pas du moteur qui l'a écrit.

Dépendance système : le binaire `espeak-ng` (paquet Debian/Ubuntu
`espeak-ng`). Absent, l'adaptateur se déclare UNAVAILABLE avec la raison, et
rien ne le contourne en silence.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path

from pdz2.audio.errors import SynthesiserUnavailable, SynthesisFailed
from pdz2.audio.ports import SynthesisResult, VoiceSpec
from pdz2.audio.wave_io import measure_wav, require_audible
from pdz2.contracts.capability import ProviderCapability

__all__ = ["EspeakSynthesiser"]

_VERSION = re.compile(r"text-to-speech:\s*([0-9][^\s]*)")
_PROBE_TIMEOUT_S = 10.0
_SYNTHESIS_TIMEOUT_S = 120.0


class EspeakSynthesiser:
    """Synthèse par le binaire `espeak-ng`."""

    name = "espeak-ng"

    def __init__(self, binary: str = "espeak-ng", timeout_s: float = _SYNTHESIS_TIMEOUT_S):
        self.binary = binary
        self.timeout_s = timeout_s

    # ------------------------------------------------------------- capacités

    def get_capabilities(self) -> ProviderCapability:
        method = f"{self.binary} --version"
        path = shutil.which(self.binary)
        if path is None:
            return ProviderCapability.measured(
                self.name,
                reachable=False,
                method=f"which({self.binary})",
                detail=(
                    f"binaire {self.binary!r} absent du PATH — "
                    "installer le paquet système « espeak-ng »"
                ),
                requires_network=False,
            )
        try:
            probe = subprocess.run(
                [self.binary, "--version"],
                capture_output=True,
                text=True,
                timeout=_PROBE_TIMEOUT_S,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return ProviderCapability.measured(
                self.name,
                reachable=False,
                method=method,
                detail=f"{self.binary} injoignable : {error}",
                requires_network=False,
            )
        if probe.returncode != 0:
            return ProviderCapability.measured(
                self.name,
                reachable=False,
                method=method,
                detail=f"{self.binary} --version a rendu {probe.returncode}",
                requires_network=False,
            )
        match = _VERSION.search(probe.stdout)
        version = match.group(1) if match else "inconnue"
        return ProviderCapability.measured(
            self.name,
            reachable=True,
            method=method,
            detail=f"eSpeak NG {version} en {path}",
            requires_network=False,
        )

    def version(self) -> str:
        capability = self.get_capabilities()
        if not capability.usable:
            return "inconnue"
        match = re.search(r"eSpeak NG (\S+)", capability.detail)
        return match.group(1) if match else "inconnue"

    def voices(self, language: str | None = None) -> list[str]:
        """Voix réellement proposées par le binaire installé."""
        # `--voices=fr` est un seul argument : en deux, le filtre est ignoré et
        # le binaire liste toutes les langues.
        argv = [self.binary, f"--voices={language}" if language else "--voices"]
        probe = subprocess.run(
            argv, capture_output=True, text=True, timeout=_PROBE_TIMEOUT_S, check=False
        )
        if probe.returncode != 0:
            return []
        found: list[str] = []
        for line in probe.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2:
                found.append(parts[1])
        return found

    # -------------------------------------------------------------- synthèse

    def synthesise(self, text: str, voice: VoiceSpec, out_path: Path) -> SynthesisResult:
        capability = self.get_capabilities()
        if not capability.usable:
            raise SynthesiserUnavailable(f"{self.name} : {capability.detail}")
        if not text.strip():
            raise SynthesisFailed("texte vide : rien à synthétiser")

        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        argv = [
            self.binary,
            "-v", voice.voice_id,
            "-s", str(voice.rate_wpm),
            "-p", str(voice.pitch),
            "-a", str(voice.amplitude),
            "-g", str(voice.gap_ms),
            "-w", str(target),
        ]
        started = time.monotonic()
        try:
            # Le texte passe par l'entrée standard : aucun argument ne peut être
            # confondu avec une option, quel que soit le caractère de tête.
            run = subprocess.run(
                argv,
                input=text,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise SynthesisFailed(
                f"{self.name} : dépassement de {self.timeout_s:g}s sur "
                f"{len(text)} caractères"
            ) from error
        except OSError as error:
            raise SynthesisFailed(f"{self.name} : appel impossible ({error})") from error
        latency = time.monotonic() - started

        if run.returncode != 0:
            detail = (run.stderr or run.stdout or "").strip()[:400]
            raise SynthesisFailed(
                f"{self.name} : code de retour {run.returncode}"
                + (f" — {detail}" if detail else "")
            )
        if not target.is_file():
            raise SynthesisFailed(f"{self.name} : aucun fichier écrit en {target}")

        # Le fichier est mesuré tout de suite : un moteur qui rend un WAV muet
        # a échoué, même s'il annonce un succès.
        require_audible(measure_wav(target), f"{self.name} / {target.name}")

        return SynthesisResult(
            path=target,
            engine=self.name,
            engine_version=self.version(),
            voice=voice,
            latency_s=round(latency, 4),
        )
