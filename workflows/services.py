import datetime

from django.db.models import Count
from django.utils import timezone

from accounts.models import Eleve
from attendance.models import Retard
from grades.models import Note
from homework.models import Devoir, RenduDevoir
from notifications.models import Notification
from notifications.services import notifier

from .models import WorkflowExecution, WorkflowRegle


def _destinataires(regle, eleve):
    if regle.destinataire == WorkflowRegle.Destinataire.PARENT:
        return [parent.user for parent in eleve.parents.all()]
    if regle.destinataire == WorkflowRegle.Destinataire.PROF_PRINCIPAL:
        prof = eleve.classe.professeur_principal
        return [prof.user] if prof else []
    return []


def _declencher(regle, eleve, cle_unicite, **contexte):
    """Fires the rule for this élève exactly once per cle_unicite — a second
    run of the périodic command won't re-notify for the same event."""
    _, cree = WorkflowExecution.objects.get_or_create(regle=regle, eleve=eleve, cle_unicite=cle_unicite)
    if not cree:
        return False

    message = regle.message.format(regle=regle.nom, eleve=eleve.user.get_full_name(), seuil=regle.seuil, **contexte)
    for destinataire in _destinataires(regle, eleve):
        notifier(destinataire, Notification.Type.AUTRE, titre=regle.nom, contenu=message)
    return True


def evaluer_notes_basses(regle):
    notes = Note.objects.filter(
        valeur__isnull=False, valeur__lt=regle.seuil, evaluation__publie=True,
        eleve__user__etablissement=regle.etablissement,
    ).select_related("eleve__user", "evaluation__matiere")

    return sum(
        _declencher(regle, note.eleve, f"note-{note.pk}", matiere=note.evaluation.matiere.nom, valeur=note.valeur)
        for note in notes
    )


def evaluer_retards_frequents(regle, fenetre_jours=30):
    depuis = timezone.now().date() - datetime.timedelta(days=fenetre_jours)
    semaine = timezone.now().date().isocalendar()[1]

    eleves_ids = (
        Retard.objects.filter(date__gte=depuis, eleve__user__etablissement=regle.etablissement)
        .values("eleve")
        .annotate(nb=Count("id"))
        .filter(nb__gte=regle.seuil)
        .values_list("eleve", flat=True)
    )

    return sum(
        _declencher(regle, eleve, f"retards-semaine-{semaine}", nb_retards=int(regle.seuil))
        for eleve in Eleve.objects.filter(pk__in=eleves_ids).select_related("user")
    )


def evaluer_devoirs_non_rendus(regle):
    limite = timezone.now().date() - datetime.timedelta(days=int(regle.seuil))
    devoirs = Devoir.objects.filter(
        date_a_faire_pour__lte=limite, classe__annee_scolaire__etablissement=regle.etablissement,
    ).select_related("classe", "matiere")

    nb = 0
    for devoir in devoirs:
        rendus_ids = set(RenduDevoir.objects.filter(devoir=devoir).values_list("eleve_id", flat=True))
        for eleve in devoir.classe.eleves.exclude(pk__in=rendus_ids).select_related("user"):
            nb += _declencher(regle, eleve, f"devoir-{devoir.pk}", devoir=devoir.matiere.nom)
    return nb


EVALUATEURS = {
    WorkflowRegle.Declencheur.NOTE_BASSE: evaluer_notes_basses,
    WorkflowRegle.Declencheur.RETARDS_FREQUENTS: evaluer_retards_frequents,
    WorkflowRegle.Declencheur.DEVOIR_NON_RENDU: evaluer_devoirs_non_rendus,
}


def executer_toutes_les_regles():
    total = 0
    for regle in WorkflowRegle.objects.filter(actif=True):
        evaluateur = EVALUATEURS.get(regle.declencheur)
        if evaluateur:
            total += evaluateur(regle)
    return total
