import datetime

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.contacts import enseignants_de_classe
from accounts.models import Utilisateur
from accounts.permissions import role_required

from .models import DisponibiliteRDV, RendezVous


@role_required(Utilisateur.Role.ENSEIGNANT)
def mes_disponibilites(request):
    if request.method == "POST":
        DisponibiliteRDV.objects.get_or_create(
            enseignant=request.user.enseignant,
            date=request.POST.get("date"),
            heure_debut=request.POST.get("heure_debut"),
            defaults={"heure_fin": request.POST.get("heure_fin")},
        )
        messages.success(request, "Créneau ajouté.")
        return redirect("rendezvous:mes_disponibilites")

    disponibilites = (
        DisponibiliteRDV.objects.filter(enseignant=request.user.enseignant, date__gte=datetime.date.today())
        .select_related("rendez_vous__parent__user", "rendez_vous__eleve_concerne__user")
    )
    return render(request, "rendezvous/mes_disponibilites.html", {"disponibilites": disponibilites, "today": datetime.date.today()})


@role_required(Utilisateur.Role.PARENT)
def disponibilites_liste(request):
    enfants = request.user.parent.enfants.select_related("user", "classe").all()
    enfant_id = request.GET.get("enfant")
    enfant = get_object_or_404(enfants, pk=enfant_id) if enfant_id else enfants.first()

    disponibilites = []
    if enfant:
        enseignants = enseignants_de_classe(enfant.classe)
        disponibilites = (
            DisponibiliteRDV.objects.filter(
                enseignant__in=enseignants, date__gte=datetime.date.today(), rendez_vous__isnull=True
            )
            .select_related("enseignant__user")
        )

    return render(
        request,
        "rendezvous/disponibilites_liste.html",
        {"disponibilites": disponibilites, "enfants": enfants, "enfant": enfant},
    )


@role_required(Utilisateur.Role.PARENT)
def reserver(request, disponibilite_id):
    enfants = request.user.parent.enfants.all()
    enfant_id = request.POST.get("enfant")
    enfant = get_object_or_404(enfants, pk=enfant_id)
    enseignants = enseignants_de_classe(enfant.classe)
    disponibilite = get_object_or_404(
        DisponibiliteRDV, pk=disponibilite_id, enseignant__in=enseignants, rendez_vous__isnull=True
    )

    RendezVous.objects.create(
        disponibilite=disponibilite,
        parent=request.user.parent,
        eleve_concerne=enfant,
        motif=request.POST.get("motif", "").strip(),
    )
    messages.success(request, "Rendez-vous confirmé.")
    return redirect("rendezvous:mes_rdv")


@role_required(Utilisateur.Role.PARENT)
def mes_rdv(request):
    rdv = RendezVous.objects.filter(parent=request.user.parent).select_related(
        "disponibilite__enseignant__user", "eleve_concerne__user"
    )
    return render(request, "rendezvous/mes_rdv.html", {"rdv": rdv})


@role_required(Utilisateur.Role.PARENT)
def annuler(request, rdv_id):
    rdv = get_object_or_404(RendezVous, pk=rdv_id, parent=request.user.parent)
    rdv.delete()
    messages.success(request, "Rendez-vous annulé.")
    return redirect("rendezvous:mes_rdv")
