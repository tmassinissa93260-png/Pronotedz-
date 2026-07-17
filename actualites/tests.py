from django.core.management import call_command
from django.test import TestCase

from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Utilisateur

from .models import Publication


class PublicationVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        Publication.objects.create(titre="Note de service internes", contenu="...", audience=Publication.Audience.ENSEIGNANTS)

    def test_enseignants_only_publication_hidden_from_eleves(self):
        visibles = Publication.visibles_pour(Utilisateur.Role.ELEVE)
        self.assertFalse(visibles.filter(titre="Note de service internes").exists())

    def test_enseignants_only_publication_visible_to_enseignants(self):
        visibles = Publication.visibles_pour(Utilisateur.Role.ENSEIGNANT)
        self.assertTrue(visibles.filter(titre="Note de service internes").exists())

    def test_liste_view_loads_for_every_role(self):
        for username in ("admin.direction", "prof.mathématiques", "eleve.202600001", "parent.benali"):
            self.assertTrue(self.client.login(username=username, password=DEMO_PASSWORD))
            response = self.client.get("/actualites/")
            self.assertEqual(response.status_code, 200)
            self.client.logout()
