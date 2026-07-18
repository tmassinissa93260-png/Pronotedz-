import datetime

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Utilisateur
from accounts.permissions import role_required

from .models import ProgrammeChapitre, ProgressionChapitre
from .services import (
    annales_pour,
    chapitres_avec_statut,
    date_examen_pour,
    est_classe_examen,
    generer_planning,
    progression_par_matiere,
)


@role_required(Utilisateur.Role.ELEVE)
def revisions_accueil(request):
    eleve = request.user.eleve
    if not est_classe_examen(eleve):
        raise PermissionDenied("Cet espace est réservé aux classes d'examen (4AM/BEM et 3AS/BAC).")

    if request.method == "POST":
        chapitre = get_object_or_404(ProgrammeChapitre, pk=request.POST.get("chapitre_id"), niveau=eleve.classe.niveau)
        nouveau_statut = request.POST.get("statut")
        if nouveau_statut in ProgressionChapitre.Statut.values:
            ProgressionChapitre.objects.update_or_create(eleve=eleve, chapitre=chapitre, defaults={"statut": nouveau_statut})
        return redirect("revisions:revisions_accueil")

    lignes = chapitres_avec_statut(eleve)
    date_examen = date_examen_pour(eleve)
    jours_restants = (date_examen.date_examen - datetime.date.today()).days if date_examen else None

    return render(
        request, "revisions/revisions_accueil.html",
        {
            "eleve": eleve,
            "progression_par_matiere": progression_par_matiere(lignes).items(),
            "lignes": lignes,
            "date_examen": date_examen,
            "jours_restants": jours_restants,
            "planning": list(enumerate(generer_planning(eleve), start=1)),
            "annales": annales_pour(eleve),
            "statuts": ProgressionChapitre.Statut.choices,
        },
    )
