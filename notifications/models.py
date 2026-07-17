from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        ABSENCE = "ABSENCE", "Absence"
        NOTE = "NOTE", "Note publiée"
        MESSAGE = "MESSAGE", "Message reçu"
        INFO = "INFO", "Information établissement"
        AUTRE = "AUTRE", "Autre"

    destinataire = models.ForeignKey("accounts.Utilisateur", on_delete=models.CASCADE, related_name="notifications")
    type_notification = models.CharField(max_length=10, choices=Type.choices, default=Type.AUTRE)
    titre = models.CharField(max_length=200)
    contenu = models.TextField(blank=True)
    lien = models.CharField(max_length=255, blank=True, help_text="URL relative vers laquelle rediriger au clic")
    lu = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.destinataire} — {self.titre}"
