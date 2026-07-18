import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import AnneeScolaire, Classe, Niveau
from accounts.models import Utilisateur
from accounts.permissions import role_required

from .models import Facture, FraisScolarite, Paiement
from .pdf import generer_recu_pdf
from .services import enregistrer_paiement, generer_factures


@role_required(Utilisateur.Role.ADMIN)
def frais_liste(request):
    frais_liste = FraisScolarite.objects.filter(
        annee_scolaire__etablissement=request.user.etablissement
    ).select_related("niveau", "annee_scolaire")
    return render(request, "finance/frais_liste.html", {"frais_liste": frais_liste})


@role_required(Utilisateur.Role.ADMIN)
def frais_creer(request):
    niveaux = Niveau.objects.all()

    if request.method == "POST":
        niveau = get_object_or_404(Niveau, pk=request.POST.get("niveau"))
        annee = get_object_or_404(
            AnneeScolaire, pk=request.POST.get("annee_scolaire"), etablissement=request.user.etablissement
        )
        libelle = request.POST.get("libelle", "").strip()
        try:
            montant = Decimal(request.POST.get("montant", "").strip())
            date_echeance = datetime.date.fromisoformat(request.POST.get("date_echeance", ""))
        except (InvalidOperation, ValueError):
            messages.error(request, "Montant ou date d'échéance invalide.")
            return redirect("finance:frais_creer")

        frais = FraisScolarite.objects.create(
            annee_scolaire=annee, niveau=niveau, libelle=libelle, montant=montant, date_echeance=date_echeance,
        )
        nb = generer_factures(frais)
        messages.success(request, f"Frais créé, {nb} facture(s) générée(s) pour les élèves du niveau.")
        return redirect("finance:frais_liste")

    annees = AnneeScolaire.objects.filter(etablissement=request.user.etablissement)
    return render(request, "finance/frais_creer.html", {"niveaux": niveaux, "annees": annees})


@role_required(Utilisateur.Role.ADMIN)
def facture_liste(request):
    factures = Facture.objects.filter(
        eleve__user__etablissement=request.user.etablissement
    ).select_related("eleve__user", "eleve__classe", "frais")

    classe_id = request.GET.get("classe", "")
    statut = request.GET.get("statut", "")
    if classe_id:
        factures = factures.filter(eleve__classe_id=classe_id)
    if statut:
        factures = factures.filter(statut=statut)

    classes = Classe.objects.filter(annee_scolaire__etablissement=request.user.etablissement)
    return render(
        request, "finance/facture_liste.html",
        {"factures": factures, "classes": classes, "statuts": Facture.Statut.choices, "classe_id": classe_id, "statut": statut},
    )


@role_required(Utilisateur.Role.ADMIN)
def facture_detail(request, facture_id):
    facture = get_object_or_404(
        Facture.objects.select_related("eleve__user", "frais"),
        pk=facture_id, eleve__user__etablissement=request.user.etablissement,
    )

    if request.method == "POST":
        try:
            montant = Decimal(request.POST.get("montant", "").strip())
            date_paiement = datetime.date.fromisoformat(request.POST.get("date_paiement", ""))
        except (InvalidOperation, ValueError):
            messages.error(request, "Montant ou date de paiement invalide.")
            return redirect("finance:facture_detail", facture_id=facture.pk)

        mode_paiement = request.POST.get("mode_paiement")
        reference = request.POST.get("reference", "").strip()
        enregistrer_paiement(facture, montant, date_paiement, mode_paiement, reference, request.user)
        messages.success(request, "Paiement enregistré.")
        return redirect("finance:facture_detail", facture_id=facture.pk)

    return render(
        request, "finance/facture_detail.html",
        {"facture": facture, "modes": Paiement.Mode.choices, "paiements": facture.paiements.all()},
    )


@role_required(Utilisateur.Role.ADMIN)
def recu_pdf(request, paiement_id):
    paiement = get_object_or_404(
        Paiement.objects.select_related("facture__eleve__user", "facture__eleve__classe", "facture__frais"),
        pk=paiement_id, facture__eleve__user__etablissement=request.user.etablissement,
    )
    buffer = generer_recu_pdf(paiement)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{paiement.numero_recu}.pdf"'
    return response


@role_required(Utilisateur.Role.ADMIN)
def tableau_bord(request):
    factures = Facture.objects.filter(eleve__user__etablissement=request.user.etablissement)
    total_attendu = factures.aggregate(total=Sum("montant"))["total"] or Decimal("0")
    total_encaisse = Paiement.objects.filter(
        facture__eleve__user__etablissement=request.user.etablissement
    ).aggregate(total=Sum("montant"))["total"] or Decimal("0")
    taux_recouvrement = round((total_encaisse / total_attendu) * 100, 1) if total_attendu else Decimal("0")

    impayes = factures.filter(
        statut__in=[Facture.Statut.EN_RETARD, Facture.Statut.PARTIELLEMENT_PAYEE]
    ).select_related(
        "eleve__user", "eleve__classe", "frais"
    ).order_by("frais__date_echeance")

    return render(
        request, "finance/tableau_bord.html",
        {
            "total_attendu": total_attendu, "total_encaisse": total_encaisse,
            "taux_recouvrement": taux_recouvrement, "impayes": impayes,
        },
    )


@role_required(Utilisateur.Role.ELEVE, Utilisateur.Role.PARENT)
def mes_frais(request):
    user = request.user
    enfants = None
    if user.role == Utilisateur.Role.ELEVE:
        eleve = user.eleve
    else:
        enfants = user.parent.enfants.select_related("user", "classe").all()
        enfant_id = request.GET.get("enfant")
        eleve = get_object_or_404(enfants, pk=enfant_id) if enfant_id else enfants.first()

    factures = (
        Facture.objects.filter(eleve=eleve).select_related("frais").prefetch_related("paiements")
        if eleve else Facture.objects.none()
    )
    return render(request, "finance/mes_frais.html", {"eleve": eleve, "enfants": enfants, "factures": factures})
