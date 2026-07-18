from django.db import models


class Observation(models.Model):
    class TypeObservation(models.TextChoices):
        OBSERVATION = "OBSERVATION", "Observation"
        ENCOURAGEMENT = "ENCOURAGEMENT", "Encouragement"
        AVERTISSEMENT = "AVERTISSEMENT", "Avertissement"
        SANCTION = "SANCTION", "Sanction"

    eleve = models.ForeignKey("accounts.Eleve", on_delete=models.CASCADE, related_name="observations")
    type_observation = models.CharField(max_length=15, choices=TypeObservation.choices)
    matiere = models.ForeignKey("academics.Matiere", on_delete=models.SET_NULL, null=True, blank=True, related_name="observations")
    motif = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField()
    saisie_par = models.ForeignKey("accounts.Utilisateur", on_delete=models.SET_NULL, null=True, related_name="observations_saisies")

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.get_type_observation_display()} — {self.eleve} — {self.date}"
