from django.db import models


class Ressource(models.Model):
    class TypeRessource(models.TextChoices):
        SALLE = "SALLE", "Salle"
        MATERIEL = "MATERIEL", "Matériel"

    etablissement = models.ForeignKey(
        "academics.Etablissement", on_delete=models.CASCADE, related_name="ressources", null=True, blank=True
    )
    nom = models.CharField(max_length=100)
    type_ressource = models.CharField(max_length=10, choices=TypeRessource.choices)
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.nom


class Reservation(models.Model):
    ressource = models.ForeignKey(Ressource, on_delete=models.CASCADE, related_name="reservations")
    enseignant = models.ForeignKey("accounts.Enseignant", on_delete=models.CASCADE, related_name="reservations_ressources")
    date = models.DateField()
    creneau = models.ForeignKey("timetable.CreneauHoraire", on_delete=models.CASCADE, related_name="reservations_ressources")
    motif = models.CharField(max_length=255, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "creneau__ordre"]
        unique_together = ("ressource", "date", "creneau")

    def __str__(self):
        return f"{self.ressource} — {self.date} ({self.creneau})"
