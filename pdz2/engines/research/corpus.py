"""Fournisseur de documents à partir d'un corpus local.

C'est le seul chemin de recherche qui fonctionne sans réseau ni identifiants.
Il n'est pas un bouche-trou : un corpus tenu à la main (documentation
constructeur, normes, articles archivés) est souvent une meilleure base
factuelle qu'une recherche web, et il est reproductible.

Format d'un document : un fichier `.md` ou `.txt` précédé d'un en-tête YAML
minimal, lu sans dépendance externe.

    ---
    title: Machine synchrone à aimants permanents
    kind: documentation
    url: https://example.org/msap
    publisher: Institut d'électrotechnique
    authority: 0.82
    ---
    Le stator crée un champ magnétique tournant...
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from pdz2.contracts.research import SourceKind
from pdz2.engines.research.ports import (
    ProviderCapability,
    SearchQuery,
    SearchUnavailable,
    SourceDocument,
)

__all__ = ["LocalCorpusProvider", "parse_document", "CorpusFormatError"]

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)
_SCALAR = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")
_SUFFIXES = (".md", ".txt")


class CorpusFormatError(ValueError):
    """Un document du corpus est mal formé. On refuse plutôt que de deviner."""


def parse_document(path: Path) -> SourceDocument:
    """Lit un document du corpus. Un en-tête absent ou invalide est une erreur."""
    raw = path.read_text(encoding="utf-8")
    match = _FRONT_MATTER.match(raw)
    if match is None:
        raise CorpusFormatError(
            f"{path.name} : en-tête `---` manquant — un document sans source "
            "déclarée ne peut pas étayer une affirmation"
        )
    header, body = match.group(1), match.group(2).strip()
    if not body:
        raise CorpusFormatError(f"{path.name} : document vide")

    fields: dict[str, str] = {}
    for number, line in enumerate(header.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        scalar = _SCALAR.match(line.strip())
        if scalar is None:
            raise CorpusFormatError(f"{path.name} ligne {number} : en-tête illisible")
        fields[scalar.group(1)] = scalar.group(2).strip().strip('"').strip("'")

    missing = [name for name in ("title", "authority") if name not in fields]
    if missing:
        raise CorpusFormatError(
            f"{path.name} : en-tête incomplet, manque {', '.join(missing)}"
        )
    try:
        authority = float(fields["authority"])
    except ValueError as error:
        raise CorpusFormatError(f"{path.name} : autorité non numérique") from error
    if not 0.0 <= authority <= 1.0:
        raise CorpusFormatError(f"{path.name} : autorité hors de [0, 1]")

    kind_text = fields.get("kind", "unknown")
    try:
        kind = SourceKind(kind_text)
    except ValueError as error:
        allowed = ", ".join(item.value for item in SourceKind)
        raise CorpusFormatError(
            f"{path.name} : type de source inconnu {kind_text!r} (attendu : {allowed})"
        ) from error

    return SourceDocument(
        title=fields["title"],
        text=body,
        kind=kind,
        url=fields.get("url") or None,
        publisher=fields.get("publisher") or None,
        authority=authority,
        retrieved_at=datetime.now(UTC),
        locator_prefix=path.name,
    )


class LocalCorpusProvider:
    """Documents lus dans un dossier. Sans réseau, sans identifiants."""

    name = "local_corpus"

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    # ------------------------------------------------------------- capacités

    def get_capabilities(self) -> ProviderCapability:
        documents = self._paths()
        if not self.root.is_dir():
            return ProviderCapability.measured(
                self.name,
                reachable=False,
                method=f"stat({self.root})",
                detail=f"dossier de corpus introuvable : {self.root}",
                requires_network=False,
            )
        if not documents:
            return ProviderCapability.measured(
                self.name,
                reachable=False,
                method=f"glob({self.root}/*.md, *.txt)",
                detail=f"corpus vide : aucun document dans {self.root}",
                requires_network=False,
            )
        return ProviderCapability.measured(
            self.name,
            reachable=True,
            method=f"glob({self.root}/*.md, *.txt)",
            detail=f"{len(documents)} documents lisibles",
            requires_network=False,
            max_results=len(documents),
        )

    # -------------------------------------------------------------- recherche

    def search(self, query: SearchQuery) -> list[SourceDocument]:
        capability = self.get_capabilities()
        if not capability.usable:
            raise SearchUnavailable(f"{self.name} : {capability.detail}")

        terms = _terms(query.text)
        scored: list[tuple[float, str, SourceDocument]] = []
        for path in self._paths():
            document = parse_document(path)
            score = _relevance(terms, f"{document.title}\n{document.text}")
            if score > 0.0:
                scored.append((score, path.name, document))
        # Tri stable et déterministe : pertinence, puis nom de fichier.
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [document for _, _, document in scored[: query.max_results]]

    def _paths(self) -> list[Path]:
        if not self.root.is_dir():
            return []
        return sorted(
            path
            for path in self.root.rglob("*")
            if path.is_file() and path.suffix.lower() in _SUFFIXES
        )


def _terms(text: str) -> set[str]:
    from pdz2.engines.research.text import normalise, tokens

    return {token for token in tokens(normalise(text)) if len(token) > 2}


def _relevance(terms: set[str], text: str) -> float:
    from pdz2.engines.research.text import normalise, tokens

    if not terms:
        return 0.0
    found = set(tokens(normalise(text)))
    return len(terms & found) / len(terms)
