from django.core.management import call_command
from django.test import TestCase

from accounts.management.commands.seed_demo import DEMO_PASSWORD

from .models import Document


class DocumentVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_eleve_sees_etablissement_wide_document(self):
        self.assertTrue(self.client.login(username="eleve.202600007", password=DEMO_PASSWORD))  # 1AS Lettres 1
        response = self.client.get("/documents/")
        self.assertContains(response, "Règlement intérieur")

    def test_eleve_does_not_see_document_scoped_to_another_classe(self):
        # "Support de cours - Fonctions" is scoped to classe_sciences; 202600007 is in classe_lettres.
        self.assertTrue(self.client.login(username="eleve.202600007", password=DEMO_PASSWORD))
        response = self.client.get("/documents/")
        self.assertNotContains(response, "Support de cours - Fonctions")

    def test_eleve_of_the_target_classe_does_see_the_document(self):
        self.assertTrue(self.client.login(username="eleve.202600001", password=DEMO_PASSWORD))  # 1AS Sciences 1
        response = self.client.get("/documents/")
        self.assertContains(response, "Support de cours - Fonctions")

    def test_admin_of_another_etablissement_does_not_see_etablissement_wide_document(self):
        self.assertTrue(self.client.login(username="admin.oran", password=DEMO_PASSWORD))
        response = self.client.get("/documents/")
        self.assertNotContains(response, "Règlement intérieur")
