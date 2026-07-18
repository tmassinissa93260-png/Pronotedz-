from django.db import models


class Evaluation(models.Model):
    class TypeEvaluation(models.TextChoices):
        DEVOIR = "DEVOIR", "Devoir"
        INTERROGATION = "INTERROGATION", "Interrogation"
        COMPOSITION = "COMPOSITION", "Composition"

    classe = models.ForeignKey("academics.Classe", on_delete=models.CASCADE, related_name="evaluations")
    matiere = models.ForeignKey("academics.Matiere", on_delete=models.CASCADE, related_name="evaluations")
    enseignant = models.ForeignKey("accounts.Enseignant", on_delete=models.CASCADE, related_name="evaluations")
    trimestre = models.ForeignKey("academics.Trimestre", on_delete=models.CASCADE, related_name="evaluations")
    titre = models.CharField(max_length=150)
    type_evaluation = models.CharField(max_length=15, choices=TypeEvaluation.choices, default=TypeEvaluation.DEVOIR)
    coefficient_evaluation = models.DecimalField(max_digits=4, decimal_places=1, default=1)
    date_evaluation = models.DateField()
    bareme = models.DecimalField(max_digits=4, decimal_places=1, default=20)
    publie = models.BooleanField(default=True, help_text="Si décoché, les notes restent invisibles aux élèves/parents (publication différée)")

    class Meta:
        ordering = ["-date_evaluation"]

    def __str__(self):
        return f"{self.titre} — {self.matiere} — {self.classe}"


class Note(models.Model):
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name="notes")
    eleve = models.ForeignKey("accounts.Eleve", on_delete=models.CASCADE, related_name="notes")
    valeur = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="Vide = absent / non noté")
    commentaire = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ("evaluation", "eleve")

    def __str__(self):
        return f"{self.eleve} — {self.evaluation}: {self.valeur}"


class AppreciationMatiere(models.Model):
    eleve = models.ForeignKey("accounts.Eleve", on_delete=models.CASCADE, related_name="appreciations_matiere")
    matiere = models.ForeignKey("academics.Matiere", on_delete=models.CASCADE, related_name="appreciations")
    trimestre = models.ForeignKey("academics.Trimestre", on_delete=models.CASCADE, related_name="appreciations_matiere")
    enseignant = models.ForeignKey("accounts.Enseignant", on_delete=models.SET_NULL, null=True, related_name="appreciations_donnees")
    texte = models.TextField(blank=True)

    class Meta:
        unique_together = ("eleve", "matiere", "trimestre")

    def __str__(self):
        return f"{self.eleve} — {self.matiere} — {self.trimestre}"


class AppreciationGenerale(models.Model):
    eleve = models.ForeignKey("accounts.Eleve", on_delete=models.CASCADE, related_name="appreciations_generales")
    trimestre = models.ForeignKey("academics.Trimestre", on_delete=models.CASCADE, related_name="appreciations_generales")
    texte = models.TextField(blank=True)
    redigee_par = models.ForeignKey("accounts.Enseignant", on_delete=models.SET_NULL, null=True, related_name="appreciations_generales_redigees")

    class Meta:
        unique_together = ("eleve", "trimestre")

    def __str__(self):
        return f"{self.eleve} — {self.trimestre}"
