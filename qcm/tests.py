from django.core.management import call_command
from django.test import TestCase

from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Eleve

from .models import QCM, TentativeQCM
from .services import parse_questions


class ParseQuestionsTests(TestCase):
    def test_parses_multiple_questions_and_marks_correct_choice(self):
        texte = (
            "Combien font 2+2 ?\n3\n* 4\n5\n\n"
            "Capitale de l'Algérie ?\nOran\n* Alger\nConstantine"
        )
        questions = parse_questions(texte)

        self.assertEqual(len(questions), 2)
        titre1, choix1 = questions[0]
        self.assertEqual(titre1, "Combien font 2+2 ?")
        self.assertEqual(choix1, [("3", False), ("4", True), ("5", False)])

    def test_ignores_blocks_without_choices(self):
        questions = parse_questions("Juste une question sans choix")
        self.assertEqual(questions, [])


class AutoCorrectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_score_computed_from_correct_choices_only(self):
        qcm = QCM.objects.get(titre="Quiz de révision — Fonctions")
        eleve = Eleve.objects.get(matricule="202600001")
        tentative = TentativeQCM.objects.create(qcm=qcm, eleve=eleve)

        q1, q2 = qcm.questions.order_by("ordre")
        bonne_reponse_q1 = q1.choix.get(est_correct=True)
        mauvaise_reponse_q2 = q2.choix.filter(est_correct=False).first()

        score = tentative.corriger_et_soumettre({q1.pk: bonne_reponse_q1.pk, q2.pk: mauvaise_reponse_q2.pk})

        self.assertEqual(score, q1.points)  # only q1 was correct
        self.assertTrue(tentative.est_soumise)


class QCMScopingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_student_of_another_classe_cannot_access_qcm(self):
        qcm = QCM.objects.get(titre="Quiz de révision — Fonctions")  # scoped to 1AS Sciences 1
        self.assertTrue(self.client.login(username="eleve.202600007", password=DEMO_PASSWORD))  # 1AS Lettres 1

        response = self.client.get(f"/qcm/{qcm.pk}/passer/")
        self.assertEqual(response.status_code, 404)

    def test_teacher_cannot_view_results_of_a_qcm_not_theirs(self):
        qcm = QCM.objects.get(titre="Quiz de révision — Fonctions")  # created by prof.mathématiques
        self.client.login(username="prof.arabe", password=DEMO_PASSWORD)

        response = self.client.get(f"/qcm/{qcm.pk}/resultats/")
        self.assertEqual(response.status_code, 404)

    def test_student_can_take_qcm_end_to_end(self):
        qcm = QCM.objects.get(titre="Quiz de révision — Fonctions")
        self.assertTrue(self.client.login(username="eleve.202600001", password=DEMO_PASSWORD))

        q1, q2 = qcm.questions.order_by("ordre")
        data = {
            f"question_{q1.pk}": q1.choix.get(est_correct=True).pk,
            f"question_{q2.pk}": q2.choix.get(est_correct=True).pk,
        }
        response = self.client.post(f"/qcm/{qcm.pk}/passer/", data)
        self.assertEqual(response.status_code, 302)

        tentative = TentativeQCM.objects.get(qcm=qcm, eleve__matricule="202600001")
        self.assertEqual(tentative.score, qcm.total_points)
