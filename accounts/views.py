from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import redirect, render

from academics.models import AnneeScolaire
from .csv_import import importer_eleves, importer_enseignants, importer_parents
from .models import Utilisateur
from .permissions import role_required


def changer_mot_de_passe(request):
    if not request.user.is_authenticated:
        return redirect("login")

    if request.method == "POST":
        mot_de_passe1 = request.POST.get("mot_de_passe1", "")
        mot_de_passe2 = request.POST.get("mot_de_passe2", "")
        if len(mot_de_passe1) < 8:
            messages.error(request, "Le mot de passe doit contenir au moins 8 caractères.")
        elif mot_de_passe1 != mot_de_passe2:
            messages.error(request, "Les deux mots de passe ne correspondent pas.")
        else:
            request.user.set_password(mot_de_passe1)
            request.user.must_change_password = False
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Mot de passe modifié avec succès.")
            return redirect("dashboard:dispatch")

    return render(request, "registration/changer_mot_de_passe.html")


@role_required(Utilisateur.Role.ADMIN)
def import_csv(request):
    resultat = None

    if request.method == "POST":
        type_import = request.POST.get("type_import")
        fichier = request.FILES.get("fichier")
        annee = AnneeScolaire.objects.filter(est_active=True).first()

        if not fichier:
            messages.error(request, "Merci de sélectionner un fichier CSV.")
        elif type_import == "eleves":
            nb_crees, erreurs, comptes = importer_eleves(fichier, annee)
            resultat = {"nb_crees": nb_crees, "erreurs": erreurs, "comptes": comptes}
        elif type_import == "enseignants":
            nb_crees, erreurs, comptes = importer_enseignants(fichier)
            resultat = {"nb_crees": nb_crees, "erreurs": erreurs, "comptes": comptes}
        elif type_import == "parents":
            nb_crees, erreurs, comptes = importer_parents(fichier)
            resultat = {"nb_crees": nb_crees, "erreurs": erreurs, "comptes": comptes}

    return render(request, "accounts/import_csv.html", {"resultat": resultat})
