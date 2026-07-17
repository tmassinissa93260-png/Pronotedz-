import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import AnneeScolaire, Classe
from accounts.models import Eleve, Enseignant, Utilisateur
from accounts.permissions import role_required
from attendance.models import Absence
from homework.models import Devoir
from timetable.models import CreneauHoraire, EmploiDuTempsEntry


@login_required
def dispatch(request):
    url_name = {
        Utilisateur.Role.ADMIN: "dashboard:admin_home",
        Utilisateur.Role.ENSEIGNANT: "dashboard:enseignant_home",
        Utilisateur.Role.ELEVE: "dashboard:eleve_home",
        Utilisateur.Role.PARENT: "dashboard:parent_home",
    }[request.user.role]
    return redirect(url_name)


def _entries_du_jour(base_qs, date):
    jour_semaine = CreneauHoraire.PYTHON_WEEKDAY_TO_JOUR.get(date.weekday())
    if jour_semaine is None:
        return base_qs.none()
    return base_qs.filter(creneau__jour_semaine=jour_semaine).select_related(
        "classe", "matiere", "creneau", "salle"
    ).order_by("creneau__ordre")


@role_required(Utilisateur.Role.ADMIN)
def admin_home(request):
    annee = AnneeScolaire.objects.filter(est_active=True).first()
    context = {
        "annee": annee,
        "nb_classes": Classe.objects.filter(annee_scolaire=annee).count() if annee else 0,
        "nb_eleves": Eleve.objects.filter(classe__annee_scolaire=annee).count() if annee else 0,
        "nb_enseignants": Enseignant.objects.count(),
    }
    return render(request, "dashboard/admin_home.html", context)


@role_required(Utilisateur.Role.ENSEIGNANT)
def enseignant_home(request):
    today = datetime.date.today()
    entries = _entries_du_jour(
        EmploiDuTempsEntry.objects.filter(enseignant=request.user.enseignant), today
    )
    return render(request, "dashboard/enseignant_home.html", {"entries": entries, "today": today})


@role_required(Utilisateur.Role.ELEVE)
def eleve_home(request):
    today = datetime.date.today()
    eleve = request.user.eleve
    entries = _entries_du_jour(EmploiDuTempsEntry.objects.filter(classe=eleve.classe), today)
    absences_recentes = Absence.objects.filter(eleve=eleve).select_related("seance")[:5]
    devoirs_a_venir = Devoir.objects.filter(classe=eleve.classe, date_a_faire_pour__gte=today)[:5]
    return render(
        request,
        "dashboard/eleve_home.html",
        {"entries": entries, "today": today, "absences_recentes": absences_recentes, "devoirs_a_venir": devoirs_a_venir, "eleve": eleve},
    )


@role_required(Utilisateur.Role.PARENT)
def parent_home(request):
    today = datetime.date.today()
    enfants = request.user.parent.enfants.select_related("user", "classe").all()
    enfant_id = request.GET.get("enfant")
    enfant = get_object_or_404(enfants, pk=enfant_id) if enfant_id else enfants.first()

    entries = _entries_du_jour(EmploiDuTempsEntry.objects.filter(classe=enfant.classe), today) if enfant else []
    absences_recentes = Absence.objects.filter(eleve=enfant).select_related("seance")[:5] if enfant else []
    devoirs_a_venir = Devoir.objects.filter(classe=enfant.classe, date_a_faire_pour__gte=today)[:5] if enfant else []
    return render(
        request,
        "dashboard/parent_home.html",
        {
            "entries": entries,
            "today": today,
            "absences_recentes": absences_recentes,
            "devoirs_a_venir": devoirs_a_venir,
            "enfants": enfants,
            "enfant": enfant,
        },
    )
