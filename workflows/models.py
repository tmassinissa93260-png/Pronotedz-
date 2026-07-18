from django.db import models


class WorkflowRegle(models.Model):
    class Declencheur(models.TextChoices):
        NOTE_BASSE = "NOTE_BASSE", "Note en dessous d'un seuil"
        RETARDS_FREQUENTS = "RETARDS_FREQUENTS", "Retards fréquents"
        DEVOIR_NON_RENDU = "DEVOIR_NON_RENDU", "Devoir non rendu après échéance"

    class Destinataire(models.TextChoices):
        PARENT = "PARENT", "Parent(s) de l'élève"
        PROF_PRINCIPAL = "PROF_PRINCIPAL", "Professeur principal"

    etablissement = models.ForeignKey(
        "academics.Etablissement", on_delete=models.CASCADE, related_name="regles_workflow"
    )
    nom = models.CharField(max_length=150)
    declencheur = models.CharField(max_length=20, choices=Declencheur.choices)
    seuil = models.DecimalField(
        max_digits=5, decimal_places=1,
        help_text="Note seuil sur 20 (NOTE_BASSE), nombre de retards (RETARDS_FREQUENTS) ou jours de "
        "retard (DEVOIR_NON_RENDU), selon le déclencheur.",
    )
    destinataire = models.CharField(max_length=15, choices=Destinataire.choices, default=Destinataire.PARENT)
    message = models.TextField(
        default="Une règle automatique (\"{regle}\") a été déclenchée pour {eleve}.",
        help_text="Variables disponibles : {regle}, {eleve}, {seuil}, et selon le déclencheur "
        "{matiere}/{valeur} (NOTE_BASSE), {nb_retards} (RETARDS_FREQUENTS), {devoir} (DEVOIR_NON_RENDU).",
    )
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Règle de workflow"
        verbose_name_plural = "Règles de workflow"

    def __str__(self):
        return f"{self.nom} ({self.get_declencheur_display()})"


class WorkflowExecution(models.Model):
    """Records that a rule already fired for a given élève + underlying
    event, so re-running the périodic command doesn't re-notify endlessly
    for the same évaluation/devoir/semaine de retards."""

    regle = models.ForeignKey(WorkflowRegle, on_delete=models.CASCADE, related_name="executions")
    eleve = models.ForeignKey("accounts.Eleve", on_delete=models.CASCADE, related_name="executions_workflow")
    cle_unicite = models.CharField(max_length=100)
    date_execution = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Exécution de règle"
        verbose_name_plural = "Exécutions de règles"
        unique_together = ("regle", "eleve", "cle_unicite")
        ordering = ["-date_execution"]

    def __str__(self):
        return f"{self.regle} — {self.eleve}"
