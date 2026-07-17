import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import AnneeScolaire, Classe
from accounts.models import Eleve, Enseignant, Utilisateur
from accounts.permissions import role_required
from actualites.models import Publication
from attendance.models import Absence
from documents.models import Document
from grades.models import Note
from homework.models import Devoir
from timetable.models import EmploiDuTempsEntry
from timetable.services import build_day


@login_required
def dispatch(request):
    url_name = {
        Utilisateur.Role.ADMIN: "dashboard:admin_home",
        Utilisateur.Role.ENSEIGNANT: "dashboard:enseignant_home",
        Utilisateur.Role.ELEVE: "dashboard:eleve_home",
        Utilisateur.Role.PARENT: "dashboard:parent_home",
    }[request.user.role]
    return redirect(url_name)


def _jour_context(request, entries_qs, extra_qs=""):
    jour_str = request.GET.get("jour")
    jour = datetime.date.fromisoformat(jour_str) if jour_str else datetime.date.today()
    return {
        "jour_widget": build_day(entries_qs, jour),
        "jour_prev": (jour - datetime.timedelta(days=1)).isoformat(),
        "jour_next": (jour + datetime.timedelta(days=1)).isoformat(),
        "jour_extra_qs": extra_qs,
    }


@role_required(Utilisateur.Role.ADMIN)
def admin_home(request):
    annee = AnneeScolaire.objects.filter(est_active=True).first()
    context = {
        "annee": annee,
        "nb_classes": Classe.objects.filter(annee_scolaire=annee).count() if annee else 0,
        "nb_eleves": Eleve.objects.filter(classe__annee_scolaire=annee).count() if annee else 0,
        "nb_enseignants": Enseignant.objects.count(),
        "publications": Publication.visibles_pour(request.user.role)[:3],
    }
    return render(request, "dashboard/admin_home.html", context)


@role_required(Utilisateur.Role.ENSEIGNANT)
def enseignant_home(request):
    context = _jour_context(request, EmploiDuTempsEntry.objects.filter(enseignant=request.user.enseignant))
    context["publications"] = Publication.visibles_pour(request.user.role)[:3]
    return render(request, "dashboard/enseignant_home.html", context)


@role_required(Utilisateur.Role.ELEVE)
def eleve_home(request):
    eleve = request.user.eleve
    context = _jour_context(request, EmploiDuTempsEntry.objects.filter(classe=eleve.classe))
    context.update(
        {
            "eleve": eleve,
            "absences_recentes": Absence.objects.filter(eleve=eleve).select_related("seance__emploi_du_temps_entry__matiere")[:4],
            "devoirs_a_venir": Devoir.objects.filter(classe=eleve.classe, date_a_faire_pour__gte=datetime.date.today()).select_related("matiere")[:4],
            "notes_recentes": Note.objects.filter(eleve=eleve, valeur__isnull=False).select_related("evaluation__matiere").order_by("-evaluation__date_evaluation")[:4],
            "documents_recents": Document.objects.filter(classe__isnull=True) | Document.objects.filter(classe=eleve.classe),
            "publications": Publication.visibles_pour(request.user.role)[:3],
        }
    )
    context["documents_recents"] = context["documents_recents"].order_by("-date_depot")[:3]
    return render(request, "dashboard/eleve_home.html", context)


@role_required(Utilisateur.Role.PARENT)
def parent_home(request):
    enfants = request.user.parent.enfants.select_related("user", "classe").all()
    enfant_id = request.GET.get("enfant")
    enfant = get_object_or_404(enfants, pk=enfant_id) if enfant_id else enfants.first()
    extra_qs = f"&enfant={enfant.pk}" if enfant else ""

    entries_qs = EmploiDuTempsEntry.objects.filter(classe=enfant.classe) if enfant else EmploiDuTempsEntry.objects.none()
    context = _jour_context(request, entries_qs, extra_qs=extra_qs)
    context.update(
        {
            "enfants": enfants,
            "enfant": enfant,
            "absences_recentes": Absence.objects.filter(eleve=enfant).select_related("seance__emploi_du_temps_entry__matiere")[:4] if enfant else [],
            "devoirs_a_venir": Devoir.objects.filter(classe=enfant.classe, date_a_faire_pour__gte=datetime.date.today()).select_related("matiere")[:4] if enfant else [],
            "notes_recentes": Note.objects.filter(eleve=enfant, valeur__isnull=False).select_related("evaluation__matiere").order_by("-evaluation__date_evaluation")[:4] if enfant else [],
            "publications": Publication.visibles_pour(request.user.role)[:3],
        }
    )
    return render(request, "dashboard/parent_home.html", context)
