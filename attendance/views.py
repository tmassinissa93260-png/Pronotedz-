import datetime

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Utilisateur
from accounts.permissions import role_required
from timetable.models import CreneauHoraire, EmploiDuTempsEntry

from .models import Absence, Seance


@role_required(Utilisateur.Role.ENSEIGNANT)
def appel_liste(request):
    date_str = request.GET.get("date")
    date = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
    jour_semaine = CreneauHoraire.PYTHON_WEEKDAY_TO_JOUR.get(date.weekday())

    entries = EmploiDuTempsEntry.objects.filter(
        enseignant=request.user.enseignant, creneau__jour_semaine=jour_semaine
    ).select_related("classe", "matiere", "creneau").order_by("creneau__ordre") if jour_semaine is not None else EmploiDuTempsEntry.objects.none()

    return render(request, "attendance/appel_liste.html", {"entries": entries, "date": date})


@role_required(Utilisateur.Role.ENSEIGNANT)
def appel_seance(request, entry_id):
    date_str = request.GET.get("date") or request.POST.get("date")
    date = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
    entry = get_object_or_404(
        EmploiDuTempsEntry, pk=entry_id, enseignant=request.user.enseignant
    )
    seance = Seance.get_or_create_for(entry, date)
    eleves = entry.classe.eleves.select_related("user").order_by("user__last_name")

    if request.method == "POST":
        absents_ids = set(request.POST.getlist("absent"))
        Absence.objects.filter(seance=seance).delete()
        for eleve in eleves:
            if str(eleve.pk) in absents_ids:
                Absence.objects.create(seance=seance, eleve=eleve, saisie_par=request.user)
        messages.success(request, "Appel enregistré.")
        return redirect(f"{request.path}?date={date.isoformat()}")

    absents_actuels = set(Absence.objects.filter(seance=seance).values_list("eleve_id", flat=True))
    return render(
        request,
        "attendance/appel_seance.html",
        {"entry": entry, "seance": seance, "eleves": eleves, "absents_actuels": absents_actuels, "date": date},
    )


@role_required(Utilisateur.Role.ELEVE, Utilisateur.Role.PARENT)
def historique(request):
    user = request.user
    eleve = None
    enfants = None

    if user.role == user.Role.ELEVE:
        eleve = user.eleve
    else:
        enfants = user.parent.enfants.select_related("user").all()
        enfant_id = request.GET.get("enfant")
        eleve = get_object_or_404(enfants, pk=enfant_id) if enfant_id else enfants.first()

    absences = (
        Absence.objects.filter(eleve=eleve).select_related("seance__emploi_du_temps_entry__matiere")
        if eleve
        else Absence.objects.none()
    )
    return render(
        request,
        "attendance/historique.html",
        {"absences": absences, "eleve": eleve, "enfants": enfants},
    )
