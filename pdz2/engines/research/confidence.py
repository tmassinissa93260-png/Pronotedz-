"""Modèle de confiance déterministe.

La confiance n'est pas une intuition de modèle : c'est une fonction, écrite
ici, de quantités observables. Deux exécutions sur les mêmes preuves donnent
le même chiffre, et n'importe qui peut contester la formule.

    base        = max sur les preuves favorables de (autorité × force)
    corroboration = bonus décroissant par source indépendante supplémentaire
    contradiction = pénalité proportionnelle à la meilleure preuve contraire
    confiance   = clamp(base + corroboration − contradiction)

Puis les plafonds du contrat s'appliquent : sans preuve, la confiance est
nulle ; tant que la vérification n'a pas conclu, elle reste sous le plafond
`UNVERIFIED_CONFIDENCE_CEILING`. Le contrat `Claim` refuserait de toute façon
un dépassement — la fonction ne s'appuie pas sur cette dernière barrière, elle
la respecte en amont.
"""

from __future__ import annotations

from dataclasses import dataclass

from pdz2.contracts.research import (
    UNVERIFIED_CONFIDENCE_CEILING,
    EvidenceStance,
    VerificationStatus,
)

__all__ = [
    "EvidenceSignal",
    "ConfidenceModel",
    "ConfidenceOutcome",
    "CORROBORATION_STEPS",
]

CORROBORATION_STEPS = (0.12, 0.07, 0.04)
"""Bonus par source indépendante au-delà de la première. Rendements décroissants :
la deuxième source vaut beaucoup, la cinquième presque rien."""


@dataclass(frozen=True)
class EvidenceSignal:
    """Une preuve réduite à ce qui compte pour le calcul."""

    source_key: str
    """Identité de la source. Deux preuves d'une même source ne corroborent pas."""

    stance: EvidenceStance
    strength: float
    authority: float

    @property
    def weight(self) -> float:
        return max(0.0, min(1.0, self.strength * self.authority))


@dataclass(frozen=True)
class ConfidenceOutcome:
    confidence: float
    verification: VerificationStatus
    supporting_sources: int
    contradicting_sources: int
    explanation: str


@dataclass(frozen=True)
class ConfidenceModel:
    """Paramètres du calcul. Tous nommés, tous discutables."""

    corroboration_threshold: int = 2
    """Nombre de sources indépendantes concordantes pour conclure."""

    minimum_base_to_conclude: float = 0.35
    """En-dessous, même corroborée, l'affirmation reste non vérifiée."""

    contradiction_weight: float = 0.9
    dispute_ratio: float = 0.6
    """Si la meilleure preuve contraire atteint cette fraction de la meilleure
    preuve favorable, l'affirmation est disputée."""

    def evaluate(self, signals: list[EvidenceSignal]) -> ConfidenceOutcome:
        if not signals:
            return ConfidenceOutcome(
                confidence=0.0,
                verification=VerificationStatus.UNVERIFIED,
                supporting_sources=0,
                contradicting_sources=0,
                explanation="aucune preuve rattachée",
            )

        supporting = [s for s in signals if s.stance is EvidenceStance.SUPPORTS]
        contradicting = [s for s in signals if s.stance is EvidenceStance.CONTRADICTS]
        supporting_sources = {s.source_key for s in supporting}
        contradicting_sources = {s.source_key for s in contradicting}

        base = max((s.weight for s in supporting), default=0.0)
        best_against = max((s.weight for s in contradicting), default=0.0)

        bonus = 0.0
        for index in range(max(0, len(supporting_sources) - 1)):
            bonus += CORROBORATION_STEPS[min(index, len(CORROBORATION_STEPS) - 1)]

        penalty = self.contradiction_weight * best_against
        raw = base + bonus - penalty
        confidence = max(0.0, min(1.0, raw))

        verification, reason = self._verdict(
            base=base,
            best_against=best_against,
            supporting_sources=len(supporting_sources),
            contradicting_sources=len(contradicting_sources),
        )

        if verification is VerificationStatus.REFUTED:
            confidence = 0.0
        elif verification is VerificationStatus.UNVERIFIED:
            confidence = min(confidence, UNVERIFIED_CONFIDENCE_CEILING)

        explanation = (
            f"base {base:.2f} + corroboration {bonus:.2f} − contradiction "
            f"{penalty:.2f} → {confidence:.2f} ; {reason}"
        )
        return ConfidenceOutcome(
            confidence=round(confidence, 4),
            verification=verification,
            supporting_sources=len(supporting_sources),
            contradicting_sources=len(contradicting_sources),
            explanation=explanation,
        )

    def _verdict(
        self,
        *,
        base: float,
        best_against: float,
        supporting_sources: int,
        contradicting_sources: int,
    ) -> tuple[VerificationStatus, str]:
        if contradicting_sources and base == 0.0:
            return (
                VerificationStatus.REFUTED,
                "aucune preuve favorable face à une preuve contraire",
            )
        if contradicting_sources and best_against >= self.dispute_ratio * base:
            return (
                VerificationStatus.DISPUTED,
                f"{contradicting_sources} source(s) contraire(s) de poids comparable",
            )
        if (
            supporting_sources >= self.corroboration_threshold
            and base >= self.minimum_base_to_conclude
        ):
            return (
                VerificationStatus.CORROBORATED,
                f"{supporting_sources} sources indépendantes concordantes",
            )
        if supporting_sources:
            return (
                VerificationStatus.UNVERIFIED,
                f"{supporting_sources} source(s) seulement, sous le seuil de "
                f"corroboration ({self.corroboration_threshold})",
            )
        return (VerificationStatus.UNVERIFIED, "aucune preuve favorable")
