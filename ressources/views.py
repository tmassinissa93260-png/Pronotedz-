import datetime

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Utilisateur
from accounts.permissions import role_required
from timetable.models import CreneauHoraire

from .models import Reservation, Ressource


@role_required(Utilisateur.Role.ENSEIGNANT)
def nouvelle_reservation(request):
    date_str = request.GET.get("date") or request.POST.get("date")
    date = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
    jour_semaine = CreneauHoraire.PYTHON_WEEKDAY_TO_JOUR.get(date.weekday())
    creneaux = CreneauHoraire.objects.filter(jour_semaine=jour_semaine).order_by("ordre") if jour_semaine is not None else CreneauHoraire.objects.none()

    if request.method == "POST":
        creneau = get_object_or_404(creneaux, pk=request.POST.get("creneau"))
        ressource = get_object_or_404(Ressource, pk=request.POST.get("ressource"))
        if Reservation.objects.filter(ressource=ressource, date=date, creneau=creneau).exists():
            messages.error(request, "Cette ressource est déjà réservée sur ce créneau.")
        else:
            Reservation.objects.create(
                ressource=ressource, enseignant=request.user.enseignant, date=date, creneau=creneau,
                motif=request.POST.get("motif", "").strip(),
            )
            messages.success(request, "Réservation confirmée.")
        return redirect(f"{request.path}?date={date.isoformat()}")

    ressources = Ressource.objects.all()
    reservations_du_jour = Reservation.objects.filter(date=date).select_related("ressource", "creneau", "enseignant__user")
    return render(
        request,
        "ressources/nouvelle_reservation.html",
        {"date": date, "creneaux": creneaux, "ressources": ressources, "reservations_du_jour": reservations_du_jour},
    )


@role_required(Utilisateur.Role.ENSEIGNANT)
def mes_reservations(request):
    reservations = Reservation.objects.filter(
        enseignant=request.user.enseignant, date__gte=datetime.date.today()
    ).select_related("ressource", "creneau")
    return render(request, "ressources/mes_reservations.html", {"reservations": reservations})


@role_required(Utilisateur.Role.ENSEIGNANT)
def annuler_reservation(request, reservation_id):
    reservation = get_object_or_404(Reservation, pk=reservation_id, enseignant=request.user.enseignant)
    reservation.delete()
    messages.success(request, "Réservation annulée.")
    return redirect("ressources:mes_reservations")
