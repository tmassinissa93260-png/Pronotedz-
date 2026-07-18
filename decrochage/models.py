from django.db import models


class AlerteDecrochage(models.Model):
    class Statut(models.TextChoices):
        NOUVELLE = "NOUVELLE", "Nouvelle"
        EN_COURS = "EN_COURS", "Prise en charge"
        RESOLUE = "RESOLUE", "Résolue"

    eleve = models.ForeignKey("accounts.Eleve", on_delete=models.CASCADE, related_name="alertes_decrochage")
    score_risque = models.PositiveSmallIntegerField()
    signaux = models.JSONField(default=list, help_text="Liste des signaux détectés : [{type, description}].")
    date_detection = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.NOUVELLE)
    notes_suivi = models.TextField(blank=True)
    traite_par = models.ForeignKey(
        "accounts.Utilisateur", on_delete=models.SET_NULL, null=True, blank=True, related_name="alertes_traitees"
    )

    class Meta:
        ordering = ["-score_risque", "-date_detection"]
        verbose_name = "Alerte de décrochage"
        verbose_name_plural = "Alertes de décrochage"

    def __str__(self):
        return f"{self.eleve} — risque {self.score_risque} ({self.get_statut_display()})"
