from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Utilisateur
from accounts.permissions import role_required

from .models import AlerteDecrochage
from .services import recommandations_pour


def _alertes_visibles(user):
    if user.role == Utilisateur.Role.ADMIN:
        return AlerteDecrochage.objects.filter(eleve__user__etablissement=user.etablissement)
    if user.role == Utilisateur.Role.ENSEIGNANT:
        return AlerteDecrochage.objects.filter(eleve__classe__professeur_principal=user.enseignant)
    return AlerteDecrochage.objects.none()


@role_required(Utilisateur.Role.ADMIN, Utilisateur.Role.ENSEIGNANT)
def alerte_liste(request):
    alertes = _alertes_visibles(request.user).select_related("eleve__user", "eleve__classe")
    statut = request.GET.get("statut")
    if statut:
        alertes = alertes.filter(statut=statut)
    return render(
        request, "decrochage/alerte_liste.html",
        {"alertes": alertes, "statuts": AlerteDecrochage.Statut.choices, "statut_filtre": statut},
    )


@role_required(Utilisateur.Role.ADMIN, Utilisateur.Role.ENSEIGNANT)
def alerte_detail(request, alerte_id):
    alerte = get_object_or_404(_alertes_visibles(request.user), pk=alerte_id)

    if request.method == "POST":
        nouveau_statut = request.POST.get("statut")
        if nouveau_statut in AlerteDecrochage.Statut.values:
            alerte.statut = nouveau_statut
            alerte.notes_suivi = request.POST.get("notes_suivi", "").strip()
            alerte.traite_par = request.user
            alerte.save()
            messages.success(request, "Alerte mise à jour.")
            return redirect("decrochage:alerte_detail", alerte_id=alerte.pk)

    return render(
        request, "decrochage/alerte_detail.html",
        {
            "alerte": alerte, "recommandations": recommandations_pour(alerte.signaux),
            "statuts": AlerteDecrochage.Statut.choices,
        },
    )
