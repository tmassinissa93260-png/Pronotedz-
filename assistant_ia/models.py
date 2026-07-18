import datetime

from django.db import models


def _mois_courant():
    return datetime.date.today().strftime("%Y-%m")


class BudgetIA(models.Model):
    etablissement = models.OneToOneField("academics.Etablissement", on_delete=models.CASCADE, related_name="budget_ia")
    plafond_mensuel_tokens = models.PositiveIntegerField(
        default=200_000, help_text="Nombre maximum de tokens IA consommés par mois pour cet établissement."
    )
    tokens_utilises = models.PositiveIntegerField(default=0)
    mois_courant = models.CharField(max_length=7, default=_mois_courant, help_text='Format "YYYY-MM".')

    class Meta:
        verbose_name = "Budget IA"
        verbose_name_plural = "Budgets IA"

    def __str__(self):
        return f"{self.etablissement} — {self.tokens_utilises}/{self.plafond_mensuel_tokens} ({self.mois_courant})"

    def _reset_si_nouveau_mois(self):
        mois = _mois_courant()
        if self.mois_courant != mois:
            self.mois_courant = mois
            self.tokens_utilises = 0

    def tokens_restants(self):
        self._reset_si_nouveau_mois()
        return max(0, self.plafond_mensuel_tokens - self.tokens_utilises)

    def peut_consommer(self):
        return self.tokens_restants() > 0

    def consommer(self, tokens):
        self._reset_si_nouveau_mois()
        self.tokens_utilises += tokens
        self.save(update_fields=["tokens_utilises", "mois_courant"])


class Conversation(models.Model):
    eleve = models.ForeignKey("accounts.Eleve", on_delete=models.CASCADE, related_name="conversations_ia")
    titre = models.CharField(max_length=150, default="Nouvelle conversation")
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.titre} — {self.eleve}"


class MessageConversation(models.Model):
    class Role(models.TextChoices):
        UTILISATEUR = "UTILISATEUR", "Élève"
        ASSISTANT = "ASSISTANT", "Assistant"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=15, choices=Role.choices)
    contenu = models.TextField()
    date_creation = models.DateTimeField(auto_now_add=True)
    tokens_utilises = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["date_creation"]

    def __str__(self):
        return f"{self.get_role_display()} — {self.contenu[:40]}"
