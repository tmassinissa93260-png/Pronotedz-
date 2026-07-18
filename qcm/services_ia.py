from assistant_ia.models import BudgetIA

GABARIT_SYSTEME = """Tu es un générateur de QCM pour un enseignant algérien, aligné sur le programme scolaire national.
Génère EXACTEMENT {nb_questions} questions à choix multiples à partir du contenu de cours fourni par l'enseignant.

Format de sortie STRICT (respecte-le à la lettre, sans aucun texte avant ou après) :
- Chaque question est un bloc de lignes, séparé du bloc suivant par une ligne vide.
- La première ligne du bloc est l'énoncé de la question.
- Les lignes suivantes sont les choix de réponse (3 à 5 par question).
- Le choix correct commence par une astérisque "*", les autres choix n'en ont pas.
- Une seule réponse correcte par question.

Exemple pour 2 questions :
Quelle est la capitale de l'Algérie ?
Oran
*Alger
Constantine

2 + 2 = ?
3
*4
5
6
"""


def generer_qcm_brut(etablissement, contenu_cours, nb_questions=10):
    """Returns (texte_genere, erreur). texte_genere is in the exact bulk-text
    format parse_questions() expects, ready to review/edit before saving —
    nothing is written to the database here. erreur is a user-facing message
    when the API isn't configured, the budget is exhausted, or the call fails."""
    from assistant_ia.services import _client

    client = _client()
    if client is None:
        return "", "L'assistant IA n'est pas configuré pour cet établissement (clé API manquante)."

    budget, _ = BudgetIA.objects.get_or_create(etablissement=etablissement)
    if not budget.peut_consommer():
        return "", "Le budget mensuel de l'assistant IA de votre établissement est épuisé."

    try:
        from django.conf import settings

        reponse = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=2048,
            system=GABARIT_SYSTEME.format(nb_questions=nb_questions),
            messages=[{"role": "user", "content": contenu_cours}],
        )
    except Exception:
        return "", "Une erreur est survenue lors de la génération du QCM. Réessayez plus tard."

    texte = "".join(bloc.text for bloc in reponse.content if bloc.type == "text")
    tokens = reponse.usage.input_tokens + reponse.usage.output_tokens
    budget.consommer(tokens)
    return texte.strip(), None
