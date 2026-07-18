from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import Matiere, Trimestre
from accounts.contacts import classes_enseignees
from accounts.models import Utilisateur
from accounts.permissions import role_required
from notifications.models import Notification
from notifications.services import notifier

from .models import AppreciationGenerale, AppreciationMatiere, Evaluation, Note
from .services import moyenne_generale, moyenne_matiere, rang_classe, statistiques_classe_matiere
from .services_ia import generer_appreciation


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


def _trimestre_actif_pour(eleve):
    if not eleve:
        return None
    return Trimestre.objects.filter(annee_scolaire=eleve.classe.annee_scolaire, est_actif=True).first()


@role_required(Utilisateur.Role.ELEVE, Utilisateur.Role.PARENT)
def bulletin(request):
    eleve, enfants = _resoudre_eleve(request)
    trimestre = _trimestre_actif_pour(eleve)
    contexte = _donnees_bulletin(eleve, trimestre)
    contexte.update({"eleve": eleve, "enfants": enfants, "trimestre": trimestre})
    return render(request, "grades/bulletin.html", contexte)


@role_required(Utilisateur.Role.ELEVE, Utilisateur.Role.PARENT)
def bulletin_pdf(request):
    from .pdf import generer_bulletin_pdf

    eleve, enfants = _resoudre_eleve(request)
    trimestre = _trimestre_actif_pour(eleve)
    if not eleve or not trimestre:
        messages.error(request, "Aucun bulletin disponible pour le moment.")
        return redirect("grades:bulletin")

    contexte = _donnees_bulletin(eleve, trimestre)
    pdf_buffer = generer_bulletin_pdf(eleve, trimestre, contexte)

    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="bulletin_{eleve.matricule}_{trimestre.numero}.pdf"'
    return response


@role_required(Utilisateur.Role.ENSEIGNANT)
def saisie_appreciations(request):
    classes = classes_enseignees(request.user.enseignant)
    matieres = request.user.enseignant.matieres_enseignees.all()

    if request.method == "POST":
        classe = get_object_or_404(classes, pk=request.POST.get("classe"))
        matiere = get_object_or_404(matieres, pk=request.POST.get("matiere"))
        trimestre = get_object_or_404(classe.annee_scolaire.trimestres, pk=request.POST.get("trimestre"))
        action = request.POST.get("action", "enregistrer")
        redirection = redirect(f"{request.path}?classe={classe.pk}&matiere={matiere.pk}&trimestre={trimestre.pk}")

        if action == "generer_tout":
            deja_generees = set(
                AppreciationMatiere.objects.filter(matiere=matiere, trimestre=trimestre, eleve__classe=classe)
                .exclude(texte="")
                .values_list("eleve_id", flat=True)
            )
            for eleve in classe.eleves.exclude(pk__in=deja_generees):
                texte, erreur = generer_appreciation(request.user.etablissement, eleve, matiere, trimestre)
                if erreur:
                    messages.error(request, erreur)
                    break
                AppreciationMatiere.objects.update_or_create(
                    eleve=eleve, matiere=matiere, trimestre=trimestre,
                    defaults={"texte": texte, "enseignant": request.user.enseignant},
                )
            else:
                messages.success(request, "Appréciations générées — relisez-les avant de les enregistrer.")
            return redirection

        if action.startswith("generer_"):
            eleve = get_object_or_404(classe.eleves, pk=action.removeprefix("generer_"))
            texte, erreur = generer_appreciation(request.user.etablissement, eleve, matiere, trimestre)
            if erreur:
                messages.error(request, erreur)
            else:
                AppreciationMatiere.objects.update_or_create(
                    eleve=eleve, matiere=matiere, trimestre=trimestre,
                    defaults={"texte": texte, "enseignant": request.user.enseignant},
                )
            return redirection

        for eleve in classe.eleves.all():
            texte = request.POST.get(f"appreciation_{eleve.pk}", "").strip()
            AppreciationMatiere.objects.update_or_create(
                eleve=eleve, matiere=matiere, trimestre=trimestre,
                defaults={"texte": texte, "enseignant": request.user.enseignant},
            )
        messages.success(request, "Appréciations enregistrées.")
        return redirection

    classe = classes.filter(pk=request.GET.get("classe")).first() or classes.first()
    matiere = matieres.filter(pk=request.GET.get("matiere")).first() or matieres.first()
    trimestre = None
    eleves_ctx = []
    if classe:
        trimestre = (
            classe.annee_scolaire.trimestres.filter(pk=request.GET.get("trimestre")).first()
            or classe.annee_scolaire.trimestres.filter(est_actif=True).first()
        )
    if classe and matiere and trimestre:
        appreciations = {
            a.eleve_id: a.texte
            for a in AppreciationMatiere.objects.filter(eleve__classe=classe, matiere=matiere, trimestre=trimestre)
        }
        for eleve in classe.eleves.select_related("user").order_by("user__last_name"):
            eleves_ctx.append({
                "eleve": eleve,
                "moyenne": moyenne_matiere(eleve, matiere, trimestre),
                "appreciation": appreciations.get(eleve.pk, ""),
            })

    return render(
        request, "grades/saisie_appreciations.html",
        {
            "classes": classes, "matieres": matieres, "classe": classe, "matiere": matiere,
            "trimestre": trimestre, "eleves_ctx": eleves_ctx,
        },
    )
