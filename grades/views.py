from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import Matiere, Trimestre
from accounts.models import Utilisateur
from accounts.permissions import role_required

from .models import Evaluation, Note
from .services import moyenne_generale, moyenne_matiere, rang_classe


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


@role_required(Utilisateur.Role.ELEVE, Utilisateur.Role.PARENT)
def bulletin(request):
    user = request.user
    eleve = None
    enfants = None

    if user.role == user.Role.ELEVE:
        eleve = user.eleve
    else:
        enfants = user.parent.enfants.select_related("user").all()
        enfant_id = request.GET.get("enfant")
        eleve = get_object_or_404(enfants, pk=enfant_id) if enfant_id else enfants.first()

    trimestre = Trimestre.objects.filter(est_actif=True).first()
    lignes = []
    moyenne_gen = None
    rang, effectif = None, 0

    if eleve and trimestre:
        matieres = Matiere.objects.filter(
            evaluations__classe=eleve.classe, evaluations__trimestre=trimestre
        ).distinct()
        for matiere in matieres:
            lignes.append(
                {
                    "matiere": matiere,
                    "moyenne": moyenne_matiere(eleve, matiere, trimestre),
                    "coefficient": eleve.classe.coefficient_pour(matiere),
                }
            )
        moyenne_gen = moyenne_generale(eleve, trimestre)
        rang, effectif = rang_classe(eleve, trimestre)

    return render(
        request,
        "grades/bulletin.html",
        {
            "eleve": eleve,
            "enfants": enfants,
            "trimestre": trimestre,
            "lignes": lignes,
            "moyenne_generale": moyenne_gen,
            "rang": rang,
            "effectif": effectif,
        },
    )
