from decimal import Decimal

from django.db import models
from django.utils import timezone


class QCM(models.Model):
    classe = models.ForeignKey("academics.Classe", on_delete=models.CASCADE, related_name="qcms")
    matiere = models.ForeignKey("academics.Matiere", on_delete=models.CASCADE, related_name="qcms")
    enseignant = models.ForeignKey("accounts.Enseignant", on_delete=models.CASCADE, related_name="qcms_crees")
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date_ouverture = models.DateTimeField(null=True, blank=True)
    date_limite = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "QCM"
        verbose_name_plural = "QCM"
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.titre} — {self.classe}"

    @property
    def est_ouvert(self):
        maintenant = timezone.now()
        if self.date_ouverture and maintenant < self.date_ouverture:
            return False
        if self.date_limite and maintenant > self.date_limite:
            return False
        return True

    @property
    def total_points(self):
        return sum((q.points for q in self.questions.all()), Decimal("0"))


class QuestionQCM(models.Model):
    qcm = models.ForeignKey(QCM, on_delete=models.CASCADE, related_name="questions")
    texte = models.CharField(max_length=500)
    ordre = models.PositiveSmallIntegerField(default=0)
    points = models.DecimalField(max_digits=4, decimal_places=1, default=1)

    class Meta:
        ordering = ["ordre"]

    def __str__(self):
        return self.texte


class ChoixQCM(models.Model):
    question = models.ForeignKey(QuestionQCM, on_delete=models.CASCADE, related_name="choix")
    texte = models.CharField(max_length=255)
    est_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.texte


class TentativeQCM(models.Model):
    qcm = models.ForeignKey(QCM, on_delete=models.CASCADE, related_name="tentatives")
    eleve = models.ForeignKey("accounts.Eleve", on_delete=models.CASCADE, related_name="tentatives_qcm")
    date_debut = models.DateTimeField(auto_now_add=True)
    date_soumission = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)

    class Meta:
        unique_together = ("qcm", "eleve")

    def __str__(self):
        return f"{self.eleve} — {self.qcm}"

    @property
    def est_soumise(self):
        return self.date_soumission is not None

    def corriger_et_soumettre(self, reponses_par_question):
        """reponses_par_question: {question_id: choix_id}. Computes the score
        from correct choices and marks the attempt as submitted."""
        score = Decimal("0")
        for question in self.qcm.questions.all():
            choix_id = reponses_par_question.get(question.pk)
            if not choix_id:
                continue
            choix = question.choix.filter(pk=choix_id).first()
            ReponseEleve.objects.update_or_create(tentative=self, question=question, defaults={"choix": choix})
            if choix and choix.est_correct:
                score += question.points
        self.score = score
        self.date_soumission = timezone.now()
        self.save()
        return score


class ReponseEleve(models.Model):
    tentative = models.ForeignKey(TentativeQCM, on_delete=models.CASCADE, related_name="reponses")
    question = models.ForeignKey(QuestionQCM, on_delete=models.CASCADE, related_name="reponses")
    choix = models.ForeignKey(ChoixQCM, on_delete=models.CASCADE, related_name="reponses")

    class Meta:
        unique_together = ("tentative", "question")

    def __str__(self):
        return f"{self.tentative} — {self.question}"
