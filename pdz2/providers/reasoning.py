"""La décision de réalisation, indépendamment de qui la prend.

Deux raisonneurs sont branchés — deux services, deux formes d'API, deux
factures. Ce qu'on leur demande, en revanche, est strictement le même, et
c'est ce module qui le tient :

* la **surface de décision** — les champs qu'aucun calcul ne peut produire —
  est dérivée du contrat `DirectorBrief`, jamais recopiée ;
* la **consigne** est écrite une fois ;
* le **scellement** ajoute ce que le modèle n'a pas à décider ;
* la **boucle de reprise** renvoie une décision refusée au modèle avec
  l'erreur exacte du contrat, une seule fois, puis abandonne.

Un adaptateur ne fournit qu'une chose : `demander(échanges) -> dict`. Tout le
reste vit ici. Sans cette séparation, la surface de décision existerait en
deux exemplaires qui divergeraient au premier changement de contrat — le
motif précis que ce dépôt traque.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from pdz2.contracts.direction import DirectorBrief
from pdz2.contracts.research import ResearchState, TopicRequest
from pdz2.engines.direction.ports import ReasonerUnavailable

__all__ = [
    "DECIDED_BY_THE_REASONER",
    "decision_schema",
    "SYSTEM",
    "instruction",
    "seal",
    "draft_with",
    "ATTEMPTS",
]

ATTEMPTS = 2
"""Une tentative, plus une reprise avec l'erreur de validation en main."""


DECIDED_BY_THE_REASONER = (
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


_BRUIT = frozenset({"default", "title"})
"""Clés retirées du schéma envoyé.

`default` parce que le modèle doit trancher, et non hériter d'une valeur.
`title` parce que pydantic le fabrique depuis le nom du champ — que le modèle
lit déjà juste à côté. Deux cent soixante-cinq jetons de redite, sur un
plafond qui en compte huit mille."""


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

    clean = {key: _strict(value) for key, value in node.items() if key not in _BRUIT}
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
        name: _without_null(full["properties"][name]) for name in DECIDED_BY_THE_REASONER
    }
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required": list(DECIDED_BY_THE_REASONER),
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


SYSTEM = """Tu es le réalisateur d'un épisode documentaire court.

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


def instruction(request: TopicRequest, research: ResearchState) -> str:
    """La demande adressée au modèle : le sujet, et les faits établis.

    Elle ne contient **pas** de gabarit de brief. Il y en a eu un, recopié en
    JSON dans le message, et c'était une redondance coûteuse : le schéma
    envoyé décrit déjà la forme attendue, plus strictement qu'un exemple, et
    les affirmations que le gabarit rappelait sont dans le relevé ci-dessous.
    Mille jetons pour redire deux fois la même chose — mesuré, puis retiré
    quand un fournisseur au palier gratuit a refusé la requête.
    """
    return (
        f"SUJET : {request.topic}\n"
        f"LANGUE DE L'ÉPISODE : {request.language}\n"
        f"PUBLIC VISÉ : {request.audience}\n"
        f"TON DEMANDÉ : {request.tone.value}\n"
        f"QUESTION DE RECHERCHE : {research.question}\n"
        f"COUVERTURE MESURÉE : {research.coverage:.2f}\n\n"
        "AFFIRMATIONS ÉTABLIES (classées par démontrabilité mesurée) :\n"
        f"{_research_digest(research)}\n\n"
        "Rends la décision de réalisation. Retiens entre trois et six "
        "affirmations, celles qui se démontrent le mieux à l'image."
    )


# --------------------------------------------------- scellement et reprise


def seal(
    decision: dict[str, Any],
    request: TopicRequest,
    research: ResearchState,
    author: str,
) -> DirectorBrief:
    """Ajoute ce que le modèle n'a pas à décider, puis laisse le contrat juger.

    L'identité du dossier et la signature ne sont jamais demandées au
    modèle : elles sont connues de l'appelant, et les lui faire écrire
    reviendrait à lui permettre de se tromper de dossier.
    """
    return DirectorBrief.model_validate(
        {
            **decision,
            "topic_request_id": request.id,
            "research_state_id": research.id,
            "author": author,
        }
    )


def draft_with(
    demander: Callable[[list[dict[str, Any]]], dict[str, Any]],
    *,
    request: TopicRequest,
    research: ResearchState,
    author: str,
) -> DirectorBrief:
    """Obtient une décision valide, ou lève. Ne complète jamais rien lui-même.

    `demander` est le seul apport de l'adaptateur : il reçoit l'historique
    au format rôle/contenu et rend la décision brute. Tout le jugement est
    ici, et il appartient au contrat.
    """
    echanges: list[dict[str, Any]] = [
        {"role": "user", "content": instruction(request, research)}
    ]
    refus = ""

    for tentative in range(ATTEMPTS):
        brut = demander(echanges)
        try:
            return seal(brut, request, research, author)
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
            if tentative + 1 == ATTEMPTS:
                break

    raise ReasonerUnavailable(
        f"{author} : {ATTEMPTS} décisions refusées par le contrat — {refus}"
    )
