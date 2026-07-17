from django.db import models


class Etablissement(models.Model):
    class TypeEtablissement(models.TextChoices):
        COLLEGE = "COLLEGE", "Collège"
        LYCEE = "LYCEE", "Lycée"

    nom = models.CharField(max_length=200)
    code = models.CharField(max_length=30, blank=True)
    adresse = models.CharField(max_length=255, blank=True)
    wilaya = models.CharField(max_length=100, blank=True)
    commune = models.CharField(max_length=100, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to="etablissement/", blank=True, null=True)
    type_etablissement = models.CharField(
        max_length=10, choices=TypeEtablissement.choices, default=TypeEtablissement.LYCEE
    )
    annee_scolaire_courante = models.ForeignKey(
        "AnneeScolaire", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        verbose_name = "Établissement"

    def __str__(self):
        return self.nom

    @classmethod
    def get_solo(cls):
        return cls.objects.first()


class AnneeScolaire(models.Model):
    libelle = models.CharField(max_length=20, unique=True, help_text='Ex: "2025-2026"')
    date_debut = models.DateField()
    date_fin = models.DateField()
    est_active = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Année scolaire"
        verbose_name_plural = "Années scolaires"
        ordering = ["-date_debut"]

    def __str__(self):
        return self.libelle

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.est_active:
            AnneeScolaire.objects.exclude(pk=self.pk).update(est_active=False)


class Trimestre(models.Model):
    annee_scolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.CASCADE, related_name="trimestres"
    )
    numero = models.PositiveSmallIntegerField(choices=[(1, "1er trimestre"), (2, "2e trimestre"), (3, "3e trimestre")])
    date_debut = models.DateField()
    date_fin = models.DateField()
    est_actif = models.BooleanField(default=False)

    class Meta:
        unique_together = ("annee_scolaire", "numero")
        ordering = ["annee_scolaire", "numero"]

    def __str__(self):
        return f"{self.get_numero_display()} ({self.annee_scolaire})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.est_actif:
            Trimestre.objects.filter(annee_scolaire=self.annee_scolaire).exclude(pk=self.pk).update(est_actif=False)


class Niveau(models.Model):
    class Cycle(models.TextChoices):
        COLLEGE = "COLLEGE", "Collège"
        LYCEE = "LYCEE", "Lycée"

    libelle = models.CharField(max_length=50, help_text='Ex: "1AS", "4AM"')
    cycle = models.CharField(max_length=10, choices=Cycle.choices)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordre"]

    def __str__(self):
        return self.libelle


class Filiere(models.Model):
    libelle = models.CharField(max_length=100, help_text='Ex: "Sciences", "Lettres et Philosophie"')

    def __str__(self):
        return self.libelle


class Matiere(models.Model):
    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True)
    couleur = models.CharField(max_length=7, default="#b8b0e8", help_text="Couleur hex pour l'emploi du temps")

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class CoefficientMatiere(models.Model):
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name="coefficients")
    niveau = models.ForeignKey(Niveau, on_delete=models.CASCADE, related_name="coefficients_matieres")
    filiere = models.ForeignKey(Filiere, on_delete=models.CASCADE, null=True, blank=True, related_name="coefficients_matieres")
    coefficient = models.DecimalField(max_digits=4, decimal_places=1)

    class Meta:
        unique_together = ("matiere", "niveau", "filiere")
        verbose_name = "Coefficient de matière"
        verbose_name_plural = "Coefficients de matière"

    def __str__(self):
        return f"{self.matiere} — {self.niveau} : {self.coefficient}"


class Salle(models.Model):
    nom = models.CharField(max_length=50)
    capacite = models.PositiveSmallIntegerField(null=True, blank=True)
    type_salle = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.nom


class Classe(models.Model):
    niveau = models.ForeignKey(Niveau, on_delete=models.PROTECT, related_name="classes")
    filiere = models.ForeignKey(Filiere, on_delete=models.SET_NULL, null=True, blank=True, related_name="classes")
    libelle = models.CharField(max_length=50, help_text='Ex: "1AS Sciences 2"')
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name="classes")
    professeur_principal = models.ForeignKey(
        "accounts.Enseignant", on_delete=models.SET_NULL, null=True, blank=True, related_name="classes_principal"
    )
    effectif_max = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["niveau__ordre", "libelle"]
        unique_together = ("libelle", "annee_scolaire")

    def __str__(self):
        return f"{self.libelle} ({self.annee_scolaire})"

    def coefficient_pour(self, matiere):
        qs = CoefficientMatiere.objects.filter(matiere=matiere, niveau=self.niveau)
        specifique = qs.filter(filiere=self.filiere).first() if self.filiere_id else None
        return specifique or qs.filter(filiere__isnull=True).first()
