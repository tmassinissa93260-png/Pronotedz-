from django.db import models
from django.db.models import Q


class Seance(models.Model):
    class Statut(models.TextChoices):
        NORMALE = "NORMALE", "Normale"
        ANNULEE = "ANNULEE", "Annulée"
        REMPLACEE = "REMPLACEE", "Remplacée"

    emploi_du_temps_entry = models.ForeignKey(
        "timetable.EmploiDuTempsEntry", on_delete=models.CASCADE, related_name="seances"
    )
    date = models.DateField()
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.NORMALE)
    enseignant_remplacant = models.ForeignKey(
        "accounts.Enseignant", on_delete=models.SET_NULL, null=True, blank=True, related_name="seances_remplacees"
    )

    class Meta:
        unique_together = ("emploi_du_temps_entry", "date")
        ordering = ["date"]

    def __str__(self):
        return f"{self.emploi_du_temps_entry} — {self.date}"

    @property
    def classe(self):
        return self.emploi_du_temps_entry.classe

    @property
    def matiere(self):
        return self.emploi_du_temps_entry.matiere

    @property
    def enseignant(self):
        return self.enseignant_remplacant or self.emploi_du_temps_entry.enseignant

    @classmethod
    def get_or_create_for(cls, emploi_du_temps_entry, date):
        seance, _ = cls.objects.get_or_create(emploi_du_temps_entry=emploi_du_temps_entry, date=date)
        return seance


class Absence(models.Model):
    seance = models.ForeignKey(Seance, on_delete=models.CASCADE, related_name="absences")
    eleve = models.ForeignKey("accounts.Eleve", on_delete=models.CASCADE, related_name="absences")
    justifiee = models.BooleanField(default=False)
    motif = models.CharField(max_length=255, blank=True)
    saisie_par = models.ForeignKey("accounts.Utilisateur", on_delete=models.SET_NULL, null=True, related_name="absences_saisies")
    date_saisie = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("seance", "eleve")
        ordering = ["-seance__date"]

    def __str__(self):
        return f"{self.eleve} — {self.seance}"


class Retard(models.Model):
    eleve = models.ForeignKey("accounts.Eleve", on_delete=models.CASCADE, related_name="retards")
    date = models.DateField()
    heure_arrivee = models.TimeField()
    duree_minutes = models.PositiveSmallIntegerField()
    motif = models.CharField(max_length=255, blank=True)
    justifie = models.BooleanField(default=False)
    saisi_par = models.ForeignKey("accounts.Utilisateur", on_delete=models.SET_NULL, null=True, related_name="retards_saisis")

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.eleve} — {self.date}"


class Justificatif(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        APPROUVE = "APPROUVE", "Approuvé"
        REJETE = "REJETE", "Rejeté"

    absence = models.ForeignKey(Absence, on_delete=models.CASCADE, null=True, blank=True, related_name="justificatifs")
    retard = models.ForeignKey(Retard, on_delete=models.CASCADE, null=True, blank=True, related_name="justificatifs")
    fichier = models.FileField(upload_to="justificatifs/")
    commentaire = models.CharField(max_length=255, blank=True)
    soumis_par = models.ForeignKey("accounts.Utilisateur", on_delete=models.SET_NULL, null=True, related_name="justificatifs_soumis")
    date_soumission = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.EN_ATTENTE)
    traite_par = models.ForeignKey(
        "accounts.Utilisateur", on_delete=models.SET_NULL, null=True, blank=True, related_name="justificatifs_traites"
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(absence__isnull=False, retard__isnull=True)
                    | Q(absence__isnull=True, retard__isnull=False)
                ),
                name="justificatif_absence_xor_retard",
            )
        ]

    def __str__(self):
        return f"Justificatif ({self.get_statut_display()})"
