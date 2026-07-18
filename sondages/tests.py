from django.core.management import call_command
from django.test import TestCase

from accounts.management.commands.seed_demo import DEMO_PASSWORD

from .models import ReponseUtilisateur, Sondage


class SondageVoteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_user_can_vote_once(self):
        self.assertTrue(self.client.login(username="eleve.202600001", password=DEMO_PASSWORD))
        sondage = Sondage.objects.get(titre="Satisfaction cantine scolaire")
        question = sondage.questions.first()
        choix = question.choix.first()

        response = self.client.post(f"/sondages/{sondage.pk}/", {f"question_{question.pk}": choix.pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ReponseUtilisateur.objects.filter(question=question, utilisateur__username="eleve.202600001").count(), 1)

    def test_voting_twice_does_not_create_a_second_response(self):
        self.assertTrue(self.client.login(username="eleve.202600001", password=DEMO_PASSWORD))
        sondage = Sondage.objects.get(titre="Satisfaction cantine scolaire")
        question = sondage.questions.first()
        choix_1, choix_2 = list(question.choix.all())[:2]

        self.client.post(f"/sondages/{sondage.pk}/", {f"question_{question.pk}": choix_1.pk})
        self.client.post(f"/sondages/{sondage.pk}/", {f"question_{question.pk}": choix_2.pk})

        self.assertEqual(ReponseUtilisateur.objects.filter(question=question, utilisateur__username="eleve.202600001").count(), 1)

    def test_results_shown_after_voting(self):
        self.assertTrue(self.client.login(username="eleve.202600001", password=DEMO_PASSWORD))
        sondage = Sondage.objects.get(titre="Satisfaction cantine scolaire")
        question = sondage.questions.first()
        choix = question.choix.first()
        self.client.post(f"/sondages/{sondage.pk}/", {f"question_{question.pk}": choix.pk})

        response = self.client.get(f"/sondages/{sondage.pk}/")
        self.assertContains(response, "vote")

    def test_sondage_not_visible_to_another_etablissement(self):
        sondage = Sondage.objects.get(titre="Satisfaction cantine scolaire")
        self.assertTrue(self.client.login(username="admin.oran", password=DEMO_PASSWORD))

        response = self.client.get("/sondages/")
        self.assertNotContains(response, "Satisfaction cantine scolaire")

        response = self.client.get(f"/sondages/{sondage.pk}/")
        self.assertEqual(response.status_code, 404)
