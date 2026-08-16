"""Où est chaque objet, en qualitatif — jamais une coordonnée.

Le prompt libre de ShotPromptWriter décrit déjà une scène, mais rien ne
garantit qu'il précise la position RELATIVE de chaque objet nommé : sur
l'exemple avion + piste + trajectoire + aéroport, le modèle d'image doit
deviner seul si la piste est devant ou derrière l'avion, si l'aéroport est
au loin ou tout proche. Ce module ne fait qu'une chose : traduire une
`zone`/`profondeur` choisie par ShotPromptWriter en une courte formule
anglaise, prête à rejoindre le prompt — même discipline que
`pdz.production.cadrage` (vocabulaire fixe et court, une table de phrases,
zéro logique).

Volontairement deux petits vocabulaires séparés plutôt qu'un seul grand
enum : un `enum` Groq à beaucoup de valeurs augmente le risque de réponse
hors-liste qui fait rejeter tout le JSON (voir l'historique de `emotion`
dans script@1.4.0) — deux enums courts combinés sont plus sûrs qu'un seul
enum à 15 valeurs pour représenter la même chose.
"""

from __future__ import annotations

ZONES = ["top", "bottom", "left", "right", "center"]
PROFONDEURS = ["background", "midground", "foreground"]

PHRASES_ZONE = {
    "top": "near the top of the frame",
    "bottom": "near the bottom of the frame",
    "left": "on the left side of the frame",
    "right": "on the right side of the frame",
    "center": "centered in the frame",
}

PHRASES_PROFONDEUR = {
    "background": "in the background",
    "midground": "in the midground",
    "foreground": "in the foreground",
}


def phrase(entite: str, zone: str, profondeur: str) -> str:
    """« aircraft near the bottom of the frame, in the foreground ».

    Vide si `entite` est vide, ou si ni `zone` ni `profondeur` ne sont
    reconnues — jamais une valeur par défaut inventée (même principe que
    `cadrage.phrase()`) : une position qu'on ne sait pas dire précisément
    ne doit pas en dire une fausse.
    """
    entite = entite.strip()
    if not entite:
        return ""
    morceaux = [entite]
    if z := PHRASES_ZONE.get(zone):
        morceaux.append(z)
    if p := PHRASES_PROFONDEUR.get(profondeur):
        morceaux.append(p)
    if len(morceaux) < 2:
        return ""
    return ", ".join(morceaux)
