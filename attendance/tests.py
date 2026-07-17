from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase

from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Eleve

from .models import Absence, Justificatif


class ParentScopingTests(TestCase):
    """A parent must never be able to view another family's child via URL manipulation."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_parent_cannot_view_other_parents_child_absences(self):
        # parent.hamdi only has 202600002 as a child; 202600001 belongs to parent.benali.
        self.assertTrue(self.client.login(username="parent.hamdi", password=DEMO_PASSWORD))
        autre_enfant = Eleve.objects.get(matricule="202600001")

        response = self.client.get(f"/absences/historique/?enfant={autre_enfant.pk}")
        self.assertEqual(response.status_code, 404)

    def test_parent_can_view_own_child_absences(self):
        self.assertTrue(self.client.login(username="parent.hamdi", password=DEMO_PASSWORD))
        son_enfant = Eleve.objects.get(matricule="202600002")

        response = self.client.get(f"/absences/historique/?enfant={son_enfant.pk}")
        self.assertEqual(response.status_code, 200)

    def test_historique_renders_for_child_with_an_actual_absence(self):
        # 202600001 has a seeded Absence (see seed_demo._make_absences_et_cahier), already
        # marked justifiée — this exercises the justificatif-status rendering path (the
        # `|last` queryset filter bug only surfaced on non-empty absence lists).
        self.assertTrue(self.client.login(username="parent.benali", password=DEMO_PASSWORD))
        enfant_avec_absence = Eleve.objects.get(matricule="202600001")

        response = self.client.get(f"/absences/historique/?enfant={enfant_avec_absence.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Maladie")

    def test_historique_shows_justificatif_button_for_unjustified_absence(self):
        self.assertTrue(self.client.login(username="parent.benali", password=DEMO_PASSWORD))
        enfant = Eleve.objects.get(matricule="202600001")
        absence_existante = Absence.objects.get(eleve=enfant)
        absence_existante.justifiee = False
        absence_existante.save()

        response = self.client.get(f"/absences/historique/?enfant={enfant.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Joindre un justificatif")

    def test_enseignant_cannot_take_attendance_for_class_not_taught(self):
        # prof.anglais never teaches Physique-Chimie's slot for the other teacher's entry.
        self.client.login(username="prof.anglais", password=DEMO_PASSWORD)
        from timetable.models import EmploiDuTempsEntry

        autre_entry = EmploiDuTempsEntry.objects.exclude(enseignant__user__username="prof.anglais").first()
        response = self.client.get(f"/absences/appel/{autre_entry.pk}/")
        self.assertEqual(response.status_code, 404)


class JustificatifUploadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def _absence_de_202600001(self):
        # Seeded in seed_demo._make_absences_et_cahier for eleves_sciences[0].
        return Absence.objects.get(eleve__matricule="202600001")

    def test_parent_cannot_upload_justificatif_for_other_parents_child(self):
        self.assertTrue(self.client.login(username="parent.hamdi", password=DEMO_PASSWORD))
        absence = self._absence_de_202600001()  # belongs to parent.benali, not parent.hamdi

        fichier = SimpleUploadedFile("justif.pdf", b"contenu", content_type="application/pdf")
        response = self.client.post(f"/absences/justificatif/{absence.pk}/", {"fichier": fichier, "commentaire": "test"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Justificatif.objects.filter(absence=absence).count(), 0)

    def test_parent_can_upload_justificatif_for_own_child(self):
        self.assertTrue(self.client.login(username="parent.benali", password=DEMO_PASSWORD))
        absence = self._absence_de_202600001()

        fichier = SimpleUploadedFile("justif.pdf", b"contenu", content_type="application/pdf")
        response = self.client.post(f"/absences/justificatif/{absence.pk}/", {"fichier": fichier, "commentaire": "Rendez-vous médical"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Justificatif.objects.filter(absence=absence).count(), 1)
        justificatif = Justificatif.objects.get(absence=absence)
        self.assertEqual(justificatif.statut, Justificatif.Statut.EN_ATTENTE)
