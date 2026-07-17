from django.core.management import call_command
from django.test import TestCase

from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Eleve


class ParentScopingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_parent_cannot_view_other_parents_child_cahier(self):
        self.assertTrue(self.client.login(username="parent.hamdi", password=DEMO_PASSWORD))
        autre_enfant = Eleve.objects.get(matricule="202600001")

        response = self.client.get(f"/cahier-de-texte/?enfant={autre_enfant.pk}")
        self.assertEqual(response.status_code, 404)
