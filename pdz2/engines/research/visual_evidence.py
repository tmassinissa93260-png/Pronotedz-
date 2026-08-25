"""Démontrabilité visuelle : une mesure, pas une décision.

Le cahier des charges demande au moteur de recherche d'« identifier les
affirmations pouvant être démontrées visuellement ». Ce module le fait en
mesurant des signaux observables : un procédé physique, un objet concret, un
changement d'état, une grandeur chiffrée.

Il s'arrête là, volontairement. Écrire *ce que le spectateur doit
physiquement voir* est une décision conceptuelle : elle appartient au Director
Core, qui l'appuie sur un `visual_proof` rédigé. Un score élevé ici n'autorise
personne à cocher `visually_demonstrable` — sans preuve rédigée, le contrat
`Claim` refuse.

    MEASURE  →  demonstrability      (ici)
    DECIDE   →  visually_demonstrable + visual_proof   (Director Core)
"""

from __future__ import annotations

from pdz2.contracts.research import ClaimKind
from pdz2.engines.research.text import contains_quantity, normalise

__all__ = ["demonstrability", "OBSERVABLE_VERBS", "ABSTRACT_MARKERS"]

OBSERVABLE_VERBS = (
    "tourne", "tournent", "circule", "circulent", "traverse", "traversent",
    "chauffe", "refroidit", "se deplace", "se deplacent", "s ouvre", "se ferme",
    "monte", "descend", "augmente", "diminue", "se dilate", "vibre", "glisse",
    "frotte", "comprime", "aspire", "ejecte", "transforme", "convertit",
    "attire", "repousse", "s allume", "s eteint", "fond", "gele", "coule",
    "rotates", "flows", "moves", "heats", "expands", "converts",
)

CONCRETE_MARKERS = (
    "moteur", "rotor", "stator", "aimant", "batterie", "cellule", "circuit",
    "courant", "champ", "roue", "pignon", "axe", "piston", "fluide", "air",
    "eau", "metal", "cable", "capteur", "engrenage", "ressort", "membrane",
)

ABSTRACT_MARKERS = (
    "concept", "notion", "theorie", "politique", "economique", "societal",
    "philosoph", "reglementaire", "juridique", "strategie", "tendance",
    "marche", "opinion", "perception",
)

_KIND_BONUS = {
    ClaimKind.MECHANISM: 0.30,
    ClaimKind.QUANTITY: 0.15,
    ClaimKind.CONSEQUENCE: 0.15,
    ClaimKind.DEFINITION: 0.05,
    ClaimKind.COMPARISON: 0.10,
    ClaimKind.FACT: 0.0,
}


def demonstrability(text: str, kind: ClaimKind) -> float:
    """Score dans [0, 1] : à quel point l'affirmation est *montrable*.

    Ce n'est pas une probabilité, c'est un indice de tri. Il aide le Director
    Core à savoir quelles affirmations méritent qu'on cherche une preuve
    visuelle, et lesquelles resteront de toute façon abstraites.
    """
    flat = normalise(text)
    score = _KIND_BONUS[kind]

    if any(verb in flat for verb in OBSERVABLE_VERBS):
        score += 0.35
    concrete = sum(1 for marker in CONCRETE_MARKERS if marker in flat)
    score += min(0.25, 0.10 * concrete)
    if contains_quantity(text):
        score += 0.15
    abstract = sum(1 for marker in ABSTRACT_MARKERS if marker in flat)
    score -= min(0.45, 0.20 * abstract)

    return round(max(0.0, min(1.0, score)), 4)
