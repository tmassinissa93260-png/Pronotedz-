from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Utilisateur
from accounts.permissions import role_required
from notifications.models import Notification
from notifications.services import notifier_plusieurs

from .models import LectureAccusee, Publication


@login_required
def liste(request):
    publications = list(Publication.visibles_pour(request.user))
    lues_ids = set(
        LectureAccusee.objects.filter(utilisateur=request.user, publication__in=publications).values_list(
            "publication_id", flat=True
        )
    )
    for publication in publications:
        publication.lue_par_moi = publication.pk in lues_ids
    return render(request, "actualites/liste.html", {"publications": publications})


@login_required
def marquer_lu(request, publication_id):
    publication = get_object_or_404(Publication.visibles_pour(request.user), pk=publication_id)
    LectureAccusee.objects.get_or_create(publication=publication, utilisateur=request.user)
    return redirect("actualites:liste")


@role_required(Utilisateur.Role.ADMIN)
def suivi_lecture(request, publication_id):
    publication = get_object_or_404(Publication, pk=publication_id, etablissement=request.user.etablissement)
    destinataires = list(publication.destinataires().select_related())
    lues_ids = set(
        LectureAccusee.objects.filter(publication=publication).values_list("utilisateur_id", flat=True)
    )
    lignes = [{"utilisateur": u, "lu": u.pk in lues_ids} for u in destinataires]
    nb_lu = sum(1 for l in lignes if l["lu"])
    return render(
        request,
        "actualites/suivi_lecture.html",
        {"publication": publication, "lignes": lignes, "nb_lu": nb_lu, "nb_total": len(lignes)},
    )


@role_required(Utilisateur.Role.ADMIN)
def creer(request):
    if request.method == "POST":
        publication = Publication.objects.create(
            titre=request.POST.get("titre", "").strip(),
            contenu=request.POST.get("contenu", "").strip(),
            audience=request.POST.get("audience"),
            epingle=bool(request.POST.get("epingle")),
            auteur=request.user,
            etablissement=request.user.etablissement,
        )
        notifier_plusieurs(
            publication.destinataires(),
            Notification.Type.INFO,
            titre=publication.titre,
            contenu=publication.contenu,
            lien="/actualites/",
        )
        messages.success(request, "Publication créée.")
        return redirect("actualites:liste")

    return render(request, "actualites/creer.html", {"audiences": Publication.Audience.choices})
