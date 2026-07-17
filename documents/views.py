from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import Classe
from accounts.contacts import classes_enseignees
from accounts.models import Utilisateur
from accounts.permissions import role_required

from .models import Document


def _visibles_pour_classes(classes):
    return Document.objects.filter(Q(classe__isnull=True) | Q(classe__in=classes))


@role_required(Utilisateur.Role.ADMIN, Utilisateur.Role.ENSEIGNANT, Utilisateur.Role.ELEVE, Utilisateur.Role.PARENT)
def liste(request):
    user = request.user

    if user.role == Utilisateur.Role.ADMIN:
        documents = Document.objects.all()
    elif user.role == Utilisateur.Role.ENSEIGNANT:
        documents = _visibles_pour_classes(classes_enseignees(user.enseignant))
    elif user.role == Utilisateur.Role.ELEVE:
        documents = _visibles_pour_classes([user.eleve.classe])
    else:
        enfants = user.parent.enfants.select_related("classe").all()
        documents = _visibles_pour_classes([enfant.classe for enfant in enfants])

    documents = documents.select_related("classe", "depose_par").order_by("-date_depot")
    return render(request, "documents/liste.html", {"documents": documents})


@role_required(Utilisateur.Role.ADMIN, Utilisateur.Role.ENSEIGNANT)
def deposer(request):
    user = request.user
    classes = Classe.objects.all() if user.role == Utilisateur.Role.ADMIN else classes_enseignees(user.enseignant)

    if request.method == "POST":
        classe_id = request.POST.get("classe")
        classe = get_object_or_404(classes, pk=classe_id) if classe_id else None
        if classe is None and user.role != Utilisateur.Role.ADMIN:
            messages.error(request, "Veuillez choisir une classe.")
        else:
            Document.objects.create(
                titre=request.POST.get("titre", "").strip(),
                fichier=request.FILES.get("fichier"),
                description=request.POST.get("description", "").strip(),
                categorie=request.POST.get("categorie"),
                classe=classe,
                depose_par=user,
            )
            messages.success(request, "Document déposé.")
            return redirect("documents:liste")

    return render(
        request,
        "documents/deposer.html",
        {"classes": classes, "categories": Document.Categorie.choices, "est_admin": user.role == Utilisateur.Role.ADMIN},
    )
