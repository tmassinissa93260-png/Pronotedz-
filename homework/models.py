from django.db import models


class CahierDeTexte(models.Model):
    seance = models.OneToOneField("attendance.Seance", on_delete=models.CASCADE, related_name="cahier_de_texte")
    contenu = models.TextField()
    saisi_par = models.ForeignKey("accounts.Utilisateur", on_delete=models.SET_NULL, null=True, related_name="cahiers_saisis")
    date_saisie = models.DateTimeField(auto_now_add=True)
    visible_eleves = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Cahier de texte"
        verbose_name_plural = "Cahier de texte"

    def __str__(self):
        return f"Cahier — {self.seance}"


class Devoir(models.Model):
    seance_donnee = models.ForeignKey("attendance.Seance", on_delete=models.CASCADE, related_name="devoirs_donnes")
    classe = models.ForeignKey("academics.Classe", on_delete=models.CASCADE, related_name="devoirs")
    matiere = models.ForeignKey("academics.Matiere", on_delete=models.CASCADE, related_name="devoirs")
    enseignant = models.ForeignKey("accounts.Enseignant", on_delete=models.CASCADE, related_name="devoirs_donnes")
    date_a_faire_pour = models.DateField()
    consigne = models.TextField()
    piece_jointe = models.FileField(upload_to="devoirs/", blank=True, null=True)

    class Meta:
        ordering = ["date_a_faire_pour"]

    def __str__(self):
        return f"{self.matiere} — {self.classe} — pour le {self.date_a_faire_pour}"

    @property
    def est_ouvert(self):
        import datetime

        return datetime.date.today() <= self.date_a_faire_pour


class RenduDevoir(models.Model):
    devoir = models.ForeignKey(Devoir, on_delete=models.CASCADE, related_name="rendus")
    eleve = models.ForeignKey("accounts.Eleve", on_delete=models.CASCADE, related_name="devoirs_rendus")
    fichier = models.FileField(upload_to="rendus_devoirs/")
    date_soumission = models.DateTimeField(auto_now_add=True)
    note_sur_20 = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    commentaire_correction = models.TextField(blank=True)
    corrige_par = models.ForeignKey("accounts.Utilisateur", on_delete=models.SET_NULL, null=True, blank=True, related_name="rendus_corriges")
    corrige_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Devoir rendu"
        verbose_name_plural = "Devoirs rendus"
        unique_together = ("devoir", "eleve")
        ordering = ["-date_soumission"]

    def __str__(self):
        return f"{self.eleve} — {self.devoir}"

    @property
    def est_corrige(self):
        return self.corrige_le is not None
