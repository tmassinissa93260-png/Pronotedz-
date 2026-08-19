"""Régénère les références du corpus golden.

    python -m tests.golden_regenerer

**Relis toujours le diff avant de committer.** Une référence régénérée sans
être relue ne prouve plus rien : elle enregistre le comportement actuel,
correct ou non. C'est le seul risque réel des golden tests, et il ne se
prévient qu'à la lecture.

Volontairement un script séparé, et non une option `--update` du test : une
mise à jour doit être un geste délibéré, jamais un effet de bord d'un
lancement de suite.
"""

from __future__ import annotations

import json

from tests.test_golden import (
    MOTEUR,
    TRAHISON,
    _compiler,
    _director_explicatif,
    _reference,
)

# (nom, producteur) — chaque entrée sait se recalculer seule.
CORPUS = [
    (TRAHISON["nom"], lambda: _compiler(TRAHISON)),
    (MOTEUR["nom"], _director_explicatif),
]


def main() -> None:
    for nom, produire in CORPUS:
        chemin = _reference(nom)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        contenu = json.loads(produire().en_json())
        chemin.write_text(
            json.dumps(contenu, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"✓ {chemin.name} — {contenu.get('contrat', '?')}")


if __name__ == "__main__":
    main()
