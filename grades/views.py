from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import Matiere, Trimestre
from accounts.models import Utilisateur
from accounts.permissions import role_required
from notifications.models import Notification
from notifications.services import notifier

from .models import AppreciationGenerale, AppreciationMatiere, Evaluation, Note
from .services import moyenne_generale, moyenne_matiere, rang_classe, statistiques_classe_matiere


@role_required(Utilisateur.Role.ENSEIGNANT)
def evaluation_liste(request):
    evaluations = Evaluation.objects.filter(enseignant=request.user.enseignant).select_related("classe", "matiere", "trimestre")
    return render(request, "grades/evaluation_liste.html", {"evaluations": evaluations})


@role_required(Utilisateur.Role.ENSEIGNANT)
def saisie_notes(request, evaluation_id):
    evaluation = get_object_or_404(Evaluation, pk=evaluation_id, enseignant=request.user.enseignant)
    eleves = evaluation.classe.eleves.select_related("user").order_by("user__last_name")

    if request.method == "POST":
        for eleve in eleves:
            valeur = request.POST.get(f"note_{eleve.pk}", "").strip()
            Note.objects.update_or_create(
                evaluation=evaluation,
                eleve=eleve,
                defaults={"valeur": valeur or None},
            )
        messages.success(request, "Notes enregistrées.")
        return redirect("grades:saisie_notes", evaluation_id=evaluation.pk)

    notes_par_eleve = {note.eleve_id: note.valeur for note in evaluation.notes.all()}
    return render(
        request,
        "grades/saisie_notes.html",
        {"evaluation": evaluation, "eleves": eleves, "notes_par_eleve": notes_par_eleve},
    )


@role_required(Utilisateur.Role.ENSEIGNANT)
def publier_evaluation(request, evaluation_id):
    evaluation = get_object_or_404(Evaluation, pk=evaluation_id, enseignant=request.user.enseignant)
    if not evaluation.publie:
        evaluation.publie = True
        evaluation.save()
        for note in evaluation.notes.filter(valeur__isnull=False).select_related("eleve__user"):
            notifier(
                note.eleve.user,
                Notification.Type.NOTE,
                titre=f"Note publiée — {evaluation.matiere}",
                contenu=f"{evaluation.titre} : {note.valeur}/{evaluation.bareme}",
                lien="/notes/bulletin/",
            )
        messages.success(request, "Notes publiées, les élèves ont été notifiés.")
    return redirect("grades:saisie_notes", evaluation_id=evaluation.pk)


def _resoudre_eleve(request):
    user = request.user
    if user.role == user.Role.ELEVE:
        return user.eleve, None
    enfants = user.parent.enfants.select_related("user").all()
    enfant_id = request.GET.get("enfant")
    eleve = get_object_or_404(enfants, pk=enfant_id) if enfant_id else enfants.first()
    return eleve, enfants


def _donnees_bulletin(eleve, trimestre):
    lignes = []
    moyenne_gen = None
    rang, effectif = None, 0

    if eleve and trimestre:
        matieres = Matiere.objects.filter(
            evaluations__classe=eleve.classe, evaluations__trimestre=trimestre
        ).distinct()
        appreciations = {
            a.matiere_id: a.texte
            for a in AppreciationMatiere.objects.filter(eleve=eleve, trimestre=trimestre)
        }
        for matiere in matieres:
            lignes.append(
                {
                    "matiere": matiere,
                    "moyenne": moyenne_matiere(eleve, matiere, trimestre),
                    "coefficient": eleve.classe.coefficient_pour(matiere),
                    "stats_classe": statistiques_classe_matiere(eleve.classe, matiere, trimestre),
                    "appreciation": appreciations.get(matiere.pk, ""),
                }
            )
        moyenne_gen = moyenne_generale(eleve, trimestre)
        rang, effectif = rang_classe(eleve, trimestre)

    appreciation_generale = (
        AppreciationGenerale.objects.filter(eleve=eleve, trimestre=trimestre).first() if eleve and trimestre else None
    )

    return {
        "lignes": lignes,
        "moyenne_generale": moyenne_gen,
        "rang": rang,
        "effectif": effectif,
        "appreciation_generale": appreciation_generale,
    }


@role_required(Utilisateur.Role.ELEVE, Utilisateur.Role.PARENT)
def bulletin(request):
    eleve, enfants = _resoudre_eleve(request)
    trimestre = Trimestre.objects.filter(est_actif=True).first()
    contexte = _donnees_bulletin(eleve, trimestre)
    contexte.update({"eleve": eleve, "enfants": enfants, "trimestre": trimestre})
    return render(request, "grades/bulletin.html", contexte)


@role_required(Utilisateur.Role.ELEVE, Utilisateur.Role.PARENT)
def bulletin_pdf(request):
    from .pdf import generer_bulletin_pdf

    eleve, enfants = _resoudre_eleve(request)
    trimestre = Trimestre.objects.filter(est_actif=True).first()
    if not eleve or not trimestre:
        messages.error(request, "Aucun bulletin disponible pour le moment.")
        return redirect("grades:bulletin")

    contexte = _donnees_bulletin(eleve, trimestre)
    pdf_buffer = generer_bulletin_pdf(eleve, trimestre, contexte)

    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="bulletin_{eleve.matricule}_{trimestre.numero}.pdf"'
    return response
