from django.db import models


class ProgrammeChapitre(models.Model):
    """The official Algerian curriculum's chapter list for one matière at one
    niveau — reference data, managed like CoefficientMatiere."""

    niveau = models.ForeignKey("academics.Niveau", on_delete=models.CASCADE, related_name="chapitres_programme")
    matiere = models.ForeignKey("academics.Matiere", on_delete=models.CASCADE, related_name="chapitres_programme")
    ordre = models.PositiveSmallIntegerField(default=1)
    titre = models.CharField(max_length=200)

    class Meta:
        ordering = ["niveau", "matiere", "ordre"]
        unique_together = ("niveau", "matiere", "ordre")
        verbose_name = "Chapitre du programme"
        verbose_name_plural = "Chapitres du programme"

    def __str__(self):
        return f"{self.matiere} — {self.titre} ({self.niveau})"


class AnnaleExamen(models.Model):
    niveau = models.ForeignKey("academics.Niveau", on_delete=models.CASCADE, related_name="annales")
    matiere = models.ForeignKey("academics.Matiere", on_delete=models.CASCADE, related_name="annales")
    annee = models.CharField(max_length=20, help_text='Ex: "2025"')
    titre = models.CharField(max_length=200)
    fichier = models.FileField(upload_to="annales/", blank=True, null=True)

    class Meta:
        ordering = ["-annee"]
        verbose_name = "Annale d'examen"
        verbose_name_plural = "Annales d'examen"

    def __str__(self):
        return f"{self.matiere} — {self.titre} ({self.annee})"


class DateExamen(models.Model):
    niveau = models.ForeignKey("academics.Niveau", on_delete=models.CASCADE, related_name="dates_examen")
    annee_scolaire = models.ForeignKey("academics.AnneeScolaire", on_delete=models.CASCADE, related_name="dates_examen")
    date_examen = models.DateField()

    class Meta:
        unique_together = ("niveau", "annee_scolaire")
        verbose_name = "Date d'examen"
        verbose_name_plural = "Dates d'examen"

    def __str__(self):
        return f"{self.niveau} — {self.date_examen}"


class ProgressionChapitre(models.Model):
    class Statut(models.TextChoices):
        A_FAIRE = "A_FAIRE", "À faire"
        EN_COURS = "EN_COURS", "En cours"
        MAITRISE = "MAITRISE", "Maîtrisé"

    eleve = models.ForeignKey("accounts.Eleve", on_delete=models.CASCADE, related_name="progressions_revision")
    chapitre = models.ForeignKey(ProgrammeChapitre, on_delete=models.CASCADE, related_name="progressions")
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.A_FAIRE)
    date_maj = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("eleve", "chapitre")

    def __str__(self):
        return f"{self.eleve} — {self.chapitre} : {self.get_statut_display()}"
