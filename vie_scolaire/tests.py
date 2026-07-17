from django.core.management import call_command
from django.test import TestCase

from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Eleve


class ObservationScopingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_parent_cannot_view_other_parents_child_observations(self):
        self.assertTrue(self.client.login(username="parent.hamdi", password=DEMO_PASSWORD))
        autre_enfant = Eleve.objects.get(matricule="202600003")  # not a child of parent.hamdi

        response = self.client.get(f"/vie-scolaire/mes-observations/?enfant={autre_enfant.pk}")
        self.assertEqual(response.status_code, 404)

    def test_teacher_sees_observation_for_a_class_they_teach(self):
        self.assertTrue(self.client.login(username="prof.mathématiques", password=DEMO_PASSWORD))
        response = self.client.get("/vie-scolaire/")
        self.assertContains(response, "Excellent travail")

    def test_admin_creer_form_only_lists_classes_of_their_own_etablissement(self):
        self.assertTrue(self.client.login(username="admin.oran", password=DEMO_PASSWORD))
        response = self.client.get("/vie-scolaire/nouvelle/")
        classes = list(response.context["classes"])
        self.assertEqual([c.libelle for c in classes], ["1AM 1"])
