"""Outils de texte déterministes, sans dépendance externe.

Tout ce qui suit est volontairement simple et explicable : chaque décision du
moteur de recherche doit pouvoir être rejouée et justifiée. Aucune de ces
fonctions ne prétend comprendre une phrase — elles la mesurent.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = [
    "normalise",
    "tokens",
    "sentences",
    "jaccard",
    "overlap",
    "is_negated",
    "contains_quantity",
    "STOP_WORDS",
]

STOP_WORDS = frozenset(
    """
    le la les un une des du de d des au aux et ou mais donc or ni car que qui
    quoi dont ou a à en y il elle ils elles on nous vous je tu se sa son ses
    leur leurs ce cet cette ces cela ça est sont etre être ete été avoir a ont
    avait pour par sur sous dans avec sans plus moins tres très peu tout tous
    toute toutes meme même aussi alors ainsi entre chez vers lors
    comment pourquoi quand combien quel quelle quels quelles
    ne pas jamais aucun aucune rien
    the a an of to in on for and or but is are was were be been it its this
    that these those with without from as at by how why when what which
    """.split()
)

# Élisions françaises : « l'énergie » et « énergie » sont le même mot, et
# « n'atteint » est « atteint ». Sans ce découpage, une phrase niée cesse de
# ressembler à son homologue affirmative — et la contradiction passe inaperçue.
_ELISIONS = frozenset("l d n j m t s c qu qu'".split())

_WORD = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ0-9«\"])")
_ABBREVIATIONS = ("cf.", "p.", "ex.", "etc.", "fig.", "env.", "art.", "no.")
# Un `\b` final ne convient pas : « 95 % » finit sur un caractère non-mot.
# Les unités alphabétiques sont bornées par un antécédent négatif à la place.
_QUANTITY = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*"
    r"(?:%|°|"
    r"(?:km/h|m/s|km|mm|cm|kg|kwh|wh|kw|hz|nm|min|ans?|fois|[mgwvash])(?![a-z]))",
    re.IGNORECASE,
)


def normalise(text: str) -> str:
    """Minuscules, accents retirés, espaces normalisés."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", stripped).strip()


def tokens(text: str) -> list[str]:
    """Mots significatifs : élisions défaites, mots outils écartés."""
    kept: list[str] = []
    for word in _WORD.findall(text):
        head, sep, tail = word.partition("'")
        if sep and head in _ELISIONS and tail:
            word = tail
        if word not in STOP_WORDS:
            kept.append(word)
    return kept


def sentences(text: str) -> list[str]:
    """Découpe en phrases. Les abréviations courantes ne coupent pas."""
    guarded = text
    for index, abbreviation in enumerate(_ABBREVIATIONS):
        guarded = guarded.replace(abbreviation, f"\x00{index}\x00")
    parts = _SENTENCE_SPLIT.split(guarded)
    restored: list[str] = []
    for part in parts:
        for index, abbreviation in enumerate(_ABBREVIATIONS):
            part = part.replace(f"\x00{index}\x00", abbreviation)
        cleaned = " ".join(part.split())
        if cleaned:
            restored.append(cleaned)
    return restored


# Négation détectée sur des mots entiers. Une recherche par sous-chaîne
# attraperait « ne » dans « chaîne », et une phrase affirmative passerait pour
# niée — ce qui transforme silencieusement une contradiction en corroboration.
_NEGATION = re.compile(
    r"(?:^|[^a-z0-9])(?:n'|ne|pas|jamais|aucune?|rien|sans|non|not|never|no)"
    r"(?:[^a-z0-9]|$)"
)


def is_negated(text: str) -> bool:
    """Vrai si la phrase porte une marque de négation, mot entier."""
    return _NEGATION.search(normalise(text)) is not None


def jaccard(left: str, right: str) -> float:
    """Similarité lexicale entre deux textes, dans [0, 1]."""
    first = set(tokens(normalise(left)))
    second = set(tokens(normalise(right)))
    if not first or not second:
        return 0.0
    return len(first & second) / len(first | second)


def overlap(left: str, right: str) -> float:
    """Recouvrement : part du plus court des deux textes couverte par l'autre.

    Jaccard répond à « ces deux phrases disent-elles la même chose ? ».
    Ici la question est autre : « cette phrase courte parle-t-elle du sujet de
    cette phrase longue ? ». Jaccard y répond mal — il divise par l'union, donc
    une grandeur en huit mots ne peut structurellement pas ressembler au
    mécanisme en trente mots qu'elle chiffre. Le recouvrement divise par le
    plus court, et mesure ce qu'on cherche vraiment.
    """
    first = set(tokens(normalise(left)))
    second = set(tokens(normalise(right)))
    if not first or not second:
        return 0.0
    return len(first & second) / min(len(first), len(second))


def contains_quantity(text: str) -> bool:
    """Vrai si la phrase porte une grandeur chiffrée avec son unité."""
    return _QUANTITY.search(text) is not None
