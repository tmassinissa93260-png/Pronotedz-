from django.db import models


class DisponibiliteRDV(models.Model):
    enseignant = models.ForeignKey("accounts.Enseignant", on_delete=models.CASCADE, related_name="disponibilites")
    date = models.DateField()
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()

    class Meta:
        verbose_name = "Disponibilité de rendez-vous"
        verbose_name_plural = "Disponibilités de rendez-vous"
        ordering = ["date", "heure_debut"]
        unique_together = ("enseignant", "date", "heure_debut")

    def __str__(self):
        return f"{self.enseignant} — {self.date} {self.heure_debut:%H:%M}"

    @property
    def est_reservee(self):
        # Cancelling a RendezVous deletes it (see rendezvous.views.annuler) so the
        # slot becomes bookable again.
        return hasattr(self, "rendez_vous")


class RendezVous(models.Model):
    disponibilite = models.OneToOneField(DisponibiliteRDV, on_delete=models.CASCADE, related_name="rendez_vous")
    parent = models.ForeignKey("accounts.Parent", on_delete=models.CASCADE, related_name="rendez_vous")
    eleve_concerne = models.ForeignKey("accounts.Eleve", on_delete=models.CASCADE, related_name="rendez_vous")
    motif = models.CharField(max_length=255, blank=True)
    date_demande = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"RDV {self.parent} — {self.disponibilite}"
