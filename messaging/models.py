from django.db import models


class Conversation(models.Model):
    sujet = models.CharField(max_length=200)
    createur = models.ForeignKey("accounts.Utilisateur", on_delete=models.CASCADE, related_name="conversations_creees")
    participants = models.ManyToManyField("accounts.Utilisateur", related_name="conversations")
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]

    def __str__(self):
        return self.sujet


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    expediteur = models.ForeignKey("accounts.Utilisateur", on_delete=models.CASCADE, related_name="messages_envoyes")
    contenu = models.TextField()
    date_envoi = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date_envoi"]

    def __str__(self):
        return f"{self.expediteur} — {self.date_envoi:%d/%m/%Y %H:%M}"
