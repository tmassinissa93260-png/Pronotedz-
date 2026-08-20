"""L'état du monde, plan après plan — et ce que le rendu en a vraiment montré.

Volontairement LÉGER, et il doit le rester. Ce n'est pas un simulateur
physique : la seule question à laquelle ce paquet répond est « qu'est-ce qui a
changé entre le plan précédent et celui-ci, et le rendu l'a-t-il montré ? ».

    ÉTAT A  →  ÉVÉNEMENT  →  ÉTAT B
                   ↓
                 RENDU
                   ↓
              ÉTAT OBSERVÉ
                   ↓
                 DELTA

Le dépôt en portait déjà deux morceaux, séparés et sans nom commun :
`continuite.porter_le_decor()` fait suivre le décor d'une réplique à l'autre,
et `geometrie.py` place les objets en qualitatif. Les deux se retrouvent ici
sous une forme qui permet, en plus, de CONFRONTER l'attendu à l'observé.

── Ce que le paquet refuse de faire ─────────────────────────────────────

Inventer un état observé. Tant qu'aucune sonde ne sait mesurer la position
d'un objet dans une image, `observe` reste `None` — et `None` veut dire
« pas encore regardé », jamais « conforme ».
"""

from pdz.world.etat import (
    appliquer,
    delta,
    depuis_plans,
    etat_initial,
    observer,
)

__all__ = ["etat_initial", "depuis_plans", "appliquer", "observer", "delta"]
