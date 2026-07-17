import datetime

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Utilisateur
from accounts.permissions import role_required
from attendance.models import Seance
from timetable.models import CreneauHoraire, EmploiDuTempsEntry

from .models import CahierDeTexte, Devoir


@role_required(Utilisateur.Role.ENSEIGNANT)
def cahier_liste_enseignant(request):
    date_str = request.GET.get("date")
    date = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
    jour_semaine = CreneauHoraire.PYTHON_WEEKDAY_TO_JOUR.get(date.weekday())

    entries = (
        EmploiDuTempsEntry.objects.filter(enseignant=request.user.enseignant, creneau__jour_semaine=jour_semaine)
        .select_related("classe", "matiere", "creneau")
        .order_by("creneau__ordre")
        if jour_semaine is not None
        else EmploiDuTempsEntry.objects.none()
    )
    return render(request, "homework/cahier_liste_enseignant.html", {"entries": entries, "date": date})


@role_required(Utilisateur.Role.ENSEIGNANT)
def cahier_seance(request, entry_id):
    date_str = request.GET.get("date") or request.POST.get("date")
    date = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
    entry = get_object_or_404(EmploiDuTempsEntry, pk=entry_id, enseignant=request.user.enseignant)
    seance = Seance.get_or_create_for(entry, date)
    cahier = CahierDeTexte.objects.filter(seance=seance).first()
    devoirs = Devoir.objects.filter(seance_donnee=seance)

    if request.method == "POST":
        contenu = request.POST.get("contenu", "").strip()
        CahierDeTexte.objects.update_or_create(
            seance=seance, defaults={"contenu": contenu, "saisi_par": request.user}
        )
        consigne = request.POST.get("consigne", "").strip()
        date_a_faire_pour = request.POST.get("date_a_faire_pour")
        if consigne and date_a_faire_pour:
            Devoir.objects.create(
                seance_donnee=seance,
                classe=entry.classe,
                matiere=entry.matiere,
                enseignant=request.user.enseignant,
                date_a_faire_pour=date_a_faire_pour,
                consigne=consigne,
            )
        messages.success(request, "Cahier de texte enregistré.")
        return redirect(f"{request.path}?date={date.isoformat()}")

    return render(
        request,
        "homework/cahier_seance.html",
        {"entry": entry, "seance": seance, "cahier": cahier, "devoirs": devoirs, "date": date},
    )


@role_required(Utilisateur.Role.ELEVE, Utilisateur.Role.PARENT)
def cahier_classe(request):
    user = request.user
    eleve = None
    enfants = None

    if user.role == user.Role.ELEVE:
        eleve = user.eleve
    else:
        enfants = user.parent.enfants.select_related("user").all()
        enfant_id = request.GET.get("enfant")
        eleve = get_object_or_404(enfants, pk=enfant_id) if enfant_id else enfants.first()

    classe = eleve.classe if eleve else None
    cahiers = (
        CahierDeTexte.objects.filter(seance__emploi_du_temps_entry__classe=classe, visible_eleves=True)
        .select_related("seance__emploi_du_temps_entry__matiere")
        .order_by("-seance__date")
        if classe
        else CahierDeTexte.objects.none()
    )
    devoirs = Devoir.objects.filter(classe=classe).select_related("matiere") if classe else Devoir.objects.none()

    return render(
        request,
        "homework/cahier_liste.html",
        {"cahiers": cahiers, "devoirs": devoirs, "eleve": eleve, "enfants": enfants},
    )
