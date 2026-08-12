"""Le vocabulaire de cadrage, et sa vérification déterministe.

Un cadrage vient d'un vocabulaire FIXE et court, écrit par ShotPromptWriter
en plus du prompt texte libre — c'est ce qui permet à Python de vérifier la
variété d'un plan à l'autre sans appeler de modèle. La consigne « jamais
deux plans consécutifs avec le même cadrage » vivait jusqu'ici uniquement en
texte dans le prompt — jamais vérifiée. Ce module la vérifie, en diagnostic
seulement (voir `verifier_diversite`, jamais en relance).
"""

from __future__ import annotations

# Vocabulaire volontairement court (5 valeurs) : un `enum` JSON Schema avec
# beaucoup de valeurs augmente le risque qu'un modèle Llama/Groq en renvoie
# une hors liste et fasse rejeter toute la réponse — voir l'historique de
# script@1.4.0 sur `emotion` pour la même leçon.
CADRAGES = ["gros_plan", "plan_rapproche", "plan_moyen", "plan_large", "plan_detail"]

# La formule de cadrage, telle qu'elle doit apparaître dans le prompt
# d'image final (voir `images.prompt_plan`). ShotPromptWriter choisit déjà
# un cadrage en prose dans `prompt_image`, mais rien ne garantissait qu'un
# mot-clé de cadrage FIABLE atteigne vraiment le modèle d'image — cette
# formule le garantit, en plus de ce que le texte libre décrit.
PHRASES = {
    "gros_plan": "close-up shot",
    "plan_rapproche": "medium close-up shot",
    "plan_moyen": "medium shot",
    "plan_large": "wide shot",
    "plan_detail": "extreme close-up, fine detail shot",
}


def phrase(cadrage_id: str) -> str:
    """La formule anglaise prête pour un prompt d'image — vide si le
    cadrage n'est pas renseigné (job en cache d'avant ce champ, par
    exemple), plutôt que d'inventer une valeur par défaut qui masquerait
    l'absence réelle d'information."""
    return PHRASES.get(cadrage_id, "")


def verifier_diversite(cadrages: list[str]) -> list[str]:
    """Les avertissements pour les paires consécutives qui répètent le même
    cadrage — jamais une erreur qui bloque ou relance.

    Volontairement en diagnostic seulement : forcer une relance à chaque
    répétition ajouterait un appel Groq de plus, exactement ce qu'on cherche
    à réduire cette nuit. Une répétition n'est pas toujours une faute — deux
    gros plans qui se suivent peuvent être le bon choix pour une scène
    précise. Ce qui compte, c'est de le savoir (dans les journaux), pas de
    l'interdire dans le code.
    """
    avertissements = []
    for i, (a, b) in enumerate(zip(cadrages, cadrages[1:])):
        if a and b and a == b:
            avertissements.append(f"plans {i} et {i + 1} : même cadrage ({a}) à la suite")
    return avertissements
