import datetime

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase

from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Eleve, Enseignant

from .models import Devoir, RenduDevoir


class ParentScopingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_parent_cannot_view_other_parents_child_cahier(self):
        self.assertTrue(self.client.login(username="parent.hamdi", password=DEMO_PASSWORD))
        autre_enfant = Eleve.objects.get(matricule="202600001")

        response = self.client.get(f"/cahier-de-texte/?enfant={autre_enfant.pk}")
        self.assertEqual(response.status_code, 404)


class RenduDevoirTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_student_cannot_submit_after_deadline(self):
        # Seeded in seed_demo._make_absences_et_cahier: due date is in the past.
        devoir_expire = Devoir.objects.get(consigne__icontains="Exercices 3, 5 et 8")
        self.assertFalse(devoir_expire.est_ouvert)

        self.assertTrue(self.client.login(username="eleve.202600001", password=DEMO_PASSWORD))
        fichier = SimpleUploadedFile("devoir.pdf", b"contenu", content_type="application/pdf")
        response = self.client.post(f"/cahier-de-texte/devoir/{devoir_expire.pk}/soumettre/", {"fichier": fichier})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(RenduDevoir.objects.filter(devoir=devoir_expire).exists())

    def test_student_cannot_access_devoir_of_another_classe(self):
        # 202600007 is in 1AS Lettres 1; the seeded devoir belongs to 1AS Sciences 1.
        devoir_sciences = Devoir.objects.get(consigne__icontains="Exercices 3, 5 et 8")
        self.assertTrue(self.client.login(username="eleve.202600007", password=DEMO_PASSWORD))

        response = self.client.get(f"/cahier-de-texte/devoir/{devoir_sciences.pk}/soumettre/")
        self.assertEqual(response.status_code, 404)

    def test_student_can_submit_to_an_open_devoir(self):
        devoir_sciences = Devoir.objects.get(consigne__icontains="Exercices 3, 5 et 8")
        devoir_sciences.date_a_faire_pour = datetime.date.today() + datetime.timedelta(days=7)
        devoir_sciences.save()

        self.assertTrue(self.client.login(username="eleve.202600001", password=DEMO_PASSWORD))
        fichier = SimpleUploadedFile("devoir.pdf", b"contenu", content_type="application/pdf")
        response = self.client.post(f"/cahier-de-texte/devoir/{devoir_sciences.pk}/soumettre/", {"fichier": fichier})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(RenduDevoir.objects.filter(devoir=devoir_sciences, eleve__matricule="202600001").exists())

    def test_teacher_cannot_view_rendus_for_a_devoir_not_theirs(self):
        devoir = Devoir.objects.get(consigne__icontains="Exercices 3, 5 et 8")
        # This devoir was created by whichever teacher taught the first créneau of classe_sciences;
        # pick a teacher guaranteed not to be that one.
        autre_prof = Enseignant.objects.exclude(pk=devoir.enseignant_id).first()

        self.client.login(username=autre_prof.user.username, password=DEMO_PASSWORD)
        response = self.client.get(f"/cahier-de-texte/devoir/{devoir.pk}/rendus/")
        self.assertEqual(response.status_code, 404)
