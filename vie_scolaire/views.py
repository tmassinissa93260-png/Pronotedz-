import datetime

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import Classe
from accounts.contacts import classes_enseignees
from accounts.models import Eleve, Utilisateur
from accounts.permissions import role_required

from .models import Observation


def _classes_visibles(user):
    if user.role == Utilisateur.Role.ADMIN:
        return Classe.objects.filter(annee_scolaire__etablissement=user.etablissement)
    return classes_enseignees(user.enseignant)


@role_required(Utilisateur.Role.ENSEIGNANT, Utilisateur.Role.ADMIN)
def observation_liste(request):
    classes = _classes_visibles(request.user)
    observations = Observation.objects.filter(eleve__classe__in=classes).select_related("eleve__user", "matiere")
    return render(request, "vie_scolaire/observation_liste.html", {"observations": observations})


@role_required(Utilisateur.Role.ENSEIGNANT, Utilisateur.Role.ADMIN)
def observation_creer(request):
    classes = _classes_visibles(request.user)
    classe_id = request.GET.get("classe") or request.POST.get("classe")
    classe = get_object_or_404(classes, pk=classe_id) if classe_id else classes.first()
    eleves = classe.eleves.select_related("user").order_by("user__last_name") if classe else Eleve.objects.none()

    if request.method == "POST":
        eleve = get_object_or_404(eleves, pk=request.POST.get("eleve"))
        Observation.objects.create(
            eleve=eleve,
            type_observation=request.POST.get("type_observation"),
            motif=request.POST.get("motif", "").strip(),
            description=request.POST.get("description", "").strip(),
            date=request.POST.get("date") or datetime.date.today(),
            saisie_par=request.user,
        )
        messages.success(request, "Observation enregistrée.")
        return redirect("vie_scolaire:observation_liste")

    return render(
        request,
        "vie_scolaire/observation_creer.html",
        {"classes": classes, "classe": classe, "eleves": eleves, "types": Observation.TypeObservation.choices, "today": datetime.date.today()},
    )


@role_required(Utilisateur.Role.ELEVE, Utilisateur.Role.PARENT)
def mes_observations(request):
    user = request.user
    eleve = None
    enfants = None

    if user.role == user.Role.ELEVE:
        eleve = user.eleve
    else:
        enfants = user.parent.enfants.select_related("user").all()
        enfant_id = request.GET.get("enfant")
        eleve = get_object_or_404(enfants, pk=enfant_id) if enfant_id else enfants.first()

    observations = (
        Observation.objects.filter(eleve=eleve).select_related("matiere") if eleve else Observation.objects.none()
    )
    return render(
        request,
        "vie_scolaire/mes_observations.html",
        {"observations": observations, "eleve": eleve, "enfants": enfants},
    )
