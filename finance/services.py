from django.utils import timezone

from accounts.models import Eleve

from .models import Facture, Paiement


def generer_factures(frais):
    """Creates one Facture per Eleve of the fee's niveau/année, skipping
    students who already have one (safe to call again after adding pupils)."""
    eleves = Eleve.objects.filter(classe__niveau=frais.niveau, classe__annee_scolaire=frais.annee_scolaire)
    nb_creees = 0
    for eleve in eleves:
        _, created = Facture.objects.get_or_create(eleve=eleve, frais=frais, defaults={"montant": frais.montant})
        if created:
            nb_creees += 1
    return nb_creees


def recalculer_statut(facture):
    if facture.montant_restant <= 0:
        statut = Facture.Statut.PAYEE
    elif facture.montant_paye > 0:
        statut = Facture.Statut.PARTIELLEMENT_PAYEE
    elif facture.frais.date_echeance < timezone.now().date():
        statut = Facture.Statut.EN_RETARD
    else:
        statut = Facture.Statut.EN_ATTENTE

    if statut != facture.statut:
        facture.statut = statut
        facture.save(update_fields=["statut"])
    return facture


def enregistrer_paiement(facture, montant, date_paiement, mode_paiement, reference, saisi_par):
    paiement = Paiement.objects.create(
        facture=facture, montant=montant, date_paiement=date_paiement,
        mode_paiement=mode_paiement, reference=reference, saisi_par=saisi_par,
    )
    recalculer_statut(facture)
    return paiement
