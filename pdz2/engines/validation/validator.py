"""Validateur statique : refuser avant de dépenser.

Douze règles, une par ligne du §13, chacune nommée et testable. Le validateur
ne répare rien et ne choisit rien : il constate, il classe par gravité, et il
rejette. Un rapport bloquant interdit à la machine à états de franchir la
barrière de coût — aucun appel payant n'a lieu avant qu'il soit accepté.

    VALIDATORS REJECT.

La règle des capacités est la plus importante en pratique : elle interdit de
*demander* une stratégie qu'aucun exécutant ne sait faire, et elle exige qu'un
repli déterministe reste disponible pour chaque plan. C'est ce qui garantit
qu'un épisode aboutit même sans le moindre fournisseur vidéo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pdz2.contracts.enums import Severity
from pdz2.contracts.motion import CameraProgram, MotionPrimitive, MotionProgram
from pdz2.contracts.render import (
    AI_VIDEO_STRATEGIES,
    DETERMINISTIC_STRATEGIES,
    RenderSpecRequested,
    RenderStrategy,
)
from pdz2.contracts.research import TopicRequest
from pdz2.contracts.shots import ShotGraph
from pdz2.contracts.validation import (
    ValidationIssue,
    ValidationReport,
    ValidationRule,
)
from pdz2.contracts.versioning import Version, registry
from pdz2.contracts.visual import ImageSpec

__all__ = ["StaticValidator", "ValidationOutcome", "VALIDATOR_VERSION"]

VALIDATOR_VERSION = "1.0.0"

MAX_SHOT_DURATION_S = 30.0
"""Au-delà, aucun exécutant connu ne rend un plan d'un seul tenant."""

MIN_SHOT_DURATION_S = 0.4
"""En deçà, un plan ne contient pas assez d'images pour être vu."""


@dataclass
class ValidationOutcome:
    report: ValidationReport
    notes: list[str] = field(default_factory=list)


@dataclass
class StaticValidator:
    """Contrôle un lot de demandes de rendu avant la moindre dépense."""

    available_strategies: frozenset[RenderStrategy] = DETERMINISTIC_STRATEGIES
    """Stratégies réellement exécutables ici. Mesurées, jamais annoncées."""

    max_shot_duration_s: float = MAX_SHOT_DURATION_S
    min_shot_duration_s: float = MIN_SHOT_DURATION_S

    def validate(
        self,
        *,
        episode_id: str,
        shot_graph: ShotGraph,
        requested: list[RenderSpecRequested],
        motion_programs: list[MotionProgram],
        camera_programs: list[CameraProgram],
        image_specs: list[ImageSpec],
        request: TopicRequest,
    ) -> ValidationOutcome:
        issues: list[ValidationIssue] = []
        motions = {program.id: program for program in motion_programs}
        cameras = {program.id: program for program in camera_programs}
        images = {spec.id: spec for spec in image_specs}
        shots = {shot.shot_id: shot for shot in shot_graph.shots}

        issues += self._check_versions(requested)
        issues += self._check_coverage(shot_graph, requested)

        for spec in requested:
            subject = spec.shot_id
            issues += self._check_references(spec, motions, cameras, images, subject)
            issues += self._check_duration(spec, shots, subject)
            issues += self._check_camera(spec, cameras, motions, subject)
            issues += self._check_resolution(spec, subject)
            issues += self._check_capability(spec, subject)
            issues += self._check_fallback(spec, subject)
            issues += self._check_evidence(spec, shots, subject)
            issues += self._check_continuity(spec, shots, images, subject)

        issues += self._check_budget(requested, request)

        blocking = [i for i in issues if i.severity is Severity.BLOCKING]
        report = ValidationReport(
            episode_id=episode_id,
            shot_graph_id=shot_graph.id,
            requested_spec_ids=[spec.id for spec in requested],
            issues=issues,
            validator_version=VALIDATOR_VERSION,
            accepted=not blocking,
        )
        return ValidationOutcome(
            report=report,
            notes=[
                f"{len(requested)} demandes contrôlées par le validateur "
                f"{VALIDATOR_VERSION}",
                f"{len(issues)} constat(s), dont {len(blocking)} bloquant(s)",
                "stratégies exécutables ici : "
                + ", ".join(sorted(s.value for s in self.available_strategies)),
            ],
        )

    # ------------------------------------------------------------- les règles

    @staticmethod
    def _check_versions(requested: list[RenderSpecRequested]) -> list[ValidationIssue]:
        """Schéma et version : un contrat illisible ne s'exécute pas."""
        issues: list[ValidationIssue] = []
        for spec in requested:
            try:
                current = Version.parse(
                    registry.get(spec.CONTRACT_NAME).CONTRACT_VERSION
                )
                payload = Version.parse(spec.version)
            except Exception as error:  # noqa: BLE001 - traduit en constat
                issues.append(
                    ValidationIssue(
                        rule=ValidationRule.SCHEMA,
                        severity=Severity.BLOCKING,
                        subject_id=spec.shot_id,
                        detail=f"contrat illisible : {error}",
                        remedy="recompiler la demande de rendu",
                    )
                )
                continue
            if not current.can_read(payload):
                issues.append(
                    ValidationIssue(
                        rule=ValidationRule.CONTRACT_VERSION,
                        severity=Severity.BLOCKING,
                        subject_id=spec.shot_id,
                        detail=f"version {payload} illisible par {current}",
                        remedy="migrer le contrat ou recompiler la demande",
                    )
                )
        return issues

    @staticmethod
    def _check_coverage(
        shot_graph: ShotGraph, requested: list[RenderSpecRequested]
    ) -> list[ValidationIssue]:
        """Chaque plan du graphe doit avoir sa demande, et une seule."""
        issues: list[ValidationIssue] = []
        counts: dict[str, int] = {}
        for spec in requested:
            counts[spec.shot_id] = counts.get(spec.shot_id, 0) + 1
        for shot in shot_graph.shots:
            if shot.shot_id not in counts:
                issues.append(
                    ValidationIssue(
                        rule=ValidationRule.REQUIRED_FIELD,
                        severity=Severity.BLOCKING,
                        subject_id=shot.shot_id,
                        detail="plan du graphe sans demande de rendu",
                        remedy="recompiler les demandes depuis le shot graph",
                    )
                )
        for shot_id, count in counts.items():
            if count > 1:
                issues.append(
                    ValidationIssue(
                        rule=ValidationRule.LOGICAL_CONTRADICTION,
                        severity=Severity.BLOCKING,
                        subject_id=shot_id,
                        detail=f"{count} demandes pour un seul plan",
                        remedy="ne garder qu'une demande par plan",
                    )
                )
            if shot_id not in {shot.shot_id for shot in shot_graph.shots}:
                issues.append(
                    ValidationIssue(
                        rule=ValidationRule.REQUIRED_FIELD,
                        severity=Severity.BLOCKING,
                        subject_id=shot_id,
                        detail="demande de rendu sans plan correspondant",
                        remedy="retirer la demande orpheline",
                    )
                )
        return issues

    @staticmethod
    def _check_references(spec, motions, cameras, images, subject) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if spec.motion_program_id not in motions:
            issues.append(
                ValidationIssue(
                    rule=ValidationRule.REQUIRED_FIELD,
                    severity=Severity.BLOCKING,
                    subject_id=subject,
                    detail=f"programme de mouvement inconnu {spec.motion_program_id}",
                    remedy="recompiler les programmes de mouvement",
                )
            )
        if spec.camera_program_id not in cameras:
            issues.append(
                ValidationIssue(
                    rule=ValidationRule.REQUIRED_FIELD,
                    severity=Severity.BLOCKING,
                    subject_id=subject,
                    detail=f"programme caméra inconnu {spec.camera_program_id}",
                    remedy="recompiler le shot graph",
                )
            )
        unknown = [ref for ref in spec.image_spec_ids if ref not in images]
        if unknown:
            issues.append(
                ValidationIssue(
                    rule=ValidationRule.REQUIRED_FIELD,
                    severity=Severity.BLOCKING,
                    subject_id=subject,
                    detail=f"spécifications d'image inconnues {unknown}",
                    remedy="recompiler les spécifications d'image",
                )
            )
        if not spec.image_spec_ids:
            issues.append(
                ValidationIssue(
                    rule=ValidationRule.REQUIRED_FIELD,
                    severity=Severity.BLOCKING,
                    subject_id=subject,
                    detail="aucune image de départ",
                    remedy="compiler au moins une spécification d'image par plan",
                )
            )
        return issues

    def _check_duration(self, spec, shots, subject) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if spec.duration_s > self.max_shot_duration_s:
            issues.append(
                ValidationIssue(
                    rule=ValidationRule.DURATION_FEASIBILITY,
                    severity=Severity.BLOCKING,
                    subject_id=subject,
                    detail=(
                        f"{spec.duration_s:.2f}s au-delà du plafond "
                        f"{self.max_shot_duration_s:g}s d'un plan d'un seul tenant"
                    ),
                    remedy="découper le plan dans le Temporal Director",
                )
            )
        if spec.duration_s < self.min_shot_duration_s:
            issues.append(
                ValidationIssue(
                    rule=ValidationRule.DURATION_FEASIBILITY,
                    severity=Severity.MAJOR,
                    subject_id=subject,
                    detail=(
                        f"{spec.duration_s:.2f}s sous le plancher "
                        f"{self.min_shot_duration_s:g}s : le plan sera à peine vu"
                    ),
                )
            )
        shot = shots.get(subject)
        if shot is not None and abs(shot.duration_s - spec.duration_s) > 1e-3:
            issues.append(
                ValidationIssue(
                    rule=ValidationRule.LOGICAL_CONTRADICTION,
                    severity=Severity.BLOCKING,
                    subject_id=subject,
                    detail=(
                        f"la demande dure {spec.duration_s:.3f}s pour un plan de "
                        f"{shot.duration_s:.3f}s"
                    ),
                    remedy="recompiler la demande depuis le shot graph",
                )
            )
        return issues

    @staticmethod
    def _check_camera(spec, cameras, motions, subject) -> list[ValidationIssue]:
        """L'exemple du §13 : caméra verrouillée et mouvement demandé."""
        issues: list[ValidationIssue] = []
        camera = cameras.get(spec.camera_program_id)
        if camera is None:
            return issues
        if camera.locked and spec.requested_camera.value != "lock":
            issues.append(
                ValidationIssue(
                    rule=ValidationRule.CAMERA_CONSTRAINT,
                    severity=Severity.BLOCKING,
                    subject_id=subject,
                    detail=(
                        f"caméra verrouillée mais mouvement "
                        f"{spec.requested_camera.value} demandé"
                    ),
                    remedy="déverrouiller la caméra ou demander « lock »",
                )
            )
        if camera.move is not spec.requested_camera:
            issues.append(
                ValidationIssue(
                    rule=ValidationRule.CAMERA_CONSTRAINT,
                    severity=Severity.BLOCKING,
                    subject_id=subject,
                    detail=(
                        f"la demande porte {spec.requested_camera.value} et le "
                        f"programme caméra {camera.move.value}"
                    ),
                    remedy="recompiler la demande depuis le programme caméra",
                )
            )
        motion = motions.get(spec.motion_program_id)
        if motion is not None:
            still = (
                camera.locked
                and motion.subject_motion.primitive is MotionPrimitive.STATIC
                and motion.environment_motion.primitive is MotionPrimitive.STATIC
            )
            if still and motion.intensity > 0:
                issues.append(
                    ValidationIssue(
                        rule=ValidationRule.LOGICAL_CONTRADICTION,
                        severity=Severity.BLOCKING,
                        subject_id=subject,
                        detail="plan entièrement immobile avec une intensité non nulle",
                        remedy="mettre l'intensité à zéro ou faire bouger quelque chose",
                    )
                )
        return issues

    @staticmethod
    def _check_resolution(spec, subject) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if spec.resolution.width % 2 or spec.resolution.height % 2:
            issues.append(
                ValidationIssue(
                    rule=ValidationRule.RESOLUTION_FORMAT,
                    severity=Severity.BLOCKING,
                    subject_id=subject,
                    detail=(
                        f"{spec.resolution.width}×{spec.resolution.height} : les "
                        "encodeurs usuels exigent des dimensions paires"
                    ),
                    remedy="arrondir la résolution au pixel pair",
                )
            )
        if spec.fps < 12:
            issues.append(
                ValidationIssue(
                    rule=ValidationRule.RESOLUTION_FORMAT,
                    severity=Severity.MAJOR,
                    subject_id=subject,
                    detail=f"{spec.fps} i/s : le mouvement sera saccadé",
                )
            )
        return issues

    def _check_capability(self, spec, subject) -> list[ValidationIssue]:
        """Ne jamais demander ce qu'aucun exécutant ne sait faire."""
        issues: list[ValidationIssue] = []
        if spec.preferred_strategy is not None:
            if spec.preferred_strategy not in self.available_strategies:
                issues.append(
                    ValidationIssue(
                        rule=ValidationRule.PROVIDER_CAPABILITY,
                        severity=Severity.BLOCKING,
                        subject_id=subject,
                        detail=(
                            f"stratégie {spec.preferred_strategy.value} demandée, "
                            "aucun exécutant ne la propose ici"
                        ),
                        remedy=(
                            "laisser le routeur choisir, ou n'exprimer qu'une "
                            "stratégie disponible"
                        ),
                    )
                )
        if spec.allow_ai_video and not (
            self.available_strategies & AI_VIDEO_STRATEGIES
        ):
            issues.append(
                ValidationIssue(
                    rule=ValidationRule.PROVIDER_CAPABILITY,
                    severity=Severity.MINOR,
                    subject_id=subject,
                    detail=(
                        "génération vidéo par IA autorisée mais aucun fournisseur "
                        "joignable : le plan sera rendu par une stratégie "
                        "déterministe, et la dégradation sera enregistrée"
                    ),
                )
            )
        return issues

    def _check_fallback(self, spec, subject) -> list[ValidationIssue]:
        """Livraison garantie : un repli local doit rester possible."""
        issues: list[ValidationIssue] = []
        local = self.available_strategies & DETERMINISTIC_STRATEGIES
        if not local:
            issues.append(
                ValidationIssue(
                    rule=ValidationRule.FALLBACK_AVAILABILITY,
                    severity=Severity.BLOCKING,
                    subject_id=subject,
                    detail="aucun repli déterministe disponible",
                    remedy=(
                        "activer au moins une stratégie locale "
                        "(still, ken_burns, parallax_2_5d, procedural)"
                    ),
                )
            )
        return issues

    @staticmethod
    def _check_evidence(spec, shots, subject) -> list[ValidationIssue]:
        shot = shots.get(subject)
        if shot is None or shot.claim_id is None:
            return []
        if not (shot.evidence_required or "").strip():
            return [
                ValidationIssue(
                    rule=ValidationRule.EVIDENCE_LINK,
                    severity=Severity.BLOCKING,
                    subject_id=subject,
                    detail=(
                        f"le plan démontre {shot.claim_id} sans dire ce qu'il faut "
                        "voir pour être convaincu"
                    ),
                    remedy="renseigner evidence_required dans le plan de preuve",
                )
            ]
        return []

    @staticmethod
    def _check_continuity(spec, shots, images, subject) -> list[ValidationIssue]:
        """Une ancre exigée doit être portée par les images du plan."""
        shot = shots.get(subject)
        if shot is None or not shot.continuity_dependencies:
            return []
        carried: set[str] = set()
        for ref in spec.image_spec_ids:
            image = images.get(ref)
            if image is not None:
                carried |= set(image.anchor_ids)
        missing = [a for a in shot.continuity_dependencies if a not in carried]
        if missing:
            return [
                ValidationIssue(
                    rule=ValidationRule.CONTINUITY,
                    severity=Severity.BLOCKING,
                    subject_id=subject,
                    detail=f"ancres exigées absentes des images : {missing}",
                    remedy="recompiler les spécifications d'image depuis le plan",
                )
            ]
        if shot.render_constraints.requires_identity_lock and not spec.identity_lock_required:
            return [
                ValidationIssue(
                    rule=ValidationRule.CONTINUITY,
                    severity=Severity.BLOCKING,
                    subject_id=subject,
                    detail="verrou d'identité exigé par le plan mais absent de la demande",
                    remedy="recompiler la demande depuis les contraintes du plan",
                )
            ]
        return []

    @staticmethod
    def _check_budget(
        requested: list[RenderSpecRequested], request: TopicRequest
    ) -> list[ValidationIssue]:
        if request.budget_cap_usd is None:
            return []
        caps = [spec.max_cost_usd for spec in requested if spec.max_cost_usd is not None]
        if len(caps) != len(requested):
            return [
                ValidationIssue(
                    rule=ValidationRule.BUDGET,
                    severity=Severity.MAJOR,
                    subject_id="episode",
                    detail=(
                        "un budget d'épisode est fixé mais tous les plans n'ont pas "
                        "de plafond : la dépense n'est pas bornée plan par plan"
                    ),
                )
            ]
        total = sum(caps)
        if total > request.budget_cap_usd + 1e-9:
            return [
                ValidationIssue(
                    rule=ValidationRule.BUDGET,
                    severity=Severity.BLOCKING,
                    subject_id="episode",
                    detail=(
                        f"la somme des plafonds de plan atteint {total:.4f} USD "
                        f"pour un budget de {request.budget_cap_usd:.4f} USD"
                    ),
                    remedy="baisser les plafonds de plan ou relever le budget",
                )
            ]
        return []
