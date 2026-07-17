from django.db import models


class Publication(models.Model):
    class Audience(models.TextChoices):
        TOUS = "TOUS", "Tout l'établissement"
        ENSEIGNANTS = "ENSEIGNANTS", "Enseignants"
        ELEVES_PARENTS = "ELEVES_PARENTS", "Élèves et parents"

    titre = models.CharField(max_length=200)
    contenu = models.TextField()
    auteur = models.ForeignKey("accounts.Utilisateur", on_delete=models.SET_NULL, null=True, related_name="publications")
    audience = models.CharField(max_length=20, choices=Audience.choices, default=Audience.TOUS)
    epingle = models.BooleanField(default=False)
    date_publication = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-epingle", "-date_publication"]

    def __str__(self):
        return self.titre

    @staticmethod
    def visibles_pour(role):
        from accounts.models import Utilisateur

        if role == Utilisateur.Role.ADMIN:
            return Publication.objects.all()
        if role == Utilisateur.Role.ENSEIGNANT:
            return Publication.objects.filter(audience__in=[Publication.Audience.TOUS, Publication.Audience.ENSEIGNANTS])
        return Publication.objects.filter(audience__in=[Publication.Audience.TOUS, Publication.Audience.ELEVES_PARENTS])
