from django.contrib.auth.models import AbstractUser
from django.db import models


class Utilisateur(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administration"
        ENSEIGNANT = "ENSEIGNANT", "Enseignant"
        ELEVE = "ELEVE", "Élève"
        PARENT = "PARENT", "Parent"

    role = models.CharField(max_length=20, choices=Role.choices)
    telephone = models.CharField(max_length=20, blank=True)
    photo = models.ImageField(upload_to="photos/", blank=True, null=True)
    must_change_password = models.BooleanField(default=False)

    def __str__(self):
        return self.get_full_name() or self.username


class PersonnelAdministratif(models.Model):
    class Fonction(models.TextChoices):
        DIRECTEUR = "DIRECTEUR", "Directeur"
        CENSEUR = "CENSEUR", "Censeur"
        SURVEILLANT_GENERAL = "SURVEILLANT_GENERAL", "Surveillant Général"
        SECRETARIAT = "SECRETARIAT", "Secrétariat"

    user = models.OneToOneField(
        Utilisateur, on_delete=models.CASCADE, related_name="personnel_administratif"
    )
    fonction = models.CharField(max_length=30, choices=Fonction.choices)

    def __str__(self):
        return f"{self.user} ({self.get_fonction_display()})"


class Enseignant(models.Model):
    class Civilite(models.TextChoices):
        M = "M", "M."
        MME = "MME", "Mme"

    user = models.OneToOneField(
        Utilisateur, on_delete=models.CASCADE, related_name="enseignant"
    )
    matieres_enseignees = models.ManyToManyField(
        "academics.Matiere", related_name="enseignants", blank=True
    )
    civilite = models.CharField(max_length=3, choices=Civilite.choices, blank=True)
    date_embauche = models.DateField(null=True, blank=True)

    def __str__(self):
        return str(self.user)


class Eleve(models.Model):
    class Sexe(models.TextChoices):
        M = "M", "Masculin"
        F = "F", "Féminin"

    user = models.OneToOneField(
        Utilisateur, on_delete=models.CASCADE, related_name="eleve"
    )
    classe = models.ForeignKey(
        "academics.Classe", on_delete=models.PROTECT, related_name="eleves"
    )
    matricule = models.CharField(max_length=30, unique=True)
    date_naissance = models.DateField(null=True, blank=True)
    lieu_naissance = models.CharField(max_length=100, blank=True)
    sexe = models.CharField(max_length=1, choices=Sexe.choices, blank=True)
    date_inscription = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} ({self.matricule})"


class Parent(models.Model):
    user = models.OneToOneField(
        Utilisateur, on_delete=models.CASCADE, related_name="parent"
    )
    enfants = models.ManyToManyField(Eleve, related_name="parents", blank=True)

    def __str__(self):
        return str(self.user)
