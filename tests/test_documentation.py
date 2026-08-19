"""Les liens de la documentation pointent vers quelque chose qui existe.

Six liens étaient morts au moment où ce test a été écrit — des documents
renumérotés (`06-plan.md` → `10-plan.md`), archivés (`03-n8n.md` →
`archive/saas-v2/`) ou jamais écrits (`04-ce-quil-faut-changer.md`). Aucun
n'était détectable autrement qu'en cliquant : rien ne les vérifiait.

Ne teste QUE les liens relatifs vers des fichiers du dépôt. Les URL externes
ne sont pas vérifiées — cela demanderait le réseau en CI, rendrait le test
non déterministe, et un lien externe cassé n'est pas une régression de ce
dépôt.
"""

from __future__ import annotations

import pathlib
import re

import pytest

RACINE = pathlib.Path(__file__).resolve().parent.parent

# `[texte](./cible)` ou `[texte](../cible)` — uniquement le relatif explicite,
# qui est la convention suivie partout dans ce dépôt.
LIEN_RELATIF = re.compile(r"\[[^\]]*\]\((\.\.?/[^)\s]+)\)")


def _documents() -> list[pathlib.Path]:
    """Tous les documents VIVANTS du dépôt.

    `docs/archive/` en est exclu volontairement : le README le présente comme
    des « versions écartées, à ignorer ». Ce sont des documents gelés, témoins
    d'un état passé du projet ; leurs liens internes renvoient à une
    arborescence qui n'existe plus. Les réparer réécrirait un historique pour
    zéro valeur, et les garder sous surveillance ferait échouer le CI sur du
    texte que personne ne lit plus.
    """
    docs = list(RACINE.glob("*.md"))
    docs += [p for p in (RACINE / "docs").rglob("*.md")
             if "archive" not in p.relative_to(RACINE).parts]
    return sorted(docs)


@pytest.mark.parametrize("document", _documents(), ids=lambda p: p.name)
def test_les_liens_relatifs_pointent_vers_un_fichier_existant(document):
    morts = []
    for lien in LIEN_RELATIF.findall(document.read_text(encoding="utf-8")):
        # L'ancre (#section) ne fait pas partie du chemin sur le disque.
        cible = (document.parent / lien.split("#", 1)[0]).resolve()
        if not cible.exists():
            morts.append(lien)

    assert not morts, (
        f"{document.relative_to(RACINE)} pointe vers des fichiers absents :\n  "
        + "\n  ".join(morts)
    )
