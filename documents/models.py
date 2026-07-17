from django.db import models


class Document(models.Model):
    class Categorie(models.TextChoices):
        REGLEMENT = "REGLEMENT", "Règlement intérieur"
        SUPPORT_COURS = "SUPPORT_COURS", "Support de cours"
        ADMINISTRATIF = "ADMINISTRATIF", "Administratif"
        AUTRE = "AUTRE", "Autre"

    titre = models.CharField(max_length=200)
    fichier = models.FileField(upload_to="documents/")
    description = models.CharField(max_length=255, blank=True)
    categorie = models.CharField(max_length=20, choices=Categorie.choices, default=Categorie.AUTRE)
    classe = models.ForeignKey(
        "academics.Classe", on_delete=models.CASCADE, null=True, blank=True, related_name="documents",
        help_text="Laisser vide pour un document visible par tout l'établissement.",
    )
    depose_par = models.ForeignKey("accounts.Utilisateur", on_delete=models.SET_NULL, null=True, related_name="documents_deposes")
    date_depot = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_depot"]

    def __str__(self):
        return self.titre
