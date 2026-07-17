import datetime
from decimal import Decimal

from django.test import TestCase

from academics.models import AnneeScolaire, Classe, CoefficientMatiere, Matiere, Niveau, Trimestre
from accounts.models import Eleve, Enseignant, Utilisateur

from .models import Evaluation, Note
from .services import moyenne_generale, moyenne_matiere


class MoyenneCalculationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        annee = AnneeScolaire.objects.create(libelle="2025-2026", date_debut=datetime.date(2025, 9, 1), date_fin=datetime.date(2026, 6, 30))
        cls.trimestre = Trimestre.objects.create(annee_scolaire=annee, numero=1, date_debut=datetime.date(2025, 9, 1), date_fin=datetime.date(2025, 12, 19))
        niveau = Niveau.objects.create(libelle="1AS", cycle=Niveau.Cycle.LYCEE, ordre=1)
        cls.classe = Classe.objects.create(libelle="Test Classe", niveau=niveau, annee_scolaire=annee)

        cls.maths = Matiere.objects.create(nom="Mathématiques")
        cls.francais = Matiere.objects.create(nom="Français")
        CoefficientMatiere.objects.create(matiere=cls.maths, niveau=niveau, coefficient=Decimal("4"))
        CoefficientMatiere.objects.create(matiere=cls.francais, niveau=niveau, coefficient=Decimal("2"))

        prof_user = Utilisateur.objects.create_user(username="prof.test", role=Utilisateur.Role.ENSEIGNANT)
        cls.enseignant = Enseignant.objects.create(user=prof_user)

        eleve_user = Utilisateur.objects.create_user(username="eleve.test", role=Utilisateur.Role.ELEVE)
        cls.eleve = Eleve.objects.create(user=eleve_user, classe=cls.classe, matricule="T001")

    def _make_evaluation(self, matiere, titre, coefficient=1, bareme=20):
        return Evaluation.objects.create(
            classe=self.classe, matiere=matiere, enseignant=self.enseignant, trimestre=self.trimestre,
            titre=titre, coefficient_evaluation=coefficient, bareme=bareme, date_evaluation=datetime.date(2025, 10, 1),
        )

    def test_moyenne_matiere_is_weighted_by_evaluation_coefficient(self):
        eval1 = self._make_evaluation(self.maths, "Devoir 1", coefficient=1)
        eval2 = self._make_evaluation(self.maths, "Devoir 2", coefficient=2)
        Note.objects.create(evaluation=eval1, eleve=self.eleve, valeur=Decimal("10"))
        Note.objects.create(evaluation=eval2, eleve=self.eleve, valeur=Decimal("16"))

        # (10*1 + 16*2) / (1+2) = 14
        self.assertEqual(moyenne_matiere(self.eleve, self.maths, self.trimestre), Decimal("14.00"))

    def test_moyenne_matiere_excludes_absent_notes(self):
        eval1 = self._make_evaluation(self.maths, "Devoir 1", coefficient=1)
        eval_absent = self._make_evaluation(self.maths, "Devoir manqué", coefficient=5)
        Note.objects.create(evaluation=eval1, eleve=self.eleve, valeur=Decimal("14"))
        Note.objects.create(evaluation=eval_absent, eleve=self.eleve, valeur=None)

        # The high-coefficient absent note must not drag the average down.
        self.assertEqual(moyenne_matiere(self.eleve, self.maths, self.trimestre), Decimal("14.00"))

    def test_moyenne_matiere_scales_non_20_bareme(self):
        evaluation = self._make_evaluation(self.maths, "Devoir sur 10", coefficient=1, bareme=10)
        Note.objects.create(evaluation=evaluation, eleve=self.eleve, valeur=Decimal("8"))

        # 8/10 scaled to /20 = 16
        self.assertEqual(moyenne_matiere(self.eleve, self.maths, self.trimestre), Decimal("16.00"))

    def test_moyenne_generale_is_weighted_by_coefficient_matiere(self):
        eval_maths = self._make_evaluation(self.maths, "Devoir", coefficient=1)
        eval_francais = self._make_evaluation(self.francais, "Devoir", coefficient=1)
        Note.objects.create(evaluation=eval_maths, eleve=self.eleve, valeur=Decimal("14"))
        Note.objects.create(evaluation=eval_francais, eleve=self.eleve, valeur=Decimal("8"))

        # (14*4 + 8*2) / (4+2) = 12
        self.assertEqual(moyenne_generale(self.eleve, self.trimestre), Decimal("12.00"))

    def test_moyenne_matiere_returns_none_without_notes(self):
        self.assertIsNone(moyenne_matiere(self.eleve, self.maths, self.trimestre))


class BulletinScopingTests(TestCase):
    """A parent must never be able to view another family's child's bulletin via URL manipulation."""

    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command

        call_command("seed_demo")

    def test_parent_cannot_view_other_parents_child_bulletin(self):
        from accounts.management.commands.seed_demo import DEMO_PASSWORD

        self.assertTrue(self.client.login(username="parent.hamdi", password=DEMO_PASSWORD))
        autre_enfant = Eleve.objects.get(matricule="202600001")

        response = self.client.get(f"/notes/bulletin/?enfant={autre_enfant.pk}")
        self.assertEqual(response.status_code, 404)
