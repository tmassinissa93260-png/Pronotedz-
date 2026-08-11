"""Détecte quand plusieurs empreintes créatives se ressemblent trop.

La diversité n'est pas un objectif : si dix vidéos partagent réellement le
même mécanisme, ce n'est pas une erreur de le constater. C'est un signal de
diagnostic — « regarde de plus près », pas une note à corriger de force. Voir
`EmpreinteCreative` dans `pdz.univers.modele` pour ce qui est comparé.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from pdz.univers import EmpreinteCreative

# Sous ce nombre d'empreintes, une répétition n'a aucune valeur statistique —
# deux vidéos qui partagent un hook, ce n'est pas un signal, c'est un hasard.
MINIMUM_POUR_DIAGNOSTIC = 3

# Part des empreintes qui doit partager la même valeur pour déclencher
# l'alerte. 0,7 : nettement plus qu'une coïncidence, sans exiger l'unanimité.
SEUIL_REPETITION = 0.7

# Les champs comparés, et le libellé humain de chacun.
_CHAMPS: dict[str, callable] = {
    "hook.type": lambda e: e.hook.type.valeur,
    "narrative.structure": lambda e: e.narrative.structure.valeur,
    "narrative.fin": lambda e: e.narrative.fin.valeur,
    "psychologie.arc_emotionnel": lambda e: e.psychologie.arc_emotionnel.valeur,
    "psychologie.retention": lambda e: e.psychologie.retention.valeur,
    "visuel.style": lambda e: e.visuel.style.valeur,
}


@dataclass
class AlerteDiversite:
    champ: str
    valeur_dominante: str
    occurrences: int
    total: int

    def __str__(self) -> str:
        part = self.occurrences / self.total
        return (
            f"POTENTIAL_ANALYSIS_COLLAPSE — {self.champ} : "
            f"« {self.valeur_dominante} » sur {self.occurrences}/{self.total} "
            f"empreintes ({part:.0%})"
        )


def diagnostic_diversite(
    empreintes: list[tuple[str, EmpreinteCreative]],
) -> list[AlerteDiversite]:
    """Compare les empreintes deux à deux, champ par champ.

    `empreintes` est une liste de `(label, empreinte)` — le label sert à
    remonter à l'univers ou la vidéo concernée si l'appelant veut creuser.
    Un champ dont la valeur vaut « unknown » n'entre jamais dans le calcul :
    dix vidéos où le modèle n'a pas su trancher ne prouvent aucune
    répétition, seulement dix incertitudes.
    """
    if len(empreintes) < MINIMUM_POUR_DIAGNOSTIC:
        return []

    alertes: list[AlerteDiversite] = []
    for champ, extraire in _CHAMPS.items():
        valeurs = [extraire(e) for _, e in empreintes]
        valeurs = [v for v in valeurs if v and v != "unknown"]
        if len(valeurs) < MINIMUM_POUR_DIAGNOSTIC:
            continue

        dominante, occurrences = Counter(valeurs).most_common(1)[0]
        if occurrences / len(valeurs) >= SEUIL_REPETITION:
            alertes.append(AlerteDiversite(
                champ=champ, valeur_dominante=dominante,
                occurrences=occurrences, total=len(valeurs),
            ))
    return alertes
