from django.db import models
from django.utils import timezone


class FraisScolarite(models.Model):
    annee_scolaire = models.ForeignKey(
        "academics.AnneeScolaire", on_delete=models.CASCADE, related_name="frais_scolarite"
    )
    niveau = models.ForeignKey("academics.Niveau", on_delete=models.CASCADE, related_name="frais_scolarite")
    libelle = models.CharField(max_length=150, help_text='Ex: "Frais d\'inscription", "Trimestre 1"')
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date_echeance = models.DateField()

    class Meta:
        verbose_name = "Frais de scolarité"
        verbose_name_plural = "Frais de scolarité"
        ordering = ["date_echeance"]

    def __str__(self):
        return f"{self.libelle} — {self.niveau} ({self.annee_scolaire})"


class Facture(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        PARTIELLEMENT_PAYEE = "PARTIELLEMENT_PAYEE", "Partiellement payée"
        PAYEE = "PAYEE", "Payée"
        EN_RETARD = "EN_RETARD", "En retard"

    eleve = models.ForeignKey("accounts.Eleve", on_delete=models.CASCADE, related_name="factures")
    frais = models.ForeignKey(FraisScolarite, on_delete=models.CASCADE, related_name="factures")
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Facture"
        unique_together = ("eleve", "frais")
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.eleve} — {self.frais}"

    @property
    def montant_paye(self):
        return self.paiements.aggregate(total=models.Sum("montant"))["total"] or 0

    @property
    def montant_restant(self):
        return self.montant - self.montant_paye


class Paiement(models.Model):
    class Mode(models.TextChoices):
        ESPECES = "ESPECES", "Espèces"
        VIREMENT = "VIREMENT", "Virement"
        CHEQUE = "CHEQUE", "Chèque"
        CCP = "CCP", "CCP"

    facture = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name="paiements")
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date_paiement = models.DateField()
    mode_paiement = models.CharField(max_length=10, choices=Mode.choices, default=Mode.ESPECES)
    reference = models.CharField(max_length=100, blank=True)
    saisi_par = models.ForeignKey(
        "accounts.Utilisateur", on_delete=models.SET_NULL, null=True, related_name="paiements_saisis"
    )
    numero_recu = models.CharField(max_length=40, unique=True, editable=False)

    class Meta:
        verbose_name = "Paiement"
        ordering = ["-date_paiement"]

    def __str__(self):
        return f"Reçu {self.numero_recu} — {self.facture.eleve} — {self.montant} DA"

    def save(self, *args, **kwargs):
        if not self.numero_recu:
            self.numero_recu = f"REC-{self.facture.eleve.matricule}-{timezone.now():%Y%m%d%H%M%S%f}"
        super().save(*args, **kwargs)
