"""Port du raisonneur.

Le Director Core a besoin d'une décision conceptuelle. Il ne lui importe pas
qu'elle vienne d'un modèle de langue ou d'un humain : il exige un
`DirectorBrief` valide, et refuse d'inventer à la place de qui que ce soit.

**État réel dans ce dépôt : aucun adaptateur de raisonneur n'est implémenté.**
Ce n'est pas un oubli, c'est une contrainte déclarée. Le seul chemin
disponible aujourd'hui est le brief rédigé à la main (`load_brief`). Écrire un
adaptateur HTTP qu'on ne peut ni joindre ni vérifier depuis cet environnement
reviendrait à livrer une capacité fictive — précisément ce que le cahier des
charges interdit.

Quand un raisonneur sera branché, il implémentera ce protocole et déclarera sa
capacité comme les autres : mesurée, datée, ou UNKNOWN.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from pdz2.contracts.research import ResearchState, TopicRequest
from pdz2.engines.direction.brief import DirectorBrief
from pdz2.engines.research.ports import ProviderCapability

__all__ = ["Reasoner", "ReasonerUnavailable", "load_brief", "save_brief", "brief_template"]


class ReasonerUnavailable(RuntimeError):
    """Aucun raisonneur utilisable pour produire la décision de réalisation."""


@runtime_checkable
class Reasoner(Protocol):
    """Producteur de décisions conceptuelles."""

    name: str

    def get_capabilities(self) -> ProviderCapability:
        """Sonde réellement le raisonneur."""

    def draft_brief(
        self,
        request: TopicRequest,
        research: ResearchState,
    ) -> DirectorBrief:
        """Retourne un brief valide, ou lève `ReasonerUnavailable`."""


def _strip_help_keys(value):
    """Retire les clés d'aide `_...` qu'un gabarit ajoute pour le rédacteur.

    Le contrat refuse les champs inconnus — c'est voulu. Mais un gabarit doit
    pouvoir rappeler au rédacteur *quelle affirmation* il est en train de
    démontrer. Ces rappels sont préfixés d'un tiret bas et disparaissent ici.
    """
    if isinstance(value, dict):
        return {
            key: _strip_help_keys(item)
            for key, item in value.items()
            if not key.startswith("_")
        }
    if isinstance(value, list):
        return [_strip_help_keys(item) for item in value]
    return value


def load_brief(path: Path | str) -> DirectorBrief:
    """Lit un brief rédigé à la main. Un brief invalide est refusé, pas rattrapé."""
    payload = _strip_help_keys(json.loads(Path(path).read_text(encoding="utf-8")))
    payload.setdefault("contract_type", DirectorBrief.CONTRACT_NAME)
    return DirectorBrief.model_validate(payload)


def save_brief(brief: DirectorBrief, path: Path | str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(brief.to_payload(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def brief_template(
    request: TopicRequest,
    research: ResearchState,
    *,
    max_proofs: int = 6,
) -> dict:
    """Gabarit de brief à remplir, dérivé de l'état de recherche.

    Le gabarit **ne rédige rien**. Il classe les affirmations par
    démontrabilité mesurée et par confiance, rappelle leur texte, et laisse
    vides les champs que seul un humain — ou un raisonneur — peut écrire. Un
    gabarit non rempli est refusé par le contrat : c'est le comportement
    voulu, pas un accident.
    """
    ranked = sorted(
        research.claims,
        key=lambda claim: (-claim.demonstrability, -claim.confidence, claim.id),
    )[:max_proofs]
    return {
        "_help": (
            "Remplir chaque champ vide. Les clés commençant par « _ » sont des "
            "rappels et sont ignorées à la lecture. Une preuve visuelle décrit ce "
            "que le spectateur voit à l'écran, pas un thème."
        ),
        "topic_request_id": request.id,
        "research_state_id": research.id,
        "thesis": "",
        "audience": request.audience,
        "tone": request.tone.value,
        "pacing": "measured",
        "ending_payoff": "",
        "visual_language": {"visual_register": "", "metaphors": [],
                            "forbidden_imagery": [], "recurring_motifs": []},
        "anchors": [
            {
                "name": "",
                "kind": "machine",
                "canonical_description": "",
                "identity": [{"name": "", "value": "", "binding": "fixed"}],
            }
        ],
        "visual_proofs": [
            {
                "_claim_text": claim.text,
                "_verification": claim.verification.value,
                "_confidence": claim.confidence,
                "_demonstrability": claim.demonstrability,
                "claim_id": claim.id,
                "causal_mechanism": "",
                "evidence_required": "",
                "visual_proof": "",
                "anchor_names": [],
                "acknowledged_dispute": False,
            }
            for claim in ranked
        ],
        "excluded_claim_ids": [],
        "author": "human",
    }
