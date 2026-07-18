import secrets

from django.db import models


def _generer_reference():
    return f"CAND-{secrets.token_hex(4).upper()}"


class Candidature(models.Model):
    class Statut(models.TextChoices):
        RECU = "RECU", "Reçue"
        EN_EXAMEN = "EN_EXAMEN", "En cours d'examen"
        ACCEPTE = "ACCEPTE", "Acceptée"
        REFUSE = "REFUSE", "Refusée"
        LISTE_ATTENTE = "LISTE_ATTENTE", "Liste d'attente"

    class Sexe(models.TextChoices):
        M = "M", "Masculin"
        F = "F", "Féminin"

    etablissement = models.ForeignKey("academics.Etablissement", on_delete=models.CASCADE, related_name="candidatures")
    reference = models.CharField(max_length=20, unique=True, default=_generer_reference, editable=False)

    niveau_souhaite = models.ForeignKey("academics.Niveau", on_delete=models.PROTECT, related_name="candidatures")
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    date_naissance = models.DateField(null=True, blank=True)
    sexe = models.CharField(max_length=1, choices=Sexe.choices, blank=True)

    nom_parent = models.CharField(max_length=150)
    telephone_parent = models.CharField(max_length=20)
    email_parent = models.EmailField()
    adresse = models.CharField(max_length=255, blank=True)

    bulletin_precedent = models.FileField(upload_to="admissions/bulletins/", blank=True, null=True)
    acte_naissance = models.FileField(upload_to="admissions/actes_naissance/", blank=True, null=True)
    photo = models.ImageField(upload_to="admissions/photos/", blank=True, null=True)

    statut = models.CharField(max_length=15, choices=Statut.choices, default=Statut.RECU)
    notes_admin = models.TextField(blank=True, help_text="Notes internes, jamais visibles par la famille.")
    date_soumission = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)
    traite_par = models.ForeignKey(
        "accounts.Utilisateur", on_delete=models.SET_NULL, null=True, blank=True, related_name="candidatures_traitees"
    )
    eleve_cree = models.OneToOneField(
        "accounts.Eleve", on_delete=models.SET_NULL, null=True, blank=True, related_name="candidature_origine"
    )

    class Meta:
        ordering = ["-date_soumission"]
        verbose_name = "Candidature"
        verbose_name_plural = "Candidatures"

    def __str__(self):
        return f"{self.reference} — {self.prenom} {self.nom}"

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}"
