"""Porte l'état du décor d'une réplique à l'autre, sans jamais appeler de modèle.

Le scénariste choisit un décor par réplique, ou n'en choisit aucun. Rien ne
garantissait jusqu'ici qu'une réplique sans décor précisé reste dans la
scène en cours : `images.prompt_plan()` retombait sur le premier décor de
l'univers pour TOUTE réplique vide, quelle que soit la scène — un plan 8
sans décor après 7 plans à la villa pouvait recevoir un décor générique sans
rapport avec la scène qui se joue, ou une réplique sans décor après une
réplique « cérémonie » pouvait silencieusement revenir à un décor par
défaut au lieu de rester à la cérémonie.

Ce module ne décide rien de créatif — deux règles mécaniques :

  1. Un plan sans décor explicite HÉRITE du dernier décor explicite qui le
     précède (voir `porter_le_decor`). Écrire un changement de décor reste
     une décision du scénariste ; ne rien écrire n'en est plus une par
     accident.
  2. Un changement de décor EST un changement de scène — la seule frontière
     que le script donne déjà, sans qu'aucun champ supplémentaire soit
     nécessaire (voir `indices_de_scene`).

Ne s'applique qu'aux univers à personnages récurrents (`univers.anime`) :
en narration, `decor` reste délibérément épars — la plupart des sujets
n'ont aucun des quelques décors génériques de l'univers qui leur
corresponde, et `action` doit alors se suffire à elle-même (voir
`Univers.contexte_script`). Hériter un décor n'y aurait aucun sens.
"""

from __future__ import annotations


def porter_le_decor(repliques: list[dict]) -> list[dict]:
    """Renvoie une COPIE des répliques, `decor` complété par héritage.

    Une réplique qui précise un décor le garde tel quel — c'est une
    décision explicite. Une réplique sans décor hérite du dernier décor
    explicite rencontré ; s'il n'y en a aucun avant elle (début de
    l'épisode), elle reste vide — rien à hériter.
    """
    portees: list[dict] = []
    dernier = ""
    for r in repliques:
        r = dict(r)
        if r.get("decor"):
            dernier = r["decor"]
        else:
            r["decor"] = dernier
        portees.append(r)
    return portees


def indices_de_scene(decors: list[str]) -> list[int]:
    """Le numéro de scène (0, 1, 2...) associé à chaque décor de la liste,
    dans l'ordre.

    Appelé sur des décors déjà « portés » par `porter_le_decor`, un décor
    identique au précédent reste dans la même scène ; un décor différent —
    y compris de vide à précisé — en ouvre une nouvelle.
    """
    indices: list[int] = []
    courant = -1
    precedent: str | None = None
    for decor in decors:
        if courant == -1 or decor != precedent:
            courant += 1
        indices.append(courant)
        precedent = decor
    return indices
