from academics.models import Trimestre
from attendance.models import Absence

from .services import moyenne_matiere

GABARIT_SYSTEME = """Tu rédiges des appréciations de bulletin scolaire pour un enseignant algérien.
Rédige UNE appréciation courte (2 à 3 phrases), en français, professionnelle et bienveillante,
adaptée au niveau de l'élève, à partir des éléments fournis. Ne mentionne pas de note chiffrée
si elle n'est pas fournie. Ne mets aucun guillemet ni titre, uniquement le texte de l'appréciation.
"""


def _trimestre_precedent(trimestre):
    if trimestre.numero <= 1:
        return None
    return Trimestre.objects.filter(annee_scolaire=trimestre.annee_scolaire, numero=trimestre.numero - 1).first()


def construire_contexte_eleve(eleve, matiere, trimestre):
    moyenne_actuelle = moyenne_matiere(eleve, matiere, trimestre)
    trimestre_precedent = _trimestre_precedent(trimestre)
    moyenne_precedente = moyenne_matiere(eleve, matiere, trimestre_precedent) if trimestre_precedent else None
    nb_absences = Absence.objects.filter(
        eleve=eleve, seance__date__gte=trimestre.date_debut, seance__date__lte=trimestre.date_fin,
    ).count()

    lignes = [f"Élève : {eleve.user.get_full_name()}, classe {eleve.classe}."]
    if moyenne_actuelle is not None:
        lignes.append(f"Moyenne en {matiere.nom} ce trimestre : {moyenne_actuelle}/20.")
    else:
        lignes.append(f"Aucune note saisie en {matiere.nom} ce trimestre.")
    if moyenne_precedente is not None:
        if moyenne_actuelle is not None and moyenne_actuelle > moyenne_precedente:
            lignes.append(f"Progression par rapport au trimestre précédent ({moyenne_precedente}/20).")
        elif moyenne_actuelle is not None and moyenne_actuelle < moyenne_precedente:
            lignes.append(f"Baisse par rapport au trimestre précédent ({moyenne_precedente}/20).")
        else:
            lignes.append(f"Résultat stable par rapport au trimestre précédent ({moyenne_precedente}/20).")
    lignes.append(f"Absences sur la période : {nb_absences}.")
    return "\n".join(lignes)


def generer_appreciation(etablissement, eleve, matiere, trimestre):
    """Returns (texte, erreur). Nothing is persisted here — the caller decides
    whether/how to save the generated text."""
    from assistant_ia.services import _client
    from assistant_ia.models import BudgetIA

    client = _client()
    if client is None:
        return "", "L'assistant IA n'est pas configuré pour cet établissement (clé API manquante)."

    budget, _ = BudgetIA.objects.get_or_create(etablissement=etablissement)
    if not budget.peut_consommer():
        return "", "Le budget mensuel de l'assistant IA de votre établissement est épuisé."

    try:
        from django.conf import settings

        reponse = client.messages.create(
            model=settings.ANTHROPIC_MODEL, max_tokens=300,
            system=GABARIT_SYSTEME, messages=[{"role": "user", "content": construire_contexte_eleve(eleve, matiere, trimestre)}],
        )
    except Exception:
        return "", "Une erreur est survenue lors de la génération de l'appréciation. Réessayez plus tard."

    texte = "".join(bloc.text for bloc in reponse.content if bloc.type == "text").strip()
    tokens = reponse.usage.input_tokens + reponse.usage.output_tokens
    budget.consommer(tokens)
    return texte, None
