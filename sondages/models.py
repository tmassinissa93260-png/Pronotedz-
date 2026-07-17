from django.db import models


class Sondage(models.Model):
    class Audience(models.TextChoices):
        TOUS = "TOUS", "Tout l'établissement"
        ENSEIGNANTS = "ENSEIGNANTS", "Enseignants"
        ELEVES = "ELEVES", "Élèves"
        PARENTS = "PARENTS", "Parents"

    etablissement = models.ForeignKey(
        "academics.Etablissement", on_delete=models.CASCADE, related_name="sondages", null=True, blank=True
    )
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    cree_par = models.ForeignKey("accounts.Utilisateur", on_delete=models.SET_NULL, null=True, related_name="sondages_crees")
    audience = models.CharField(max_length=15, choices=Audience.choices, default=Audience.TOUS)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_cloture = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-date_creation"]

    def __str__(self):
        return self.titre

    @property
    def est_ouvert(self):
        import datetime

        return self.date_cloture is None or self.date_cloture >= datetime.date.today()

    @staticmethod
    def visibles_pour(user):
        from accounts.models import Utilisateur

        audiences = [Sondage.Audience.TOUS]
        if user.role == Utilisateur.Role.ENSEIGNANT:
            audiences.append(Sondage.Audience.ENSEIGNANTS)
        elif user.role == Utilisateur.Role.ELEVE:
            audiences.append(Sondage.Audience.ELEVES)
        elif user.role == Utilisateur.Role.PARENT:
            audiences.append(Sondage.Audience.PARENTS)
        return Sondage.objects.filter(etablissement=user.etablissement, audience__in=audiences)


class QuestionSondage(models.Model):
    sondage = models.ForeignKey(Sondage, on_delete=models.CASCADE, related_name="questions")
    texte = models.CharField(max_length=255)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordre"]

    def __str__(self):
        return self.texte


class ChoixReponse(models.Model):
    question = models.ForeignKey(QuestionSondage, on_delete=models.CASCADE, related_name="choix")
    texte = models.CharField(max_length=150)

    def __str__(self):
        return self.texte


class ReponseUtilisateur(models.Model):
    question = models.ForeignKey(QuestionSondage, on_delete=models.CASCADE, related_name="reponses")
    utilisateur = models.ForeignKey("accounts.Utilisateur", on_delete=models.CASCADE, related_name="reponses_sondages")
    choix = models.ForeignKey(ChoixReponse, on_delete=models.CASCADE, related_name="reponses")
    date_reponse = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("question", "utilisateur")

    def __str__(self):
        return f"{self.utilisateur} — {self.question}: {self.choix}"
