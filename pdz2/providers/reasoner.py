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

from pydantic import ValidationError

from pdz2.contracts.capability import CapabilityState, ProviderCapability
from pdz2.contracts.direction import DirectorBrief
from pdz2.contracts.research import ResearchState, TopicRequest
from pdz2.engines.direction.ports import ReasonerUnavailable, brief_template

__all__ = ["AnthropicReasoner", "ANTHROPIC_KEY_ENV", "DEFAULT_MODEL"]

ANTHROPIC_KEY_ENV = "ANTHROPIC_API_KEY"
DEFAULT_MODEL = "claude-opus-5"

_PROBE_TIMEOUT_S = 20.0
_DECISION_TIMEOUT_S = 600.0
_MAX_TOKENS = 16000
_ATTEMPTS = 2
"""Une tentative, plus une reprise avec l'erreur de validation en main."""

_DECIDED_BY_THE_REASONER = (
    "thesis",
    "audience",
    "tone",
    "pacing",
    "ending_payoff",
    "visual_language",
    "visual_style",
    "anchors",
    "visual_proofs",
    "excluded_claim_ids",
)
"""Ce que le raisonneur décide. Tout le reste du brief est su, pas décidé.

Les *types* de ces champs ne sont pas écrits ici : ils sont lus dans le schéma
JSON du contrat. Cette liste ne dit que « qui décide quoi »."""


# --------------------------------------------------------------------- schéma


def _strict(node: Any) -> Any:
    """Rend un fragment de schéma acceptable par un *structured output*.

    Trois transformations, toutes imposées par le service : plus de valeur par
    défaut (le modèle doit trancher), tout champ présent est requis, et aucun
    champ supplémentaire n'est toléré — exactement la règle `extra="forbid"`
    des contrats, portée jusqu'au modèle.
    """
    if isinstance(node, list):
        return [_strict(item) for item in node]
    if not isinstance(node, dict):
        return node

    clean = {key: _strict(value) for key, value in node.items() if key != "default"}
    if clean.get("type") == "object" and "properties" in clean:
        clean["required"] = sorted(clean["properties"])
        clean["additionalProperties"] = False
    return clean


def _without_null(node: dict[str, Any]) -> dict[str, Any]:
    """Déplie `X | None` en `X` : un champ demandé au modèle n'est pas facultatif."""
    branches = node.get("anyOf")
    if not branches:
        return node
    kept = [b for b in branches if b.get("type") != "null"]
    if len(kept) != 1:
        return node
    return {**{k: v for k, v in node.items() if k != "anyOf"}, **kept[0]}


def decision_schema() -> dict[str, Any]:
    """Le schéma de la décision, dérivé du contrat — jamais recopié.

    Exposé (et non privé) parce qu'un test doit pouvoir vérifier qu'il suit le
    contrat sans passer par le réseau.
    """
    full = DirectorBrief.model_json_schema()
    properties = {
        name: _without_null(full["properties"][name]) for name in _DECIDED_BY_THE_REASONER
    }
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required": list(_DECIDED_BY_THE_REASONER),
        "additionalProperties": False,
    }
    defs = _reachable_defs(properties, full.get("$defs", {}))
    if defs:
        schema["$defs"] = defs
    return _strict(schema)


def _reachable_defs(root: Any, defs: dict[str, Any]) -> dict[str, Any]:
    """Ne garde que les définitions réellement citées.

    Le schéma du contrat entier en porte d'autres (le statut de cycle de vie,
    par exemple) : les envoyer décrirait au modèle des champs qu'on ne lui
    demande pas.
    """

    def refs(node: Any) -> set[str]:
        if isinstance(node, list):
            return set().union(*(refs(item) for item in node)) if node else set()
        if not isinstance(node, dict):
            return set()
        found = {node["$ref"].rsplit("/", 1)[-1]} if "$ref" in node else set()
        for value in node.values():
            found |= refs(value)
        return found

    vus: set[str] = set()
    a_voir = refs(root)
    while a_voir:
        nom = a_voir.pop()
        if nom in vus or nom not in defs:
            continue
        vus.add(nom)
        a_voir |= refs(defs[nom])
    return {nom: defs[nom] for nom in sorted(vus)}


# ---------------------------------------------------------------------- texte


def _research_digest(research: ResearchState, *, max_claims: int = 12) -> str:
    """Ce que le modèle a le droit de savoir : les affirmations mesurées.

    On ne lui envoie ni les sources brutes ni les preuves : il ne refait pas la
    recherche, il décide *quoi montrer* de ce qui a déjà été établi.
    """
    ranked = sorted(
        research.claims,
        key=lambda claim: (-claim.demonstrability, -claim.confidence, claim.id),
    )[:max_claims]
    lignes = [
        f"- {claim.id} | démontrabilité {claim.demonstrability:.2f} | "
        f"confiance {claim.confidence:.2f} | {claim.verification.value}"
        f"{' | PORTANTE' if claim.load_bearing else ''}\n  {claim.text}"
        for claim in ranked
    ]
    return "\n".join(lignes)


_SYSTEM = """Tu es le réalisateur d'un épisode documentaire court.

Tu prends la seule décision que le compilateur ne peut pas calculer : ce que
l'épisode démontre, et ce que le spectateur doit physiquement voir pour que ce
soit démontré. Tout le reste — découpage, durées, courbes, densité, stratégie
de rendu — est déduit ensuite par des compilateurs déterministes. Ne les
anticipe pas : ne parle jamais de plans, de secondes, de résolution, de
fournisseur ni de modèle.

Règles dures :
- Une preuve visuelle décrit une image concrète, filmable, à l'écran. « la
  complexité du système » n'est pas une preuve visuelle ; « la came pousse le
  poussoir de 8 mm et la soupape s'ouvre, vue en coupe » en est une.
- Deux affirmations différentes ne peuvent pas partager le même mécanisme
  causal : si tu ne sais pas les distinguer, exclus-en une.
- Une ancre de continuité est une entité qui doit rester identique d'une image
  à l'autre. Chaque ancre porte au moins un trait d'identité « fixed ».
- N'invente aucun fait : tu ne disposes que des affirmations fournies. Une
  affirmation que tu ne retiens pas va dans `excluded_claim_ids`.
- Écris dans la langue de l'épisode, indiquée avec la commande."""


def _instruction(
    request: TopicRequest,
    research: ResearchState,
    gabarit: dict[str, Any],
) -> str:
    return (
        f"SUJET : {request.topic}\n"
        f"LANGUE DE L'ÉPISODE : {request.language}\n"
        f"PUBLIC VISÉ : {request.audience}\n"
        f"TON DEMANDÉ : {request.tone.value}\n"
        f"QUESTION DE RECHERCHE : {research.question}\n"
        f"COUVERTURE MESURÉE : {research.coverage:.2f}\n\n"
        "AFFIRMATIONS ÉTABLIES (classées par démontrabilité mesurée) :\n"
        f"{_research_digest(research)}\n\n"
        "GABARIT DE RÉFÉRENCE — il rappelle la forme attendue ; les clés « _ » "
        "sont des annotations et ne doivent pas apparaître dans ta réponse :\n"
        f"{json.dumps(gabarit, ensure_ascii=False, indent=2)}\n\n"
        "Rends la décision de réalisation. Retiens entre trois et six "
        "affirmations, celles qui se démontrent le mieux à l'image."
    )


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
        gabarit = brief_template(request, research)
        echanges: list[dict[str, Any]] = [
            {"role": "user", "content": _instruction(request, research, gabarit)}
        ]
        refus: str = ""

        for tentative in range(_ATTEMPTS):
            brut = self._decide(client, echanges)
            try:
                return self._sceller(brut, request, research)
            except ValidationError as erreur:
                refus = str(erreur)
                echanges = [
                    *echanges,
                    {"role": "assistant", "content": json.dumps(brut, ensure_ascii=False)},
                    {
                        "role": "user",
                        "content": (
                            "Le contrat a refusé cette décision. Corrige "
                            "exactement ce qui est reproché, sans rien "
                            f"réécrire d'autre :\n{refus}"
                        ),
                    },
                ]
                if tentative + 1 == _ATTEMPTS:
                    break

        raise ReasonerUnavailable(
            f"{self.name} : {_ATTEMPTS} décisions refusées par le contrat — {refus}"
        )

    def _decide(self, client, echanges: list[dict[str, Any]]) -> dict[str, Any]:
        """Un aller-retour. Le flux évite d'expirer sur une réponse longue."""
        try:
            with client.messages.stream(
                model=self.model,
                max_tokens=_MAX_TOKENS,
                system=_SYSTEM,
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

    def _sceller(
        self,
        decision: dict[str, Any],
        request: TopicRequest,
        research: ResearchState,
    ) -> DirectorBrief:
        """Ajoute ce que le modèle n'a pas à décider, puis laisse le contrat juger."""
        return DirectorBrief.model_validate(
            {
                **decision,
                "topic_request_id": request.id,
                "research_state_id": research.id,
                "author": self.name,
            }
        )
