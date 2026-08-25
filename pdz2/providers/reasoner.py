"""Adaptateur de raisonneur — le modèle Anthropic décide, le contrat contraint.

    ⚠️ LA DÉCISION N'A JAMAIS ÉTÉ OBTENUE DANS L'ENVIRONNEMENT OÙ CE CODE A
    ÉTÉ ÉCRIT : aucune clé valide n'y est présente.

    La sonde, en revanche, a été **réellement exercée** contre le service, à
    la différence des autres adaptateurs de ce paquet. Avec une clé
    volontairement fausse elle rend :

        unavailable | modèle claude-opus-5 inaccessible : Error code: 401 —
        {'type': 'error', 'error': {'type': 'authentication_error', …}}

    Ce qui est donc vérifié ici : le chemin réseau, l'usage du SDK, le point
    d'entrée, et le traitement de l'erreur. Ce qui ne l'est pas : la décision
    elle-même. Son premier vrai `draft_brief()` a lieu dans GitHub Actions.

Ce module est le seul de PDZ 2 où un modèle de langue a le droit de *décider*.
Il ne lui laisse pour autant aucune liberté de forme :

* la **surface de décision** — les champs qu'aucun calcul ne peut produire —
  est dérivée du contrat `DirectorBrief` lui-même (`_DECIDED_BY_THE_REASONER`),
  jamais recopiée à la main ; le jour où le contrat change, le schéma envoyé
  au modèle change avec lui ;
* la réponse est contrainte par un *structured output* bâti sur ce schéma ;
* elle est ensuite **validée par le contrat**, pas par une relecture humaine.
  Un brief invalide n'est pas rattrapé : il est renvoyé au modèle une fois
  avec l'erreur exacte, et si la seconde tentative échoue, l'adaptateur lève
  `ReasonerUnavailable`. Il ne complète jamais lui-même une décision.

L'identité (`topic_request_id`, `research_state_id`) et l'attribution
(`author`) ne sont pas demandées au modèle : elles sont connues de l'appelant,
et les faire écrire par un raisonneur reviendrait à lui permettre de se
tromper de dossier.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pdz2.contracts.capability import CapabilityState, ProviderCapability
from pdz2.contracts.direction import DirectorBrief
from pdz2.contracts.research import ResearchState, TopicRequest
from pdz2.engines.direction.ports import ReasonerUnavailable
from pdz2.providers.reasoning import SYSTEM, decision_schema, draft_with

__all__ = ["AnthropicReasoner", "ANTHROPIC_KEY_ENV", "DEFAULT_MODEL"]

ANTHROPIC_KEY_ENV = "ANTHROPIC_API_KEY"
DEFAULT_MODEL = "claude-opus-5"

_PROBE_TIMEOUT_S = 20.0
_DECISION_TIMEOUT_S = 600.0
_MAX_TOKENS = 16000
_ATTEMPTS = 2
"""Une tentative, plus une reprise avec l'erreur de validation en main."""

# ------------------------------------------------------------------ adaptateur


@dataclass
class AnthropicReasoner:
    """Raisonneur distant. Décide le brief ; ne calcule rien d'autre."""

    name: str = "anthropic"
    model: str = DEFAULT_MODEL
    effort: str = "high"
    _last_usage: dict[str, int] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------ sonde

    def _cle(self) -> str | None:
        return os.environ.get(ANTHROPIC_KEY_ENV, "").strip() or None

    def _client(self, timeout: float):
        """Charge le SDK officiel à l'appel : son absence est une indisponibilité.

        L'import est local pour que `pdz2` reste importable sans la dépendance
        — un dépôt qui n'appelle pas de raisonneur n'a pas à l'installer.
        """
        try:
            from anthropic import Anthropic
        except ImportError as erreur:  # pragma: no cover - dépend de l'install
            raise ReasonerUnavailable(
                "SDK « anthropic » absent : `pip install .[providers]`"
            ) from erreur
        return Anthropic(api_key=self._cle(), timeout=timeout)

    def get_capabilities(self) -> ProviderCapability:
        cle = self._cle()
        if cle is None:
            return self._capacite(False, f"{ANTHROPIC_KEY_ENV} absente de l'environnement")
        try:
            client = self._client(_PROBE_TIMEOUT_S)
        except ReasonerUnavailable as erreur:
            return self._capacite(False, str(erreur))
        try:
            fiche = client.models.retrieve(self.model)
        except Exception as erreur:  # noqa: BLE001 - toute panne est une indispo
            return self._capacite(False, f"modèle {self.model} inaccessible : {erreur}")
        return self._capacite(True, f"modèle {getattr(fiche, 'id', self.model)} confirmé")

    def _capacite(self, joignable: bool, detail: str) -> ProviderCapability:
        return ProviderCapability(
            provider=self.name,
            state=CapabilityState.AVAILABLE if joignable else CapabilityState.UNAVAILABLE,
            measured_at=datetime.now(UTC),
            measurement_method=f"GET /v1/models/{self.model}",
            detail=detail,
            requires_network=True,
            requires_credentials=True,
        )

    # --------------------------------------------------------------- décision

    def draft_brief(self, request: TopicRequest, research: ResearchState) -> DirectorBrief:
        capacite = self.get_capabilities()
        if not capacite.usable:
            raise ReasonerUnavailable(f"{self.name} : {capacite.detail}")

        client = self._client(_DECISION_TIMEOUT_S)
        return draft_with(
            lambda echanges: self._decide(client, echanges),
            request=request,
            research=research,
            author=self.name,
        )

    def _decide(self, client, echanges: list[dict[str, Any]]) -> dict[str, Any]:
        """Un aller-retour. Le flux évite d'expirer sur une réponse longue."""
        try:
            with client.messages.stream(
                model=self.model,
                max_tokens=_MAX_TOKENS,
                system=SYSTEM,
                messages=echanges,
                thinking={"type": "adaptive"},
                output_config={
                    "effort": self.effort,
                    "format": {"type": "json_schema", "schema": decision_schema()},
                },
            ) as flux:
                message = flux.get_final_message()
        except Exception as erreur:  # noqa: BLE001 - une panne réseau est une indispo
            raise ReasonerUnavailable(f"{self.name} : appel impossible ({erreur})") from erreur

        usage = getattr(message, "usage", None)
        if usage is not None:
            self._last_usage = {
                "input_tokens": getattr(usage, "input_tokens", 0),
                "output_tokens": getattr(usage, "output_tokens", 0),
            }
        texte = "".join(
            bloc.text for bloc in message.content if getattr(bloc, "type", "") == "text"
        )
        try:
            decision = json.loads(texte)
        except json.JSONDecodeError as erreur:
            raise ReasonerUnavailable(
                f"{self.name} : réponse illisible malgré le schéma imposé ({erreur})"
            ) from erreur
        if not isinstance(decision, dict):
            raise ReasonerUnavailable(f"{self.name} : décision de type {type(decision).__name__}")
        return decision
