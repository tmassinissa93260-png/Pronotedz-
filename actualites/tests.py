from django.core.management import call_command
from django.test import TestCase

from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Utilisateur

from .models import LectureAccusee, Publication


class PublicationVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        admin = Utilisateur.objects.get(username="admin.direction")
        Publication.objects.create(
            titre="Note de service internes", contenu="...", audience=Publication.Audience.ENSEIGNANTS,
            etablissement=admin.etablissement,
        )

    def test_enseignants_only_publication_hidden_from_eleves(self):
        eleve = Utilisateur.objects.get(username="eleve.202600001")
        visibles = Publication.visibles_pour(eleve)
        self.assertFalse(visibles.filter(titre="Note de service internes").exists())

    def test_enseignants_only_publication_visible_to_enseignants(self):
        enseignant = Utilisateur.objects.get(username="prof.mathématiques")
        visibles = Publication.visibles_pour(enseignant)
        self.assertTrue(visibles.filter(titre="Note de service internes").exists())

    def test_liste_view_loads_for_every_role(self):
        for username in ("admin.direction", "prof.mathématiques", "eleve.202600001", "parent.benali"):
            self.assertTrue(self.client.login(username=username, password=DEMO_PASSWORD))
            response = self.client.get("/actualites/")
            self.assertEqual(response.status_code, 200)
            self.client.logout()

    def test_publication_not_visible_to_another_etablissement(self):
        self.assertTrue(self.client.login(username="admin.oran", password=DEMO_PASSWORD))
        response = self.client.get("/actualites/")
        self.assertNotContains(response, "Note de service internes")


class LectureAccuseeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        admin = Utilisateur.objects.get(username="admin.direction")
        cls.publication = Publication.objects.create(
            titre="Rentrée", contenu="...", audience=Publication.Audience.TOUS, etablissement=admin.etablissement,
        )

    def test_marquer_lu_creates_accuse_and_redirects(self):
        self.client.login(username="eleve.202600001", password=DEMO_PASSWORD)
        response = self.client.post(f"/actualites/{self.publication.pk}/lu/")
        self.assertRedirects(response, "/actualites/")
        eleve = Utilisateur.objects.get(username="eleve.202600001")
        self.assertTrue(LectureAccusee.objects.filter(publication=self.publication, utilisateur=eleve).exists())

    def test_marquer_lu_is_idempotent(self):
        self.client.login(username="eleve.202600001", password=DEMO_PASSWORD)
        self.client.post(f"/actualites/{self.publication.pk}/lu/")
        self.client.post(f"/actualites/{self.publication.pk}/lu/")
        eleve = Utilisateur.objects.get(username="eleve.202600001")
        self.assertEqual(LectureAccusee.objects.filter(publication=self.publication, utilisateur=eleve).count(), 1)

    def test_marquer_lu_rejects_publication_outside_audience(self):
        enseignants_only = Publication.objects.create(
            titre="Note interne", contenu="...", audience=Publication.Audience.ENSEIGNANTS
        )
        self.client.login(username="eleve.202600001", password=DEMO_PASSWORD)
        response = self.client.post(f"/actualites/{enseignants_only.pk}/lu/")
        self.assertEqual(response.status_code, 404)

    def test_liste_view_flags_publications_already_read(self):
        self.client.login(username="eleve.202600001", password=DEMO_PASSWORD)
        self.client.post(f"/actualites/{self.publication.pk}/lu/")
        response = self.client.get("/actualites/")
        self.assertContains(response, "Lu")

    def test_suivi_lecture_requires_admin_role(self):
        self.client.login(username="eleve.202600001", password=DEMO_PASSWORD)
        response = self.client.get(f"/actualites/{self.publication.pk}/suivi/")
        self.assertEqual(response.status_code, 403)

    def test_suivi_lecture_counts_reads_correctly(self):
        self.client.login(username="eleve.202600001", password=DEMO_PASSWORD)
        self.client.post(f"/actualites/{self.publication.pk}/lu/")
        self.client.logout()

        self.client.login(username="admin.direction", password=DEMO_PASSWORD)
        response = self.client.get(f"/actualites/{self.publication.pk}/suivi/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["nb_lu"], 1)
