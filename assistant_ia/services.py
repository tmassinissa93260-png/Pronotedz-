import logging

from django.conf import settings

from grades.services import moyenne_matiere
from homework.models import CahierDeTexte
from timetable.models import EmploiDuTempsEntry

from .models import BudgetIA, MessageConversation

logger = logging.getLogger(__name__)

MESSAGE_NON_CONFIGURE = (
    "L'assistant IA n'est pas encore configuré pour cet établissement "
    "(clé API manquante). Contactez l'administration."
)
MESSAGE_BUDGET_EPUISE = (
    "Le budget mensuel de questions à l'assistant IA de votre établissement est épuisé. "
    "Il sera renouvelé le mois prochain."
)


def _client():
    if not getattr(settings, "ANTHROPIC_API_KEY", ""):
        return None
    import anthropic

    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def _matieres_de_l_eleve(eleve):
    return sorted({
        entry.matiere.nom
        for entry in EmploiDuTempsEntry.objects.filter(classe=eleve.classe).select_related("matiere")
    })


def _dernieres_notes(eleve):
    lignes = []
    for nom_matiere in _matieres_de_l_eleve(eleve):
        from academics.models import Matiere

        matiere = Matiere.objects.filter(nom=nom_matiere).first()
        if not matiere:
            continue
        trimestre = eleve.classe.annee_scolaire.trimestres.filter(est_actif=True).first()
        if not trimestre:
            continue
        moyenne = moyenne_matiere(eleve, matiere, trimestre)
        if moyenne is not None:
            lignes.append(f"{matiere.nom} : {moyenne}/20")
    return lignes


def construire_contexte(eleve):
    matieres = _matieres_de_l_eleve(eleve)
    notes = _dernieres_notes(eleve)
    lignes = [
        "Tu es l'assistant pédagogique de Pronotedz, aligné sur le programme scolaire algérien.",
        f"Tu aides {eleve.user.first_name}, élève en classe de {eleve.classe.niveau.libelle} ({eleve.classe}).",
        f"Matières suivies : {', '.join(matieres) if matieres else 'non renseignées'}.",
    ]
    if notes:
        lignes.append("Moyennes actuelles : " + "; ".join(notes) + ".")
    lignes.append(
        "Explique les notions clairement et simplement, adapte ton niveau de langage à un élève "
        "du secondaire algérien, et encourage-le. Ne donne jamais directement les réponses d'un devoir noté "
        "en cours — aide-le à comprendre la méthode."
    )
    return "\n".join(lignes)


def envoyer_message(conversation, texte_utilisateur):
    eleve = conversation.eleve
    MessageConversation.objects.create(
        conversation=conversation, role=MessageConversation.Role.UTILISATEUR, contenu=texte_utilisateur,
    )

    etablissement = eleve.user.etablissement
    budget, _ = BudgetIA.objects.get_or_create(etablissement=etablissement)

    client = _client()
    if client is None:
        return MessageConversation.objects.create(
            conversation=conversation, role=MessageConversation.Role.ASSISTANT, contenu=MESSAGE_NON_CONFIGURE,
        )
    if not budget.peut_consommer():
        return MessageConversation.objects.create(
            conversation=conversation, role=MessageConversation.Role.ASSISTANT, contenu=MESSAGE_BUDGET_EPUISE,
        )

    historique = [
        {"role": "user" if m.role == MessageConversation.Role.UTILISATEUR else "assistant", "content": m.contenu}
        for m in conversation.messages.order_by("date_creation")
    ]

    try:
        reponse = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=1024,
            system=construire_contexte(eleve),
            messages=historique,
        )
    except Exception:
        logger.exception("Échec de l'appel à l'API IA pour la conversation %s", conversation.pk)
        return MessageConversation.objects.create(
            conversation=conversation, role=MessageConversation.Role.ASSISTANT,
            contenu="Une erreur est survenue lors de la communication avec l'assistant IA. Réessayez plus tard.",
        )

    texte_reponse = "".join(bloc.text for bloc in reponse.content if bloc.type == "text")
    tokens = reponse.usage.input_tokens + reponse.usage.output_tokens
    budget.consommer(tokens)

    return MessageConversation.objects.create(
        conversation=conversation, role=MessageConversation.Role.ASSISTANT, contenu=texte_reponse, tokens_utilises=tokens,
    )


def generer_fiche_revision(conversation, matiere_nom):
    eleve = conversation.eleve
    entrees = (
        CahierDeTexte.objects.filter(
            seance__emploi_du_temps_entry__classe=eleve.classe,
            seance__emploi_du_temps_entry__matiere__nom=matiere_nom,
            visible_eleves=True,
        )
        .select_related("seance")
        .order_by("-seance__date")[:8]
    )
    if not entrees:
        contenu_cours = "(Aucun contenu de cahier de texte disponible pour cette matière.)"
    else:
        contenu_cours = "\n".join(f"- {e.seance.date:%d/%m/%Y} : {e.contenu}" for e in entrees)

    demande = (
        f"Génère une fiche de révision claire et structurée (titres, points clés, à retenir) "
        f"pour la matière {matiere_nom}, à partir du contenu de mes derniers cours ci-dessous :\n\n{contenu_cours}"
    )
    return envoyer_message(conversation, demande)
