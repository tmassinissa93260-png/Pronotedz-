"""Extraction d'affirmations à partir de documents sourcés.

Ce module ne comprend pas le français : il le **mesure**. Une phrase devient
une affirmation candidate en fonction de signaux comptables — présence des
termes du sujet, indices causaux, grandeur chiffrée, longueur exploitable.
Chaque affirmation retenue garde la trace du signal qui l'a fait retenir, ce
qui rend la décision rejouable et discutable.

Ce n'est délibérément pas un modèle de langue. Un extracteur lexical ne sait
pas reformuler, il sait citer — et une citation exacte adossée à sa source est
précisément ce dont le Fact Graph a besoin. La reformulation, la thèse et la
preuve visuelle relèvent d'une décision conceptuelle : elles arrivent par le
Director Core, jamais d'ici.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from pdz2.contracts.research import ClaimKind
from pdz2.engines.research.text import (
    contains_quantity,
    is_negated,
    jaccard,
    normalise,
    sentences,
    tokens,
)

__all__ = [
    "ClaimSignal",
    "SentenceCandidate",
    "ExtractionSettings",
    "extract_candidates",
    "group_duplicates",
    "CAUSAL_CUES",
]


class ClaimSignal(str, Enum):
    """Pourquoi une phrase a été retenue. Un signal, une justification."""

    TOPIC_TERM = "topic_term"
    CAUSAL_CUE = "causal_cue"
    QUANTITY = "quantity"
    DEFINITION_CUE = "definition_cue"
    COMPARISON_CUE = "comparison_cue"


# Indices causaux : ils signalent un mécanisme, pas une opinion.
CAUSAL_CUES: dict[str, ClaimKind] = {
    "parce que": ClaimKind.MECHANISM,
    "car": ClaimKind.MECHANISM,
    "donc": ClaimKind.CONSEQUENCE,
    "ainsi": ClaimKind.CONSEQUENCE,
    "par consequent": ClaimKind.CONSEQUENCE,
    "ce qui provoque": ClaimKind.MECHANISM,
    "provoque": ClaimKind.MECHANISM,
    "entraine": ClaimKind.MECHANISM,
    "produit": ClaimKind.MECHANISM,
    "genere": ClaimKind.MECHANISM,
    "transforme": ClaimKind.MECHANISM,
    "convertit": ClaimKind.MECHANISM,
    "permet": ClaimKind.MECHANISM,
    "grace a": ClaimKind.MECHANISM,
    "sous l effet": ClaimKind.MECHANISM,
    "resulte": ClaimKind.CONSEQUENCE,
    "because": ClaimKind.MECHANISM,
    "therefore": ClaimKind.CONSEQUENCE,
    "causes": ClaimKind.MECHANISM,
    "converts": ClaimKind.MECHANISM,
    "produces": ClaimKind.MECHANISM,
}

DEFINITION_CUES = (
    "est un",
    "est une",
    "designe",
    "s appelle",
    "se compose",
    "est constitue",
    "is a",
    "is an",
    "consists of",
)

COMPARISON_CUES = (
    "plus que",
    "moins que",
    "contrairement",
    "alors que",
    "tandis que",
    "par rapport",
    "compared",
    "unlike",
)

_MIN_WORDS = 6
_MAX_WORDS = 45
_INTERROGATIVE = re.compile(r"\?\s*$")


@dataclass(frozen=True)
class SentenceCandidate:
    """Une phrase retenue, avec ce qui l'a fait retenir."""

    text: str
    document_index: int
    sentence_index: int
    kind: ClaimKind
    signals: tuple[ClaimSignal, ...]
    salience: float
    """Score de saillance dans [0, 1]. Sert au tri, pas à la confiance."""

    matched_terms: frozenset[str] = field(default_factory=frozenset)

    @property
    def negated(self) -> bool:
        """Polarité de la phrase. Sépare une corroboration d'une contradiction."""
        return is_negated(self.text)


@dataclass(frozen=True)
class ExtractionSettings:
    """Seuils de l'extracteur. Explicites, donc discutables et réglables."""

    min_salience: float = 0.25
    max_per_document: int = 6
    duplicate_threshold: float = 0.50
    """Au-dessus, deux phrases énoncent la même affirmation.

    Mesuré sur de la prose technique réelle : les reformulations d'une même
    affirmation par deux sources tombent entre 0,60 et 0,75, les phrases
    distinctes sous 0,25. Le seuil est posé au milieu du fossé. Les élisions
    étant défaites en amont, une phrase niée reste proche de son homologue
    affirmative — elle rejoint donc le même groupe et y devient une preuve
    contraire, au lieu de passer pour une affirmation indépendante."""


def extract_candidates(
    *,
    topic: str,
    documents: list[tuple[int, str]],
    settings: ExtractionSettings | None = None,
) -> list[SentenceCandidate]:
    """Retourne les phrases candidates, triées par saillance décroissante.

    `documents` est une liste de `(index du document, texte)`. L'index sert à
    rattacher chaque candidate à sa source sans la transporter ici.
    """
    settings = settings or ExtractionSettings()
    topic_terms = {term for term in tokens(normalise(topic)) if len(term) > 2}

    candidates: list[SentenceCandidate] = []
    for document_index, text in documents:
        per_document: list[SentenceCandidate] = []
        for sentence_index, sentence in enumerate(sentences(text)):
            candidate = _score(sentence, document_index, sentence_index, topic_terms)
            if candidate is not None and candidate.salience >= settings.min_salience:
                per_document.append(candidate)
        per_document.sort(key=lambda item: (-item.salience, item.sentence_index))
        candidates.extend(per_document[: settings.max_per_document])

    candidates.sort(
        key=lambda item: (-item.salience, item.document_index, item.sentence_index)
    )
    return candidates


def _score(
    sentence: str,
    document_index: int,
    sentence_index: int,
    topic_terms: set[str],
) -> SentenceCandidate | None:
    words = sentence.split()
    if not _MIN_WORDS <= len(words) <= _MAX_WORDS:
        return None
    if _INTERROGATIVE.search(sentence):
        return None

    flat = normalise(sentence)
    padded = f" {flat} "
    found_terms = frozenset(term for term in topic_terms if term in flat)
    signals: list[ClaimSignal] = []
    kind = ClaimKind.FACT
    score = 0.0

    if found_terms:
        signals.append(ClaimSignal.TOPIC_TERM)
        score += 0.35 * min(1.0, len(found_terms) / max(1, min(3, len(topic_terms))))

    for cue, cue_kind in CAUSAL_CUES.items():
        if f" {cue} " in padded or padded.startswith(f" {cue} "):
            signals.append(ClaimSignal.CAUSAL_CUE)
            kind = cue_kind
            score += 0.35
            break

    if contains_quantity(sentence):
        signals.append(ClaimSignal.QUANTITY)
        if kind is ClaimKind.FACT:
            kind = ClaimKind.QUANTITY
        score += 0.25

    if any(cue in padded for cue in DEFINITION_CUES):
        signals.append(ClaimSignal.DEFINITION_CUE)
        if kind is ClaimKind.FACT:
            kind = ClaimKind.DEFINITION
        score += 0.15

    if any(cue in padded for cue in COMPARISON_CUES):
        signals.append(ClaimSignal.COMPARISON_CUE)
        if kind is ClaimKind.FACT:
            kind = ClaimKind.COMPARISON
        score += 0.10

    if not signals:
        return None

    return SentenceCandidate(
        text=sentence,
        document_index=document_index,
        sentence_index=sentence_index,
        kind=kind,
        signals=tuple(dict.fromkeys(signals)),
        salience=min(1.0, round(score, 4)),
        matched_terms=found_terms,
    )


def group_duplicates(
    candidates: list[SentenceCandidate],
    threshold: float,
) -> list[list[SentenceCandidate]]:
    """Regroupe les candidates qui disent la même chose.

    Deux phrases proches issues de **documents différents** forment une
    corroboration ; issues du même document, une redondance.
    """
    groups: list[list[SentenceCandidate]] = []
    for candidate in candidates:
        for group in groups:
            if jaccard(candidate.text, group[0].text) >= threshold:
                group.append(candidate)
                break
        else:
            groups.append([candidate])
    return groups
