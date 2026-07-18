from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render

from accounts.models import Eleve, Enseignant
from actualites.models import Publication
from finance.models import Facture, Paiement

from .models import Classe, Etablissement, Niveau


@login_required
def groupe_tableau_bord(request):
    groupe = request.user.groupe_gere
    if groupe is None:
        raise PermissionDenied("Vous ne gérez aucun groupe scolaire.")

    campus = []
    for etablissement in groupe.etablissements.all():
        total_attendu = Facture.objects.filter(
            eleve__user__etablissement=etablissement
        ).aggregate(total=Sum("montant"))["total"] or 0
        total_encaisse = Paiement.objects.filter(
            facture__eleve__user__etablissement=etablissement
        ).aggregate(total=Sum("montant"))["total"] or 0
        campus.append(
            {
                "etablissement": etablissement,
                "nb_classes": Classe.objects.filter(annee_scolaire__etablissement=etablissement).count(),
                "nb_eleves": Eleve.objects.filter(user__etablissement=etablissement).count(),
                "nb_enseignants": Enseignant.objects.filter(user__etablissement=etablissement).count(),
                "total_attendu": total_attendu,
                "total_encaisse": total_encaisse,
            }
        )

    totaux = {
        "nb_classes": sum(c["nb_classes"] for c in campus),
        "nb_eleves": sum(c["nb_eleves"] for c in campus),
        "nb_enseignants": sum(c["nb_enseignants"] for c in campus),
        "total_attendu": sum(c["total_attendu"] for c in campus),
        "total_encaisse": sum(c["total_encaisse"] for c in campus),
    }

    return render(request, "academics/groupe_tableau_bord.html", {"groupe": groupe, "campus": campus, "totaux": totaux})


def portail_public(request, slug):
    etablissement = get_object_or_404(Etablissement, slug=slug)
    publications = Publication.objects.filter(
        etablissement=etablissement, audience=Publication.Audience.PUBLIC
    ).order_by("-epingle", "-date_publication")[:10]
    niveaux = Niveau.objects.filter(
        classes__annee_scolaire__etablissement=etablissement
    ).distinct().order_by("ordre")

    return render(
        request, "academics/portail_public.html",
        {"etablissement": etablissement, "publications": publications, "niveaux": niveaux},
    )
