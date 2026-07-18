import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from academics.models import AnneeScolaire, Classe
from accounts.models import Utilisateur
from accounts.permissions import role_required
from attendance.models import Seance
from notifications.models import Notification
from notifications.services import notifier_plusieurs

from .models import CreneauHoraire, EmploiDuTempsEntry
from .services import build_grid, suggerer_remplacants


def _annee_active(user):
    return AnneeScolaire.objects.filter(etablissement=user.etablissement, est_active=True).first()


@login_required
def mon_emploi_du_temps(request):
    user = request.user
    annee = _annee_active(user)
    classe = None

    if user.role == user.Role.ELEVE:
        classe = user.eleve.classe
        entries = EmploiDuTempsEntry.objects.filter(classe=classe, annee_scolaire=annee)
    elif user.role == user.Role.PARENT:
        enfants = user.parent.enfants.select_related("classe").all()
        enfant_id = request.GET.get("enfant")
        enfant = get_object_or_404(enfants, pk=enfant_id) if enfant_id else enfants.first()
        classe = enfant.classe if enfant else None
        entries = (
            EmploiDuTempsEntry.objects.filter(classe=classe, annee_scolaire=annee)
            if classe
            else EmploiDuTempsEntry.objects.none()
        )
    elif user.role == user.Role.ENSEIGNANT:
        entries = EmploiDuTempsEntry.objects.filter(enseignant=user.enseignant, annee_scolaire=annee)
    elif user.role == user.Role.ADMIN:
        classe_id = request.GET.get("classe")
        classes = Classe.objects.filter(annee_scolaire=annee) if annee else Classe.objects.none()
        classe = get_object_or_404(classes, pk=classe_id) if classe_id else classes.first()
        entries = (
            EmploiDuTempsEntry.objects.filter(classe=classe, annee_scolaire=annee)
            if classe
            else EmploiDuTempsEntry.objects.none()
        )
    else:
        raise PermissionDenied

    grid = build_grid(entries)
    context = {"grid": grid, "classe": classe}
    if user.role == user.Role.PARENT:
        context["enfants"] = user.parent.enfants.select_related("classe").all()
    if user.role == user.Role.ADMIN:
        context["classes"] = Classe.objects.filter(annee_scolaire=annee) if annee else Classe.objects.none()
    return render(request, "timetable/grid.html", context)


@role_required(Utilisateur.Role.ADMIN)
def remplacements_jour(request):
    date_str = request.GET.get("date")
    date = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
    jour_semaine = CreneauHoraire.PYTHON_WEEKDAY_TO_JOUR.get(date.weekday())

    entries = []
    if jour_semaine is not None:
        entries = list(
            EmploiDuTempsEntry.objects.filter(
                creneau__jour_semaine=jour_semaine, annee_scolaire__etablissement=request.user.etablissement,
            )
            .select_related("classe", "matiere", "enseignant__user", "creneau")
            .order_by("creneau__ordre", "classe__libelle")
        )

    seances_par_entry = {
        entry.pk: Seance.objects.filter(emploi_du_temps_entry=entry, date=date)
        .select_related("enseignant_remplacant__user")
        .first()
        for entry in entries
    }

    return render(
        request, "timetable/remplacements.html",
        {"date": date, "entries": entries, "seances_par_entry": seances_par_entry},
    )


@role_required(Utilisateur.Role.ADMIN)
def remplacement_assigner(request, entry_id, date):
    entry = get_object_or_404(
        EmploiDuTempsEntry, pk=entry_id, annee_scolaire__etablissement=request.user.etablissement,
    )
    date_obj = datetime.date.fromisoformat(date)
    candidats = suggerer_remplacants(entry)

    if request.method == "POST":
        remplacant = get_object_or_404(candidats, pk=request.POST.get("enseignant"))
        seance = Seance.get_or_create_for(entry, date_obj)
        seance.enseignant_remplacant = remplacant
        seance.statut = Seance.Statut.REMPLACEE
        seance.save()
        notifier_plusieurs(
            [eleve.user for eleve in entry.classe.eleves.select_related("user")],
            Notification.Type.REMPLACEMENT,
            titre=f"Remplacement — {entry.matiere}",
            contenu=f"Le cours de {entry.matiere} du {date_obj:%d/%m/%Y} sera assuré par {remplacant}.",
        )
        messages.success(request, f"{remplacant} a été assigné(e) en remplacement.")
        return redirect(f"{reverse('timetable:remplacements_jour')}?date={date_obj.isoformat()}")

    return render(
        request, "timetable/remplacement_assigner.html",
        {"entry": entry, "date": date_obj, "candidats": candidats},
    )


@role_required(Utilisateur.Role.ADMIN)
def remplacement_annuler(request, seance_id):
    seance = get_object_or_404(
        Seance, pk=seance_id, emploi_du_temps_entry__annee_scolaire__etablissement=request.user.etablissement,
    )
    seance.enseignant_remplacant = None
    seance.statut = Seance.Statut.NORMALE
    seance.save()
    messages.success(request, "Remplacement annulé.")
    return redirect(f"{reverse('timetable:remplacements_jour')}?date={seance.date.isoformat()}")
