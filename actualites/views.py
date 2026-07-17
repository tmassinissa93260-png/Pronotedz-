from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.models import Utilisateur
from accounts.permissions import role_required

from .models import Publication


@login_required
def liste(request):
    publications = Publication.visibles_pour(request.user.role)
    return render(request, "actualites/liste.html", {"publications": publications})


@role_required(Utilisateur.Role.ADMIN)
def creer(request):
    if request.method == "POST":
        Publication.objects.create(
            titre=request.POST.get("titre", "").strip(),
            contenu=request.POST.get("contenu", "").strip(),
            audience=request.POST.get("audience"),
            epingle=bool(request.POST.get("epingle")),
            auteur=request.user,
        )
        messages.success(request, "Publication créée.")
        return redirect("actualites:liste")

    return render(request, "actualites/creer.html", {"audiences": Publication.Audience.choices})
