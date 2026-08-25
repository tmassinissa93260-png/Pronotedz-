"""Construction du Fact Graph.

Les arêtes ne sont pas devinées : chacune vient d'une règle nommée, et une
arête qui créerait un cycle est refusée. Le graphe reste donc acyclique par
construction, ce que le contrat `FactGraph` revérifie de son côté.

Règles, appliquées dans cet ordre :

  1. SEQUENCE   — dans un même document, une affirmation de conséquence suit
                  la dernière affirmation de mécanisme qui la précède.
  2. QUANTIFIES — une affirmation chiffrée chiffre le mécanisme dont elle
                  partage le vocabulaire.
  3. ENABLES    — une définition rend intelligibles les affirmations qui
                  emploient le terme qu'elle définit.

Chaque arête porte son explication : le graphe se lit sans le code.
"""

from __future__ import annotations

from dataclasses import dataclass

from pdz2.contracts.research import CausalEdge, CausalRelation, ClaimKind
from pdz2.engines.research.text import jaccard, normalise, overlap, tokens

__all__ = ["GraphNode", "build_edges", "EdgeRules"]


@dataclass(frozen=True)
class GraphNode:
    """Une affirmation vue par le constructeur de graphe."""

    claim_id: str
    text: str
    kind: ClaimKind
    document_index: int
    sentence_index: int


@dataclass(frozen=True)
class EdgeRules:
    sequence_similarity: float = 0.15
    """Vocabulaire partagé minimal pour relier deux phrases éloignées."""

    sequence_adjacency: int = 2
    """Deux phrases aussi proches dans un document s'enchaînent sans exiger de
    vocabulaire commun : « le stator génère un champ » puis « le rotor s'aligne
    sur ce champ, donc l'arbre tourne » ne partagent presque aucun mot, et
    pourtant la seconde découle de la première. L'adjacence *est* le signal."""

    quantifies_overlap: float = 0.25
    """Recouvrement minimal entre une grandeur et le mécanisme qu'elle chiffre.

    Mesuré sur de la prose technique : les liens réels se situent au-dessus de
    0,25, les paires sans rapport tombent exactement à 0,00. Le seuil est posé
    dans ce fossé."""

    enables_overlap: float = 0.10
    """Recouvrement minimal entre une définition et ce qu'elle éclaire."""

    cross_document_overlap: float = 0.40
    """Seuil relevé quand les deux affirmations viennent de documents différents.

    Deux documents peuvent employer le même vocabulaire sans parler de la même
    chose — « rendement d'un moteur thermique » et « conversion d'un moteur
    électrique » partagent des mots sans que l'un chiffre l'autre. Le graphe
    est délibérément conservateur : une arête manquante se rattrape, une fausse
    chaîne causale se retrouve dans la vidéo et se raconte au spectateur."""

    max_out_degree: int = 3
    """Une cause qui explique tout n'explique rien."""


def build_edges(
    nodes: list[GraphNode],
    rules: EdgeRules | None = None,
) -> list[CausalEdge]:
    """Retourne les arêtes causales, dans un ordre déterministe et sans cycle."""
    rules = rules or EdgeRules()
    ordered = sorted(nodes, key=lambda node: (node.document_index, node.sentence_index))
    successors: dict[str, set[str]] = {node.claim_id: set() for node in nodes}
    edges: list[CausalEdge] = []

    def accept(source: str, target: str, relation: CausalRelation, why: str) -> None:
        if source == target:
            return
        if target in successors[source]:
            return
        if len(successors[source]) >= rules.max_out_degree:
            return
        if _reaches(successors, target, source):
            return  # l'arête fermerait une boucle causale
        successors[source].add(target)
        edges.append(
            CausalEdge(
                from_claim_id=source,
                to_claim_id=target,
                relation=relation,
                explanation=why,
            )
        )

    # 1. Enchaînement dans un document : mécanisme → conséquence.
    for index, node in enumerate(ordered):
        if node.kind is not ClaimKind.CONSEQUENCE:
            continue
        for previous in reversed(ordered[:index]):
            if previous.document_index != node.document_index:
                break
            if previous.kind is not ClaimKind.MECHANISM:
                continue
            gap = node.sentence_index - previous.sentence_index
            adjacent = 0 < gap <= rules.sequence_adjacency
            shared = jaccard(previous.text, node.text)
            if adjacent or shared >= rules.sequence_similarity:
                why = (
                    f"conséquence énoncée {gap} phrase(s) après ce mécanisme"
                    if adjacent
                    else f"conséquence partageant le vocabulaire du mécanisme ({shared:.2f})"
                )
                accept(previous.claim_id, node.claim_id, CausalRelation.CAUSES, why)
                break

    # 2. Une grandeur chiffre le mécanisme qu'elle décrit.
    mechanisms = [n for n in ordered if n.kind is ClaimKind.MECHANISM]
    for node in ordered:
        if node.kind is not ClaimKind.QUANTITY:
            continue
        best = _closest(node, mechanisms, rules, rules.quantifies_overlap)
        if best is not None:
            score, target = best
            accept(
                node.claim_id,
                target.claim_id,
                CausalRelation.QUANTIFIES,
                f"grandeur recouvrant le vocabulaire de ce mécanisme ({score:.2f})",
            )

    # 3. Une définition rend intelligible ce qui emploie son terme.
    definitions = [n for n in ordered if n.kind is ClaimKind.DEFINITION]
    for definition in definitions:
        defined = _subject_terms(definition.text)
        if not defined:
            continue
        for node in ordered:
            if node.kind is ClaimKind.DEFINITION:
                continue
            shared = defined & set(tokens(normalise(node.text)))
            if not shared:
                continue
            score = overlap(definition.text, node.text)
            if score >= _threshold(rules, rules.enables_overlap, definition, node):
                accept(
                    definition.claim_id,
                    node.claim_id,
                    CausalRelation.ENABLES,
                    f"définit le terme employé ici : {', '.join(sorted(shared))}",
                )

    return edges


def _threshold(
    rules: EdgeRules,
    base: float,
    left: GraphNode,
    right: GraphNode,
) -> float:
    """Seuil applicable, relevé entre deux documents distincts."""
    if left.document_index == right.document_index:
        return base
    return max(base, rules.cross_document_overlap)


def _closest(
    node: GraphNode,
    others: list[GraphNode],
    rules: EdgeRules,
    base: float,
) -> tuple[float, GraphNode] | None:
    scored = [
        (overlap(node.text, other.text), other)
        for other in others
        if other.claim_id != node.claim_id
    ]
    scored = [
        (score, other)
        for score, other in scored
        if score >= _threshold(rules, base, node, other)
    ]
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], item[1].document_index, item[1].sentence_index))
    return scored[0]


def _subject_terms(text: str) -> set[str]:
    """Termes situés avant la formule définitoire : le sujet défini."""
    flat = normalise(text)
    for cue in (" est un ", " est une ", " designe ", " is a ", " is an "):
        if cue in flat:
            return {term for term in tokens(flat.split(cue)[0]) if len(term) > 3}
    return set()


def _reaches(successors: dict[str, set[str]], start: str, target: str) -> bool:
    seen: set[str] = set()
    stack = [start]
    while stack:
        current = stack.pop()
        if current == target:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(successors.get(current, ()))
    return False
