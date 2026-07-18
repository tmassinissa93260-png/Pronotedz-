from django.core.exceptions import ValidationError
from django.db import models


class CreneauHoraire(models.Model):
    class Jour(models.IntegerChoices):
        DIMANCHE = 0, "Dimanche"
        LUNDI = 1, "Lundi"
        MARDI = 2, "Mardi"
        MERCREDI = 3, "Mercredi"
        JEUDI = 4, "Jeudi"
        SAMEDI = 5, "Samedi"

    # Mapping from Python's date.weekday() (Monday=0..Sunday=6) to our Jour
    # values. Friday has no entry: the Algerian school week is Dimanche-Jeudi
    # (+ Samedi in some établissements), Vendredi is never a school day.
    PYTHON_WEEKDAY_TO_JOUR = {0: Jour.LUNDI, 1: Jour.MARDI, 2: Jour.MERCREDI, 3: Jour.JEUDI, 5: Jour.SAMEDI, 6: Jour.DIMANCHE}

    jour_semaine = models.PositiveSmallIntegerField(choices=Jour.choices)
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    ordre = models.PositiveSmallIntegerField(help_text="Rang du créneau dans la journée")

    class Meta:
        verbose_name = "Créneau horaire"
        verbose_name_plural = "Créneaux horaires"
        ordering = ["jour_semaine", "ordre"]
        unique_together = ("jour_semaine", "ordre")

    def __str__(self):
        return f"{self.get_jour_semaine_display()} {self.heure_debut:%H:%M}-{self.heure_fin:%H:%M}"


class EmploiDuTempsEntry(models.Model):
    classe = models.ForeignKey("academics.Classe", on_delete=models.CASCADE, related_name="emploi_du_temps")
    matiere = models.ForeignKey("academics.Matiere", on_delete=models.CASCADE, related_name="emploi_du_temps")
    enseignant = models.ForeignKey("accounts.Enseignant", on_delete=models.CASCADE, related_name="emploi_du_temps")
    salle = models.ForeignKey("academics.Salle", on_delete=models.CASCADE, related_name="emploi_du_temps")
    creneau = models.ForeignKey(CreneauHoraire, on_delete=models.CASCADE, related_name="entrees")
    annee_scolaire = models.ForeignKey("academics.AnneeScolaire", on_delete=models.CASCADE, related_name="emploi_du_temps")

    class Meta:
        verbose_name = "Entrée d'emploi du temps"
        verbose_name_plural = "Emploi du temps"
        unique_together = (
            ("classe", "creneau", "annee_scolaire"),
            ("enseignant", "creneau", "annee_scolaire"),
            ("salle", "creneau", "annee_scolaire"),
        )

    def __str__(self):
        return f"{self.classe} — {self.matiere} — {self.creneau}"

    def clean(self):
        conflits = []
        autres = EmploiDuTempsEntry.objects.filter(
            creneau=self.creneau, annee_scolaire=self.annee_scolaire
        ).exclude(pk=self.pk)

        if autres.filter(classe=self.classe).exists():
            conflits.append(f"La classe {self.classe} a déjà un cours à ce créneau.")
        if autres.filter(enseignant=self.enseignant).exists():
            conflits.append(f"{self.enseignant} a déjà un cours à ce créneau.")
        if autres.filter(salle=self.salle).exists():
            conflits.append(f"La salle {self.salle} est déjà occupée à ce créneau.")

        if conflits:
            raise ValidationError(" ".join(conflits))
