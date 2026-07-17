from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render

from academics.models import AnneeScolaire, Classe

from .models import EmploiDuTempsEntry
from .services import build_grid


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
