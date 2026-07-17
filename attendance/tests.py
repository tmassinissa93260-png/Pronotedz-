from django.core.management import call_command
from django.test import TestCase

from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Eleve


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

    def test_enseignant_cannot_take_attendance_for_class_not_taught(self):
        # prof.anglais never teaches Physique-Chimie's slot for the other teacher's entry.
        self.client.login(username="prof.anglais", password=DEMO_PASSWORD)
        from timetable.models import EmploiDuTempsEntry

        autre_entry = EmploiDuTempsEntry.objects.exclude(enseignant__user__username="prof.anglais").first()
        response = self.client.get(f"/absences/appel/{autre_entry.pk}/")
        self.assertEqual(response.status_code, 404)
