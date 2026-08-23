"""Mastering audio : normaliser, et mesurer ce qu'on a obtenu.

La normalisation de loudness passe par le filtre `loudnorm` de ffmpeg, qui
implémente EBU R128. Elle se fait en **deux passes** : la première mesure, la
seconde corrige avec les valeurs mesurées. Une passe unique corrige à
l'aveugle et manque la cible de plusieurs LU.

La mesure finale est refaite sur le fichier produit — on ne fait pas confiance
à ce que le filtre annonce, on relit ce qu'il a écrit.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from pdz2.audio.errors import AudioError
from pdz2.contracts.delivery import LoudnessMeasurement

__all__ = [
    "AudioMasterer",
    "MasteringOutcome",
    "MasteringFailed",
    "measure_loudness",
    "TARGET_LUFS",
    "TARGET_TRUE_PEAK_DBTP",
    "LOUDNESS_TOLERANCE_LU",
]

TARGET_LUFS = -14.0
"""Cible de loudness intégrée, en LUFS.

−14 LUFS est la valeur vers laquelle normalisent les plateformes courtes. Y
livrer évite qu'elles ne réduisent le niveau elles-mêmes, ce qui écraserait la
dynamique du mixage.
"""

TARGET_TRUE_PEAK_DBTP = -1.5
"""Plafond de crête vraie, en dBTP. Garde une marge pour l'encodage lossy."""

LOUDNESS_TOLERANCE_LU = 1.0
"""Écart toléré à la cible, en LU."""

_TIMEOUT_S = 300.0


class MasteringFailed(AudioError):
    """Le mastering a échoué. La raison est nommée."""


@dataclass
class MasteringOutcome:
    path: Path
    loudness: LoudnessMeasurement
    within_tolerance: bool
    notes: list[str] = field(default_factory=list)


def measure_loudness(path: Path, binary: str = "ffmpeg") -> LoudnessMeasurement:
    """Mesure EBU R128 sur le fichier tel qu'il est. Aucune valeur devinée."""
    target = Path(path)
    if not target.is_file():
        raise MasteringFailed(f"fichier audio absent : {target}")
    argv = [
        binary, "-hide_banner", "-nostats",
        "-i", str(target),
        "-af", "loudnorm=print_format=json",
        "-f", "null", "-",
    ]
    run = subprocess.run(argv, capture_output=True, text=True, timeout=_TIMEOUT_S)
    if run.returncode != 0:
        raise MasteringFailed(
            f"mesure impossible : {run.stderr.strip()[:300]}"
        )
    payload = _last_json(run.stderr)
    if payload is None:
        raise MasteringFailed(f"{target.name} : ffmpeg n'a rendu aucune mesure")
    return LoudnessMeasurement(
        integrated_lufs=float(payload["input_i"]),
        true_peak_dbtp=float(payload["input_tp"]),
        loudness_range_lu=abs(float(payload["input_lra"])),
        method="ffmpeg loudnorm / EBU R128, deux passes",
    )


def _explain_gap_reason(
    measured: LoudnessMeasurement,
    final: LoudnessMeasurement,
    target_lufs: float,
    target_true_peak: float,
) -> str:
    """Pourquoi la cible n'est pas atteinte. Un écart nu n'apprend rien."""
    needed_gain = target_lufs - measured.integrated_lufs
    resulting_peak = measured.true_peak_dbtp + needed_gain
    if resulting_peak > target_true_peak + 0.1:
        return (
            f"atteindre {target_lufs:g} LUFS demanderait {needed_gain:+.1f} dB, "
            f"ce qui porterait la crête à {resulting_peak:+.1f} dBTP contre un "
            f"plafond de {target_true_peak:g} dBTP. Le plafond de crête est la "
            f"contrainte, pas la normalisation : la crête finale est à "
            f"{final.true_peak_dbtp:.2f} dBTP, saturée. Réduire l'écart exigerait "
            "une compression qui change la dynamique — c'est une décision de "
            "mixage, pas une correction mécanique"
        )
    return (
        "la normalisation n'a pas convergé sans que le plafond de crête soit "
        f"en cause (crête finale {final.true_peak_dbtp:.2f} dBTP)"
    )


def _last_json(text: str) -> dict | None:
    """Extrait le dernier objet JSON de la sortie d'erreur de ffmpeg."""
    matches = list(re.finditer(r"\{[^{}]*\}", text, re.DOTALL))
    for match in reversed(matches):
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if "input_i" in payload:
            return payload
    return None


@dataclass
class AudioMasterer:
    """Normalise la voix vers la cible, puis vérifie sur le fichier produit."""

    target_lufs: float = TARGET_LUFS
    target_true_peak: float = TARGET_TRUE_PEAK_DBTP
    binary: str = "ffmpeg"

    def master(self, *, source: Path, out_path: Path) -> MasteringOutcome:
        measured = measure_loudness(source, self.binary)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Seconde passe : on corrige avec ce que la première a mesuré.
        loudnorm = (
            f"loudnorm=I={self.target_lufs}:TP={self.target_true_peak}:LRA=11"
            f":measured_I={measured.integrated_lufs}"
            f":measured_TP={measured.true_peak_dbtp}"
            f":measured_LRA={measured.loudness_range_lu}"
            f":linear=true:print_format=summary"
        )
        argv = [
            self.binary, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(source),
            "-af", loudnorm,
            "-ar", "48000",
            "-c:a", "pcm_s16le",
            str(out_path),
        ]
        run = subprocess.run(argv, capture_output=True, text=True, timeout=_TIMEOUT_S)
        if run.returncode != 0:
            raise MasteringFailed(
                f"normalisation impossible : {run.stderr.strip()[:300]}"
            )
        if not out_path.is_file() or out_path.stat().st_size == 0:
            raise MasteringFailed(f"aucun fichier écrit en {out_path}")

        # On relit ce qui a été écrit, pas ce que le filtre annonce.
        final = measure_loudness(out_path, self.binary)
        gap = abs(final.integrated_lufs - self.target_lufs)
        within = gap <= LOUDNESS_TOLERANCE_LU
        notes = [
            f"avant : {measured.integrated_lufs:.2f} LUFS, "
            f"crête {measured.true_peak_dbtp:.2f} dBTP",
            f"après : {final.integrated_lufs:.2f} LUFS, "
            f"crête {final.true_peak_dbtp:.2f} dBTP "
            f"(cible {self.target_lufs:g} ± {LOUDNESS_TOLERANCE_LU:g} LU)",
        ]
        if not within:
            notes.append(self._explain_gap(measured, final, gap))
        return MasteringOutcome(
            path=out_path, loudness=final, within_tolerance=within, notes=notes
        )

    def _explain_gap(self, measured, final, gap) -> str:
        return (
            f"écart de {gap:.2f} LU à la cible. "
            + _explain_gap_reason(
                measured, final, self.target_lufs, self.target_true_peak
            )
        )
