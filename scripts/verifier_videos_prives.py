#!/usr/bin/env python3
"""Garde-fou : bloque toute vidéo suivie par git dans un dossier privé.

Aucune vidéo de référence ne doit jamais atteindre l'historique git de ce
dépôt — c'est presque toujours le contenu d'un tiers (voir TELEPHONE.md,
étape 5). `.gitignore` protège `git add` en local, mais ni un `git add -f`
distrait, ni l'upload web de GitHub (qui ignore `.gitignore` — c'est un
mécanisme entièrement différent). Ce script est la sécurité
SUPPLÉMENTAIRE, pas un remplacement de cette vigilance.

Deux usages, une seule logique de détection :

  · hook pre-commit (.githooks/pre-commit) — vérifie les fichiers STAGÉS,
    avant que le commit n'existe.
  · vérification CI (.github/workflows/verifier-videos.yml) — vérifie tout
    ce que git suit déjà après un push, quelle qu'en soit l'origine :
    c'est la seule des deux qui voit un upload fait via GitHub Web.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

EXTENSIONS_VIDEO = {".mp4", ".mov", ".webm", ".mkv", ".avi"}

# Les dossiers où une vidéo privée circule pendant les tests. Une vidéo
# ailleurs dans ce dépôt serait de toute façon suspecte — aucune vidéo
# n'y est jamais commise intentionnellement — mais c'est ici que le
# risque est concret et attendu.
DOSSIERS_SENSIBLES = ("donnees/",)


def chemins_interdits(chemins: list[str]) -> list[str]:
    """Parmi les chemins donnés, ceux qui sont une vidéo dans un dossier sensible."""
    interdits = []
    for brut in chemins:
        chemin = brut.strip()
        if not chemin:
            continue
        if Path(chemin).suffix.lower() in EXTENSIONS_VIDEO and any(
            chemin.startswith(d) for d in DOSSIERS_SENSIBLES
        ):
            interdits.append(chemin)
    return interdits


def _fichiers_staged() -> list[str]:
    sortie = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True, text=True, check=True,
    )
    return sortie.stdout.splitlines()


def _fichiers_suivis() -> list[str]:
    sortie = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True,
    )
    return sortie.stdout.splitlines()


def main(argv: list[str]) -> int:
    tout = "--tous" in argv
    chemins = _fichiers_suivis() if tout else _fichiers_staged()
    trouves = chemins_interdits(chemins)
    if not trouves:
        return 0

    print("✗ Vidéo(s) détectée(s) dans un dossier privé — bloqué.", file=sys.stderr)
    for c in trouves:
        print(f"  · {c}", file=sys.stderr)
    print(
        "\nAucune vidéo de référence ne doit atteindre l'historique de ce "
        "dépôt (voir TELEPHONE.md, étape 5). Si c'est une vraie vidéo de "
        "test : retire-la du suivi (`git restore --staged <fichier>`, ou "
        "`git rm --cached <fichier>` si déjà commise) et garde-la "
        "uniquement en local.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
