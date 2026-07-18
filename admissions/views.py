from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from academics.models import Classe, Etablissement, Niveau
from accounts.models import Utilisateur
from accounts.permissions import role_required

from .models import Candidature
from .services import changer_statut, convertir_en_eleve


def candidature_form(request, slug):
    etablissement = get_object_or_404(Etablissement, slug=slug)
    niveaux = Niveau.objects.all().order_by("ordre")

    if request.method == "POST":
        erreurs = []
        nom = request.POST.get("nom", "").strip()
        prenom = request.POST.get("prenom", "").strip()
        nom_parent = request.POST.get("nom_parent", "").strip()
        telephone_parent = request.POST.get("telephone_parent", "").strip()
        email_parent = request.POST.get("email_parent", "").strip()
        niveau_id = request.POST.get("niveau_souhaite")
        niveau = niveaux.filter(pk=niveau_id).first()

        if not nom or not prenom:
            erreurs.append("Le nom et le prénom de l'enfant sont obligatoires.")
        if not nom_parent or not telephone_parent or not email_parent:
            erreurs.append("Les coordonnées du parent (nom, téléphone, email) sont obligatoires.")
        if not niveau:
            erreurs.append("Merci de choisir le niveau souhaité.")

        if not erreurs:
            candidature = Candidature.objects.create(
                etablissement=etablissement,
                niveau_souhaite=niveau,
                nom=nom,
                prenom=prenom,
                date_naissance=request.POST.get("date_naissance") or None,
                sexe=request.POST.get("sexe", ""),
                nom_parent=nom_parent,
                telephone_parent=telephone_parent,
                email_parent=email_parent,
                adresse=request.POST.get("adresse", "").strip(),
                bulletin_precedent=request.FILES.get("bulletin_precedent"),
                acte_naissance=request.FILES.get("acte_naissance"),
                photo=request.FILES.get("photo"),
            )
            return redirect("admissions:candidature_confirmation", reference=candidature.reference)

        for erreur in erreurs:
            messages.error(request, erreur)

    return render(
        request,
        "admissions/candidature_form.html",
        {"etablissement": etablissement, "niveaux": niveaux, "sexes": Candidature.Sexe.choices},
    )


def candidature_confirmation(request, reference):
    candidature = get_object_or_404(Candidature, reference=reference)
    return render(request, "admissions/candidature_confirmation.html", {"candidature": candidature})


def candidature_suivi(request):
    candidature = None
    recherche = False
    if request.method == "POST":
        recherche = True
        reference = request.POST.get("reference", "").strip().upper()
        email = request.POST.get("email", "").strip()
        candidature = Candidature.objects.filter(reference=reference, email_parent__iexact=email).first()

    return render(request, "admissions/candidature_suivi.html", {"candidature": candidature, "recherche": recherche})


@role_required(Utilisateur.Role.ADMIN)
def candidature_liste(request):
    candidatures = Candidature.objects.filter(etablissement=request.user.etablissement).select_related("niveau_souhaite")
    statut = request.GET.get("statut")
    if statut:
        candidatures = candidatures.filter(statut=statut)

    return render(
        request,
        "admissions/candidature_liste.html",
        {"candidatures": candidatures, "statuts": Candidature.Statut.choices, "statut_filtre": statut},
    )


@role_required(Utilisateur.Role.ADMIN)
def candidature_detail(request, candidature_id):
    candidature = get_object_or_404(Candidature, pk=candidature_id, etablissement=request.user.etablissement)

    if request.method == "POST":
        nouveau_statut = request.POST.get("statut")
        if nouveau_statut in Candidature.Statut.values:
            changer_statut(candidature, nouveau_statut, request.user, notes=request.POST.get("notes_admin", "").strip())
            messages.success(request, "Statut mis à jour, la famille a été notifiée par email.")
            return redirect("admissions:candidature_detail", candidature_id=candidature.pk)

    classes = (
        Classe.objects.filter(niveau=candidature.niveau_souhaite, annee_scolaire__etablissement=request.user.etablissement)
        if candidature.statut == Candidature.Statut.ACCEPTE
        else Classe.objects.none()
    )
    return render(
        request,
        "admissions/candidature_detail.html",
        {"candidature": candidature, "statuts": Candidature.Statut.choices, "classes": classes},
    )


@role_required(Utilisateur.Role.ADMIN)
@require_http_methods(["POST"])
def candidature_convertir(request, candidature_id):
    candidature = get_object_or_404(Candidature, pk=candidature_id, etablissement=request.user.etablissement)
    classe = get_object_or_404(
        Classe, pk=request.POST.get("classe"), niveau=candidature.niveau_souhaite,
        annee_scolaire__etablissement=request.user.etablissement,
    )

    try:
        eleve, username, mot_de_passe = convertir_en_eleve(candidature, classe)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("admissions:candidature_detail", candidature_id=candidature.pk)

    return render(
        request,
        "admissions/candidature_convertie.html",
        {"candidature": candidature, "eleve": eleve, "username": username, "mot_de_passe": mot_de_passe},
    )


@role_required(Utilisateur.Role.ADMIN)
def portail_candidature_liens(request):
    """Helper page giving the admin the shareable public URL for their school."""
    return render(request, "admissions/portail_liens.html", {"etablissement": request.user.etablissement})
