"""Observateur déterministe.

Il mesure ce qui est réellement sorti, et confronte les mesures aux cibles que
le `MotionProgram` avait posées. Il ne devine pas, il ne juge pas la beauté :
il compte, et il dit si le compte tombe juste.

Chaque contrôle porte un identifiant, une valeur observée, une valeur attendue
et une tolérance. Le rapport qui en sort est relisible par un humain **et** par
le diagnostic — et son verdict découle mécaniquement de ses contrôles, ce que
le contrat `ObservationReport` revérifie.

Ce que l'observateur ne fait pas, volontairement : décider qu'un plan est
« beau », reconnaître un objet, ou évaluer la fidélité au sujet. Ces jugements
demandent un modèle ; sans lui, prétendre les rendre serait une mesure
inventée. Ils reviennent à la revue humaine (phase 10).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pdz2.contracts.common import QaCheck
from pdz2.contracts.enums import Severity
from pdz2.contracts.motion import MotionProgram
from pdz2.contracts.observation import Measurement, ObservationReport
from pdz2.contracts.render import RenderArtifact, RenderSpecExecutable
from pdz2.contracts.visual import VisualBible
from pdz2.qa.measures import (
    black_frame_ratio,
    colour_distance_to_palette,
    decode_frames,
    first_to_last_difference,
    frozen_frame_ratio,
    mean_absolute_difference,
    sharpness,
)
from pdz2.renderers.ffmpeg import EncodingFailed, probe_video

__all__ = [
    "DeterministicObserver",
    "ObservationOutcome",
    "ObservationFailed",
    "OBSERVER_VERSION",
    "MOTION_TOLERANCE",
]

OBSERVER_VERSION = "1.0.0"

MOTION_TOLERANCE = 0.55
"""Tolérance relative entre mouvement visé et mouvement mesuré.

Large à dessein : la cible est une intention perceptive dans [0, 1], la mesure
une différence de pixels. Les deux ne sont pas dans la même unité et ne le
seront jamais. Ce que le contrôle attrape est l'écart de *nature* — un plan
qu'on voulait animé et qui est figé, un plan qu'on voulait calme et qui
tremble — pas un écart de degré.
"""

DURATION_TOLERANCE_S = 0.12
BLACK_LIMIT = 0.02

FROZEN_LIMIT = 0.50
"""Part d'images strictement identiques au-delà de laquelle le rendu a bloqué.

Mesuré sur des rendus corrects : 0,000 à 0,023. Un rendu bloqué tend vers 1,0.
"""

MOVEMENT_FLOOR = 0.002
"""Déplacement première→dernière image en dessous duquel le plan n'a pas bougé.

Mesuré sur des poussées et parallaxes réussis : 0,005 à 0,020. Sur un plan
volontairement fixe : 0. Le plancher est posé dans ce fossé.
"""

STILLNESS_CEILING = 0.002
"""Déplacement au-delà duquel un plan voulu fixe bouge trop."""

MIN_SHARPNESS = 1e-5
PALETTE_LIMIT = 0.42


class ObservationFailed(RuntimeError):
    """L'observation elle-même n'a pas pu être menée."""


@dataclass
class ObservationOutcome:
    reports: list[ObservationReport]
    notes: list[str] = field(default_factory=list)

    def for_shot(self, shot_id: str) -> ObservationReport:
        for report in self.reports:
            if report.shot_id == shot_id:
                return report
        raise KeyError(shot_id)

    @property
    def failed(self) -> list[ObservationReport]:
        return [report for report in self.reports if not report.passed]


@dataclass
class DeterministicObserver:
    """Mesure les rendus et confronte le résultat aux cibles."""

    motion_tolerance: float = MOTION_TOLERANCE

    def observe(
        self,
        *,
        artifacts: list[RenderArtifact],
        executables: list[RenderSpecExecutable],
        motion_programs: list[MotionProgram],
        visual_bible: VisualBible,
        renders_dir: Path,
    ) -> ObservationOutcome:
        by_spec = {executable.id: executable for executable in executables}
        motions = {program.shot_id: program for program in motion_programs}
        reports: list[ObservationReport] = []

        for artifact in artifacts:
            executable = by_spec.get(artifact.source_contract_id or "")
            if executable is None:
                continue
            path = Path(renders_dir) / artifact.path
            reports.append(
                self._observe_one(
                    artifact, executable, motions.get(artifact.shot_id or ""),
                    visual_bible, path,
                )
            )

        failed = [report for report in reports if not report.passed]
        return ObservationOutcome(
            reports=reports,
            notes=[
                f"{len(reports)} plans observés par l'observateur {OBSERVER_VERSION}",
                f"{len(failed)} plan(s) non conforme(s)",
                "toutes les mesures sont déterministes : deux observations du "
                "même fichier donnent les mêmes nombres",
            ],
        )

    # ------------------------------------------------------------------ mesure

    def _observe_one(
        self,
        artifact: RenderArtifact,
        executable: RenderSpecExecutable,
        motion: MotionProgram | None,
        bible: VisualBible,
        path: Path,
    ) -> ObservationReport:
        try:
            probe = probe_video(path)
            sequence = decode_frames(path)
        except (EncodingFailed, OSError) as error:
            raise ObservationFailed(
                f"{executable.shot_id} : mesure impossible ({error})"
            ) from error

        observed_motion = mean_absolute_difference(sequence)
        displacement = first_to_last_difference(sequence)
        black = black_frame_ratio(sequence)
        frozen = frozen_frame_ratio(sequence)
        crispness = sharpness(sequence)
        palette_distance = colour_distance_to_palette(path, bible.color.palette)

        measurements = [
            Measurement(
                name="duration_s",
                value=round(probe.duration_s, 6),
                unit="s",
                method="ffprobe format.duration",
            ),
            Measurement(
                name="frame_count",
                value=float(probe.frame_count),
                unit="images",
                method="ffprobe nb_frames",
            ),
            Measurement(
                name="fps",
                value=round(probe.fps, 4),
                unit="i/s",
                method="ffprobe avg_frame_rate",
            ),
            Measurement(
                name="motion_mean_abs_diff",
                value=round(observed_motion, 8),
                unit="niveau/pixel",
                method="moyenne des différences absolues entre images consécutives, "
                "en niveaux de gris réduits à 160 px",
            ),
            Measurement(
                name="motion_first_to_last",
                value=round(displacement, 8),
                unit="niveau/pixel",
                method="différence absolue moyenne entre la première et la "
                "dernière image, en niveaux de gris réduits à 160 px",
            ),
            Measurement(
                name="black_frame_ratio",
                value=round(black, 6),
                unit="fraction",
                method="part d'images de luminance moyenne < 0,02",
            ),
            Measurement(
                name="frozen_frame_ratio",
                value=round(frozen, 6),
                unit="fraction",
                method="part de transitions strictement identiques",
            ),
            Measurement(
                name="sharpness",
                value=round(crispness, 8),
                unit="variance",
                method="variance du laplacien, moyennée sur huit images",
            ),
            Measurement(
                name="palette_distance",
                value=round(palette_distance, 6),
                unit="fraction",
                method="distance RGB moyenne au plus proche voisin de la palette "
                "de la bible visuelle",
            ),
        ]

        checks = self._checks(
            executable, motion, probe, displacement, black, frozen,
            crispness, palette_distance,
        )
        blocking_failed = any(
            check.severity is Severity.BLOCKING and not check.passed
            for check in checks
        )
        major_failed = any(
            check.severity is Severity.MAJOR and not check.passed for check in checks
        )
        return ObservationReport(
            artifact_id=artifact.id,
            shot_id=executable.shot_id,
            observer_version=OBSERVER_VERSION,
            measurements=measurements,
            checks=checks,
            passed=not (blocking_failed or major_failed),
            parent_id=artifact.id,
        )

    def _checks(
        self,
        executable,
        motion,
        probe,
        displacement,
        black,
        frozen,
        crispness,
        palette_distance,
    ) -> list[QaCheck]:
        checks = [
            QaCheck(
                check_id="duration",
                name="durée conforme à la demande",
                passed=abs(probe.duration_s - executable.duration_s)
                <= DURATION_TOLERANCE_S,
                observed=round(probe.duration_s, 4),
                expected=round(executable.duration_s, 4),
                tolerance=DURATION_TOLERANCE_S,
                severity=Severity.BLOCKING,
                detail="un plan plus court ou plus long désynchronise tout le montage",
            ),
            QaCheck(
                check_id="resolution",
                name="résolution conforme",
                passed=(probe.width, probe.height)
                == (executable.resolution.width, executable.resolution.height),
                observed=float(probe.width),
                expected=float(executable.resolution.width),
                severity=Severity.BLOCKING,
                detail=f"{probe.width}×{probe.height} rendu",
            ),
            QaCheck(
                check_id="fps",
                name="cadence conforme",
                passed=abs(probe.fps - executable.fps) <= 0.6,
                observed=round(probe.fps, 3),
                expected=float(executable.fps),
                tolerance=0.6,
                severity=Severity.MAJOR,
            ),
            QaCheck(
                check_id="not_black",
                name="le plan n'est pas noir",
                passed=black <= BLACK_LIMIT,
                observed=round(black, 4),
                expected=0.0,
                tolerance=BLACK_LIMIT,
                severity=Severity.BLOCKING,
                detail="un plan noir est un rendu perdu, pas un choix esthétique",
            ),
            QaCheck(
                check_id="not_blank",
                name="le plan a du contenu",
                passed=crispness >= MIN_SHARPNESS,
                observed=round(crispness, 8),
                expected=MIN_SHARPNESS,
                severity=Severity.BLOCKING,
                detail="une image sans aucun contour est une image vide",
            ),
        ]
        checks.extend(self._motion_checks(executable, motion, displacement, frozen))
        checks.append(
            QaCheck(
                check_id="palette",
                name="le plan reste dans le registre chromatique",
                passed=palette_distance <= PALETTE_LIMIT,
                observed=round(palette_distance, 4),
                expected=0.0,
                tolerance=PALETTE_LIMIT,
                severity=Severity.MINOR,
                detail="écart à la palette décidée dans la bible visuelle",
            )
        )
        return checks

    def _motion_checks(
        self, executable, motion, displacement, frozen
    ) -> list[QaCheck]:
        """Le contrôle le plus important : le mouvement voulu existe-t-il ?"""
        if motion is None:
            return []
        target = motion.perceptual_target.motion_energy
        if target < 0.15:
            return [
                QaCheck(
                    check_id="stillness",
                    name="le plan est bien immobile",
                    passed=displacement <= STILLNESS_CEILING,
                    observed=round(displacement, 6),
                    expected=0.0,
                    tolerance=STILLNESS_CEILING,
                    severity=Severity.MAJOR,
                    detail="un plan voulu fixe qui bouge trahit un défaut de rendu",
                )
            ]
        return [
            QaCheck(
                check_id="motion_present",
                name="le mouvement demandé existe",
                passed=displacement > MOVEMENT_FLOOR,
                observed=round(displacement, 6),
                expected=MOVEMENT_FLOOR,
                severity=Severity.BLOCKING,
                detail=(
                    f"énergie de mouvement visée {target:.2f} : un plan figé ne "
                    "démontre rien de ce qu'on voulait montrer"
                ),
            ),
            QaCheck(
                check_id="not_frozen",
                name="le plan n'est pas figé par intermittence",
                passed=frozen <= FROZEN_LIMIT,
                observed=round(frozen, 4),
                expected=0.0,
                tolerance=FROZEN_LIMIT,
                severity=Severity.MAJOR,
                detail="des images identiques d'affilée signalent un rendu bloqué",
            ),
        ]
