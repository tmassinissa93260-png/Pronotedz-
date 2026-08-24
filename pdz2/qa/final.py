"""QA finale : contrôler le livrable, pas les intentions.

Le dernier contrôle porte sur le fichier qui partira. Il vérifie ce qu'on peut
mesurer sur lui — durée, format, cadence, présence d'audio, loudness, noirceur,
mouvement — et rien d'autre.

Ce qu'il ne fait pas : dire si la vidéo est bonne. Un `HumanReview` reste
nécessaire, et le rapport le dit explicitement plutôt que de laisser croire
qu'un contrôle automatique suffit.

    HUMANS JUDGE WHAT MACHINES CANNOT MEASURE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pdz2.contracts.common import QaCheck
from pdz2.contracts.delivery import EditTimeline, LoudnessMeasurement
from pdz2.contracts.enums import AspectRatio, Severity
from pdz2.contracts.observation import Measurement, ObservationReport
from pdz2.qa.measures import black_frame_ratio, decode_frames, first_to_last_difference
from pdz2.renderers.ffmpeg import probe_video

__all__ = ["FinalQa", "FinalQaOutcome", "FINAL_QA_VERSION", "HUMAN_REVIEW_NOTICE"]

FINAL_QA_VERSION = "1.0.0"

HUMAN_REVIEW_NOTICE = (
    "Ce rapport ne dit pas si la vidéo est bonne. Il dit qu'elle est "
    "techniquement livrable. La pertinence de la démonstration, la justesse du "
    "ton et la qualité des images relèvent d'une revue humaine."
)

_DURATION_TOLERANCE_S = 0.2

_TARGET_TOLERANCE = 0.15
"""Écart toléré entre la durée commandée et celle réellement livrée.

15 % : sur une commande de 40 s, un livrable entre 34 et 46 s reste le même
objet éditorial. Au-delà, ce n'est plus le format demandé — l'épisode de
référence est tombé à 27,4 s pour 40 s commandées (−31 %), et rien ne le
disait une fois le MP4 écrit.

Le contrôle est MINOR, pas BLOCKING, et c'est délibéré : la vidéo est
techniquement parfaite, la durée officielle vient de la voix mesurée et elle
est exacte. Bloquer la livraison pour ça reviendrait à jeter un livrable
valide. Mais le taire reviendrait à laisser croire que la commande a été
tenue.
"""
_BLACK_LIMIT = 0.02
_LOUDNESS_TOLERANCE_LU = 2.5


@dataclass
class FinalQaOutcome:
    report: ObservationReport
    notes: list[str] = field(default_factory=list)

    @property
    def deliverable(self) -> bool:
        return self.report.passed


@dataclass
class FinalQa:
    target_lufs: float = -14.0

    def check(
        self,
        *,
        master_path: Path,
        timeline: EditTimeline,
        loudness: LoudnessMeasurement,
        aspect_ratio: AspectRatio,
        master_artifact_id: str,
        target_duration_s: float | None = None,
    ) -> FinalQaOutcome:
        probe = probe_video(master_path)
        sequence = decode_frames(master_path)
        black = black_frame_ratio(sequence)
        displacement = first_to_last_difference(sequence)

        measurements = [
            Measurement(name="duration_s", value=round(probe.duration_s, 6),
                        unit="s", method="ffprobe format.duration"),
            Measurement(name="width", value=float(probe.width), unit="px",
                        method="ffprobe stream.width"),
            Measurement(name="height", value=float(probe.height), unit="px",
                        method="ffprobe stream.height"),
            Measurement(name="fps", value=round(probe.fps, 4), unit="i/s",
                        method="ffprobe avg_frame_rate"),
            Measurement(name="size_bytes", value=float(probe.size_bytes),
                        unit="octets", method="stat"),
            Measurement(name="integrated_lufs", value=loudness.integrated_lufs,
                        unit="LUFS", method=loudness.method),
            Measurement(name="true_peak_dbtp", value=loudness.true_peak_dbtp,
                        unit="dBTP", method=loudness.method),
            Measurement(name="black_frame_ratio", value=round(black, 6),
                        unit="fraction", method="part d'images de luminance < 0,02"),
            Measurement(name="motion_first_to_last", value=round(displacement, 8),
                        unit="niveau/pixel",
                        method="différence première ↔ dernière image"),
        ]

        checks = [
            QaCheck(
                check_id="final_duration",
                name="la durée du master suit le montage",
                passed=abs(probe.duration_s - timeline.duration_s)
                <= _DURATION_TOLERANCE_S,
                observed=round(probe.duration_s, 3),
                expected=round(timeline.duration_s, 3),
                tolerance=_DURATION_TOLERANCE_S,
                severity=Severity.BLOCKING,
            ),
            QaCheck(
                check_id="final_duration_target",
                name="le livrable tient la durée commandée",
                passed=(
                    True
                    if target_duration_s is None
                    else abs(probe.duration_s - target_duration_s)
                    <= target_duration_s * _TARGET_TOLERANCE
                ),
                observed=round(probe.duration_s, 2),
                expected=round(target_duration_s, 2) if target_duration_s else None,
                tolerance=(
                    round(target_duration_s * _TARGET_TOLERANCE, 2)
                    if target_duration_s
                    else None
                ),
                severity=Severity.MINOR,
                detail=(
                    "écart éditorial, pas technique : la durée officielle vient "
                    "de la voix mesurée et elle est juste. C'est le script qui "
                    "n'a pas la longueur commandée — un épisode plus court que "
                    "demandé reste diffusable, mais ce n'est pas ce qui a été "
                    "commandé, et personne ne doit s'en apercevoir au montage."
                ),
            ),
            QaCheck(
                check_id="final_format",
                name="le format correspond à celui demandé",
                passed=_matches(probe.width, probe.height, aspect_ratio),
                observed=round(probe.width / max(1, probe.height), 4),
                expected=_ratio(aspect_ratio),
                tolerance=0.02,
                severity=Severity.BLOCKING,
                detail=f"{probe.width}×{probe.height} pour {aspect_ratio.value}",
            ),
            QaCheck(
                check_id="final_has_audio",
                name="le master a une piste audio",
                passed=probe.has_audio,
                observed=1.0 if probe.has_audio else 0.0,
                expected=1.0,
                severity=Severity.BLOCKING,
                detail="une vidéo muette n'est pas le livrable attendu",
            ),
            QaCheck(
                check_id="final_not_black",
                name="le master n'est pas noir",
                passed=black <= _BLACK_LIMIT,
                observed=round(black, 4),
                expected=0.0,
                tolerance=_BLACK_LIMIT,
                severity=Severity.BLOCKING,
            ),
            QaCheck(
                check_id="final_loudness",
                name="la loudness reste dans la plage de diffusion",
                passed=abs(loudness.integrated_lufs - self.target_lufs)
                <= _LOUDNESS_TOLERANCE_LU,
                observed=round(loudness.integrated_lufs, 2),
                expected=self.target_lufs,
                tolerance=_LOUDNESS_TOLERANCE_LU,
                severity=Severity.MINOR,
                detail="au-delà, la plateforme normalisera elle-même",
            ),
            QaCheck(
                check_id="final_true_peak",
                name="la crête ne sature pas",
                passed=loudness.true_peak_dbtp <= -0.9,
                observed=round(loudness.true_peak_dbtp, 2),
                expected=-1.5,
                tolerance=0.6,
                severity=Severity.MAJOR,
                detail="une crête trop haute écrête à l'encodage lossy",
            ),
            QaCheck(
                check_id="final_not_frozen",
                name="le master n'est pas une image fixe",
                passed=displacement > 0.001,
                observed=round(displacement, 6),
                expected=0.001,
                severity=Severity.MAJOR,
                detail="un épisode entièrement figé signale un montage vide",
            ),
        ]

        blocking = [
            check for check in checks
            if check.severity is Severity.BLOCKING and not check.passed
        ]
        major = [
            check for check in checks
            if check.severity is Severity.MAJOR and not check.passed
        ]
        report = ObservationReport(
            artifact_id=master_artifact_id,
            shot_id=None,
            observer_version=f"final-qa {FINAL_QA_VERSION}",
            measurements=measurements,
            checks=checks,
            passed=not (blocking or major),
            parent_id=master_artifact_id,
        )
        return FinalQaOutcome(
            report=report,
            notes=[
                f"{len(checks)} contrôles finaux, {len(blocking)} bloquant(s), "
                f"{len(major)} majeur(s)",
                HUMAN_REVIEW_NOTICE,
            ],
        )


def _ratio(aspect_ratio: AspectRatio) -> float:
    width, height = (int(part) for part in aspect_ratio.value.split(":"))
    return round(width / height, 4)


def _matches(width: int, height: int, aspect_ratio: AspectRatio) -> bool:
    return abs(width / max(1, height) - _ratio(aspect_ratio)) <= 0.02
