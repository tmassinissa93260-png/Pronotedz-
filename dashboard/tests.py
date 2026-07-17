import datetime

from django.core.management import call_command
from django.test import TestCase

from academics.models import Classe
from attendance.models import Absence, Seance
from timetable.models import EmploiDuTempsEntry


class DashboardSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def _login(self, username):
        from accounts.management.commands.seed_demo import DEMO_PASSWORD

        self.assertTrue(self.client.login(username=username, password=DEMO_PASSWORD))

    def test_admin_dashboard_loads(self):
        self._login("admin.direction")
        response = self.client.get("/dashboard/admin/")
        self.assertEqual(response.status_code, 200)

    def test_enseignant_dashboard_loads(self):
        self._login("prof.mathématiques")
        response = self.client.get("/dashboard/enseignant/")
        self.assertEqual(response.status_code, 200)

    def test_eleve_dashboard_loads(self):
        self._login("eleve.202600001")
        response = self.client.get("/dashboard/eleve/")
        self.assertEqual(response.status_code, 200)

    def test_parent_dashboard_loads(self):
        self._login("parent.benali")
        response = self.client.get("/dashboard/parent/")
        self.assertEqual(response.status_code, 200)

    def test_dispatch_redirects_by_role(self):
        self._login("eleve.202600001")
        response = self.client.get("/dashboard/")
        self.assertRedirects(response, "/dashboard/eleve/")

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get("/dashboard/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)


class AdminDashboardStatsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def _login(self, username):
        from accounts.management.commands.seed_demo import DEMO_PASSWORD

        self.assertTrue(self.client.login(username=username, password=DEMO_PASSWORD))

    def test_absenteeism_rate_reflects_absences_marked_today(self):
        classe = Classe.objects.filter(eleves__isnull=False).distinct().first()
        entry = EmploiDuTempsEntry.objects.filter(classe=classe).first()
        seance = Seance.get_or_create_for(entry, datetime.date.today())
        eleve = classe.eleves.first()
        Absence.objects.get_or_create(seance=seance, eleve=eleve)

        self._login("admin.direction")
        response = self.client.get("/dashboard/admin/")

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.context["nb_absents_aujourdhui"], 1)
        self.assertGreater(response.context["taux_absenteisme"], 0)

    def test_recent_activity_only_shows_published_evaluations(self):
        from academics.models import Matiere, Trimestre
        from accounts.models import Enseignant
        from grades.models import Evaluation

        classe = Classe.objects.filter(eleves__isnull=False).distinct().first()
        trimestre = Trimestre.objects.filter(annee_scolaire=classe.annee_scolaire).first()
        matiere = Matiere.objects.first()
        enseignant = Enseignant.objects.first()
        Evaluation.objects.create(
            classe=classe, matiere=matiere, enseignant=enseignant, trimestre=trimestre,
            titre="Interro non publiée", date_evaluation=datetime.date.today(), publie=False,
        )

        self._login("admin.direction")
        response = self.client.get("/dashboard/admin/")

        libelles = [item["libelle"] for item in response.context["activite_recente"]]
        self.assertFalse(any("Interro non publiée" in libelle for libelle in libelles))
