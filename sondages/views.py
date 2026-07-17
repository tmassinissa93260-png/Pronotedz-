from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Utilisateur
from accounts.permissions import role_required

from .models import ChoixReponse, QuestionSondage, ReponseUtilisateur, Sondage


@login_required
def liste(request):
    sondages = Sondage.visibles_pour(request.user.role)
    return render(request, "sondages/liste.html", {"sondages": sondages})


@login_required
def detail(request, sondage_id):
    sondage = get_object_or_404(Sondage.visibles_pour(request.user.role), pk=sondage_id)
    questions = sondage.questions.prefetch_related("choix")
    deja_vote = ReponseUtilisateur.objects.filter(question__sondage=sondage, utilisateur=request.user).exists()

    if request.method == "POST" and not deja_vote and sondage.est_ouvert:
        for question in questions:
            choix_id = request.POST.get(f"question_{question.pk}")
            if choix_id:
                choix = get_object_or_404(ChoixReponse, pk=choix_id, question=question)
                ReponseUtilisateur.objects.get_or_create(question=question, utilisateur=request.user, defaults={"choix": choix})
        messages.success(request, "Réponse enregistrée, merci !")
        return redirect("sondages:detail", sondage_id=sondage.pk)

    resultats = None
    if deja_vote or not sondage.est_ouvert:
        resultats = {
            question.pk: question.choix.annotate(nb_votes=Count("reponses")) for question in questions
        }

    return render(
        request,
        "sondages/detail.html",
        {"sondage": sondage, "questions": questions, "deja_vote": deja_vote, "resultats": resultats},
    )


@role_required(Utilisateur.Role.ADMIN)
def creer(request):
    if request.method == "POST":
        sondage = Sondage.objects.create(
            titre=request.POST.get("titre", "").strip(),
            description=request.POST.get("description", "").strip(),
            audience=request.POST.get("audience"),
            date_cloture=request.POST.get("date_cloture") or None,
            cree_par=request.user,
        )
        question = QuestionSondage.objects.create(sondage=sondage, texte=request.POST.get("question", "").strip())
        options = [ligne.strip() for ligne in request.POST.get("choix", "").splitlines() if ligne.strip()]
        for option in options:
            ChoixReponse.objects.create(question=question, texte=option)
        messages.success(request, "Sondage créé.")
        return redirect("sondages:liste")

    return render(request, "sondages/creer.html", {"audiences": Sondage.Audience.choices})
