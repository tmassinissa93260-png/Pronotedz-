from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.contacts import classes_enseignees
from accounts.models import Utilisateur
from accounts.permissions import role_required

from .models import ChoixQCM, QCM, QuestionQCM, TentativeQCM
from .services import parse_questions
from .services_ia import generer_qcm_brut


@role_required(Utilisateur.Role.ENSEIGNANT)
def qcm_liste_enseignant(request):
    qcms = QCM.objects.filter(enseignant=request.user.enseignant).select_related("classe", "matiere")
    return render(request, "qcm/qcm_liste_enseignant.html", {"qcms": qcms})


@role_required(Utilisateur.Role.ENSEIGNANT)
def qcm_creer(request):
    classes = classes_enseignees(request.user.enseignant)
    matieres = request.user.enseignant.matieres_enseignees.all()

    if request.method == "POST":
        classe = get_object_or_404(classes, pk=request.POST.get("classe"))
        matiere = get_object_or_404(matieres, pk=request.POST.get("matiere"))
        questions = parse_questions(request.POST.get("questions_brutes", ""))

        if not questions:
            messages.error(request, "Merci de saisir au moins une question avec ses choix.")
        else:
            qcm = QCM.objects.create(
                classe=classe,
                matiere=matiere,
                enseignant=request.user.enseignant,
                titre=request.POST.get("titre", "").strip(),
                description=request.POST.get("description", "").strip(),
                date_limite=request.POST.get("date_limite") or None,
            )
            for ordre, (question_texte, choix_list) in enumerate(questions, start=1):
                question = QuestionQCM.objects.create(qcm=qcm, texte=question_texte, ordre=ordre)
                for texte_choix, est_correct in choix_list:
                    ChoixQCM.objects.create(question=question, texte=texte_choix, est_correct=est_correct)
            messages.success(request, "QCM créé.")
            return redirect("qcm:qcm_liste_enseignant")

    return render(request, "qcm/qcm_creer.html", {"classes": classes, "matieres": matieres})


@role_required(Utilisateur.Role.ENSEIGNANT)
def qcm_generer_ia(request):
    classes = classes_enseignees(request.user.enseignant)
    matieres = request.user.enseignant.matieres_enseignees.all()
    contexte = {"classes": classes, "matieres": matieres, "titre_saisi": request.POST.get("titre", "")}

    if request.method == "POST":
        contenu_cours = request.POST.get("contenu_cours", "").strip()
        if not contenu_cours:
            messages.error(request, "Collez le contenu du cours à partir duquel générer le QCM.")
        else:
            etablissement = request.user.etablissement
            questions_brutes, erreur = generer_qcm_brut(etablissement, contenu_cours)
            if erreur:
                messages.error(request, erreur)
            elif not parse_questions(questions_brutes):
                messages.error(request, "L'IA n'a pas produit de questions exploitables. Réessayez ou saisissez-les manuellement.")
            else:
                contexte["questions_brutes_generees"] = questions_brutes
                messages.success(request, "QCM généré — relisez et modifiez les questions avant de les enregistrer.")

    return render(request, "qcm/qcm_creer.html", contexte)


@role_required(Utilisateur.Role.ENSEIGNANT)
def qcm_resultats(request, qcm_id):
    qcm = get_object_or_404(QCM, pk=qcm_id, enseignant=request.user.enseignant)
    eleves = qcm.classe.eleves.select_related("user").order_by("user__last_name")
    tentatives = {t.eleve_id: t for t in qcm.tentatives.all()}
    lignes = [{"eleve": eleve, "tentative": tentatives.get(eleve.pk)} for eleve in eleves]
    return render(request, "qcm/qcm_resultats.html", {"qcm": qcm, "lignes": lignes})


@role_required(Utilisateur.Role.ELEVE)
def qcm_liste_eleve(request):
    qcms = QCM.objects.filter(classe=request.user.eleve.classe).select_related("matiere")
    tentatives = {t.qcm_id: t for t in TentativeQCM.objects.filter(eleve=request.user.eleve)}
    for qcm in qcms:
        qcm.ma_tentative = tentatives.get(qcm.pk)
    return render(request, "qcm/qcm_liste_eleve.html", {"qcms": qcms})


@role_required(Utilisateur.Role.ELEVE)
def qcm_passer(request, qcm_id):
    qcm = get_object_or_404(QCM, pk=qcm_id, classe=request.user.eleve.classe)
    questions = qcm.questions.prefetch_related("choix")
    tentative = TentativeQCM.objects.filter(qcm=qcm, eleve=request.user.eleve).first()

    if tentative and tentative.est_soumise:
        reponses = {r.question_id: r.choix_id for r in tentative.reponses.all()}
        return render(
            request,
            "qcm/qcm_resultat_eleve.html",
            {"qcm": qcm, "questions": questions, "tentative": tentative, "reponses": reponses},
        )

    if request.method == "POST" and qcm.est_ouvert:
        tentative = tentative or TentativeQCM.objects.create(qcm=qcm, eleve=request.user.eleve)
        reponses_par_question = {
            question.pk: request.POST.get(f"question_{question.pk}") for question in questions
        }
        tentative.corriger_et_soumettre(reponses_par_question)
        messages.success(request, "QCM soumis, voici votre résultat.")
        return redirect("qcm:qcm_passer", qcm_id=qcm.pk)

    return render(request, "qcm/qcm_passer.html", {"qcm": qcm, "questions": questions})
