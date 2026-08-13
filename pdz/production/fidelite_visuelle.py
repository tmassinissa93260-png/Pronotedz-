"""Garantit que le prompt d'image montre ce que la réplique nomme vraiment.

Laissé libre, un modèle qui écrit un prompt d'image a tendance à illustrer
« l'esprit » d'une réplique plutôt que les objets concrets qu'elle nomme :
la voix dit « le signal plonge dans le câble sous-marin », l'image montre un
hologramme générique sans câble ni océan. `ShotPromptWriter` désigne donc
ces objets explicitement dans `elements_obligatoires` ; ce module vérifie
après coup qu'ils sont bien dans le prompt final, et les rajoute sinon —
jamais un appel Groq de plus, une simple concaténation de texte.
"""

from __future__ import annotations


def renforcer(prompt: str, elements: list[str]) -> tuple[str, list[str]]:
    """Ajoute au prompt les éléments obligatoires qui n'y sont pas déjà.

    Comparaison insensible à la casse sur une sous-chaîne simple : pas besoin
    de plus, `elements_obligatoires` est écrit par le même modèle et dans le
    même appel que `prompt_image`, donc dans un vocabulaire déjà cohérent.
    """
    bas = prompt.lower()
    manquants = [e for e in elements if e.strip() and e.strip().lower() not in bas]
    if not manquants:
        return prompt, []
    return f"{prompt}, featuring {', '.join(manquants)}", manquants
