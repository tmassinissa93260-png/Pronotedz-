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

    def destinataires(self):
        """Utilisateur queryset matching this publication's target audience."""
        from accounts.models import Utilisateur

        if self.audience == self.Audience.ENSEIGNANTS:
            return Utilisateur.objects.filter(role=Utilisateur.Role.ENSEIGNANT)
        if self.audience == self.Audience.ELEVES_PARENTS:
            return Utilisateur.objects.filter(role__in=[Utilisateur.Role.ELEVE, Utilisateur.Role.PARENT])
        return Utilisateur.objects.exclude(pk=self.auteur_id)


class LectureAccusee(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name="accuses_lecture")
    utilisateur = models.ForeignKey("accounts.Utilisateur", on_delete=models.CASCADE, related_name="publications_lues")
    date_lecture = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("publication", "utilisateur")

    def __str__(self):
        return f"{self.utilisateur} — {self.publication}"
