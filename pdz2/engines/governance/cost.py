"""Gouverneur de coût : autoriser avant, constater après.

Un compteur qui additionne les dépenses passées ne gouverne rien. Ce
gouverneur **autorise** : on lui demande la permission avant d'engager une
dépense, et il refuse celle qui ferait franchir le plafond.

Trois refus distincts, parce qu'ils appellent trois réactions différentes :

    BUDGET_EXHAUSTED   il ne reste plus rien : arrêter
    WOULD_EXCEED       cette dépense-ci passerait au-dessus : la réduire
    UNMEASURED_COST    on ignore ce que ça coûte : mesurer d'abord

Le dernier est le plus important. Engager une dépense dont on ne connaît pas
le montant, c'est perdre le contrôle du budget d'un seul coup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from pdz2.contracts.capacity import (
    CapabilityMatrix,
    CostLedger,
    Provenance,
    SpendRecord,
)
from pdz2.contracts.pipeline import Stage

__all__ = ["CostGovernor", "SpendDecision", "Refusal", "CostRefused"]


class Refusal(str, Enum):
    BUDGET_EXHAUSTED = "budget_exhausted"
    WOULD_EXCEED = "would_exceed"
    UNMEASURED_COST = "unmeasured_cost"


class CostRefused(RuntimeError):
    """Une dépense a été refusée avant d'avoir lieu."""

    def __init__(self, reason: Refusal, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason


@dataclass(frozen=True)
class SpendDecision:
    allowed: bool
    reason: Refusal | None
    detail: str
    remaining_usd: float | None


@dataclass
class CostGovernor:
    """Autorise ou refuse une dépense, plafond en main."""

    ledger: CostLedger
    matrix: CapabilityMatrix | None = None
    notes: list[str] = field(default_factory=list)

    # ------------------------------------------------------------ autorisation

    def may_spend(
        self,
        amount_usd: float,
        *,
        stage: Stage,
        provider: str | None = None,
        model: str | None = None,
    ) -> SpendDecision:
        """Demande la permission. Ne dépense rien."""
        if amount_usd < 0:
            raise ValueError("une dépense négative n'existe pas")
        remaining = self.ledger.remaining_usd

        if provider and model and self.matrix is not None:
            unmeasured = self._unmeasured_cost(provider, model)
            if unmeasured is not None:
                return SpendDecision(
                    allowed=False,
                    reason=Refusal.UNMEASURED_COST,
                    detail=unmeasured,
                    remaining_usd=remaining,
                )

        if remaining is None:
            return SpendDecision(
                allowed=True,
                reason=None,
                detail="aucun plafond déclaré",
                remaining_usd=None,
            )
        if remaining <= 0:
            return SpendDecision(
                allowed=False,
                reason=Refusal.BUDGET_EXHAUSTED,
                detail=(
                    f"budget épuisé : {self.ledger.spent_usd:.4f} sur "
                    f"{self.ledger.budget_cap_usd:.4f} USD"
                ),
                remaining_usd=remaining,
            )
        if amount_usd > remaining + 1e-9:
            return SpendDecision(
                allowed=False,
                reason=Refusal.WOULD_EXCEED,
                detail=(
                    f"{amount_usd:.4f} USD demandés pour {remaining:.4f} USD "
                    f"restants à l'étape « {stage.value} »"
                ),
                remaining_usd=remaining,
            )
        return SpendDecision(
            allowed=True,
            reason=None,
            detail=f"{remaining - amount_usd:.4f} USD resteront",
            remaining_usd=remaining,
        )

    def spend(
        self,
        amount_usd: float,
        *,
        stage: Stage,
        shot_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        detail: str = "",
    ) -> SpendRecord:
        """Engage une dépense après l'avoir fait autoriser. Refuse sinon."""
        decision = self.may_spend(
            amount_usd, stage=stage, provider=provider, model=model
        )
        if not decision.allowed:
            assert decision.reason is not None
            raise CostRefused(decision.reason, decision.detail)
        record = SpendRecord(
            stage=stage.value,
            shot_id=shot_id,
            provider=provider,
            amount_usd=round(amount_usd, 6),
            at=datetime.now(UTC),
            detail=detail,
        )
        self.ledger.records.append(record)
        return record

    # ------------------------------------------------------------- estimation

    def estimate(
        self, *, provider: str, model: str, seconds: float
    ) -> float | None:
        """Coût attendu d'une génération, **seulement s'il est mesuré**.

        Rendre `None` plutôt qu'un chiffre annoncé : une estimation fondée sur
        une brochure n'est pas une estimation, c'est un pari.
        """
        if self.matrix is None:
            return None
        entry = self.matrix.entry(provider, model)
        if entry is None:
            return None
        value = entry.value("cost_per_second_usd")
        if value is None or not value.trustworthy(days=self.matrix.freshness_days):
            return None
        return round((value.value or 0.0) * seconds, 6)

    def _unmeasured_cost(self, provider: str, model: str) -> str | None:
        assert self.matrix is not None
        entry = self.matrix.entry(provider, model)
        if entry is None:
            return (
                f"{provider}/{model} absent de la matrice de capacités : "
                "on ignore ce que cette dépense coûte"
            )
        value = entry.value("cost_per_second_usd")
        if value is None:
            return (
                f"{provider}/{model} : aucun coût par seconde enregistré — "
                "mesurer avant d'engager"
            )
        if value.provenance is Provenance.ANNOUNCED:
            return (
                f"{provider}/{model} : coût seulement ANNONCÉ par le fournisseur, "
                "jamais vérifié — une brochure n'est pas une mesure"
            )
        if not value.trustworthy(days=self.matrix.freshness_days):
            return (
                f"{provider}/{model} : coût mesuré le "
                f"{value.measured_at:%Y-%m-%d}, périmé au-delà de "
                f"{self.matrix.freshness_days} jours — re-mesurer"
            )
        return None
