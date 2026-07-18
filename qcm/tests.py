from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Eleve, Utilisateur

from .models import QCM, TentativeQCM
from .services import parse_questions
from .services_ia import generer_qcm_brut


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


def _fake_response(texte, input_tokens=50, output_tokens=200):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=texte)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


QCM_GENERE_VALIDE = (
    "Combien font 2+2 ?\n3\n*4\n5\n\n"
    "Capitale de l'Algérie ?\nOran\n*Alger\nConstantine"
)


class QCMGenerationIATests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_without_api_key_returns_graceful_error(self):
        etablissement = Utilisateur.objects.get(username="prof.mathématiques").etablissement
        with override_settings(ANTHROPIC_API_KEY=""):
            texte, erreur = generer_qcm_brut(etablissement, "Le théorème de Pythagore...")
        self.assertEqual(texte, "")
        self.assertIn("configuré", erreur)

    @override_settings(ANTHROPIC_API_KEY="fake-key-for-tests")
    @patch("assistant_ia.services._client")
    def test_successful_generation_returns_parseable_text(self, mock_client_factory):
        mock_client_factory.return_value.messages.create.return_value = _fake_response(QCM_GENERE_VALIDE)
        etablissement = Utilisateur.objects.get(username="prof.mathématiques").etablissement

        texte, erreur = generer_qcm_brut(etablissement, "Contenu du cours de maths...")

        self.assertIsNone(erreur)
        questions = parse_questions(texte)
        self.assertEqual(len(questions), 2)

    @override_settings(ANTHROPIC_API_KEY="fake-key-for-tests")
    @patch("assistant_ia.services._client")
    def test_generation_view_prefills_textarea_and_does_not_save_qcm(self, mock_client_factory):
        mock_client_factory.return_value.messages.create.return_value = _fake_response(QCM_GENERE_VALIDE)
        self.assertTrue(self.client.login(username="prof.mathématiques", password=DEMO_PASSWORD))

        nb_qcm_avant = QCM.objects.count()
        response = self.client.post("/qcm/nouveau/generer-ia/", {"contenu_cours": "Fonctions affines et linéaires"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alger")
        self.assertEqual(QCM.objects.count(), nb_qcm_avant)

    def test_non_teacher_cannot_access_generation_endpoint(self):
        self.assertTrue(self.client.login(username="eleve.202600001", password=DEMO_PASSWORD))
        response = self.client.post("/qcm/nouveau/generer-ia/", {"contenu_cours": "test"})
        self.assertEqual(response.status_code, 403)
