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
