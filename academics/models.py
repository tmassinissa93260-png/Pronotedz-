from django.db import models
from django.utils.text import slugify


class Etablissement(models.Model):
    class TypeEtablissement(models.TextChoices):
        PRIMAIRE = "PRIMAIRE", "École primaire"
        COLLEGE = "COLLEGE", "Collège (CEM)"
        LYCEE = "LYCEE", "Lycée"

    nom = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True, help_text="Utilisé dans les URLs publiques (candidature, portail vitrine).")
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

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nom) or "etablissement"
            slug = base
            suffixe = 1
            while Etablissement.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                suffixe += 1
                slug = f"{base}-{suffixe}"
            self.slug = slug
        super().save(*args, **kwargs)


class AnneeScolaire(models.Model):
    etablissement = models.ForeignKey(
        Etablissement, on_delete=models.CASCADE, related_name="annees_scolaires", null=True, blank=True
    )
    libelle = models.CharField(max_length=20, help_text='Ex: "2025-2026"')
    date_debut = models.DateField()
    date_fin = models.DateField()
    est_active = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Année scolaire"
        verbose_name_plural = "Années scolaires"
        ordering = ["-date_debut"]
        unique_together = ("etablissement", "libelle")

    def __str__(self):
        return self.libelle

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.est_active:
            AnneeScolaire.objects.filter(etablissement=self.etablissement).exclude(pk=self.pk).update(est_active=False)


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
        PRIMAIRE = "PRIMAIRE", "Primaire"
        MOYEN = "MOYEN", "Moyen"
        SECONDAIRE = "SECONDAIRE", "Secondaire"

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
    etablissement = models.ForeignKey(
        Etablissement, on_delete=models.CASCADE, related_name="salles", null=True, blank=True
    )
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
