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

    def _classe_lycee_ibn_khaldoun(self):
        return Classe.objects.filter(
            eleves__isnull=False, annee_scolaire__etablissement__nom="Lycée Ibn Khaldoun"
        ).distinct().first()

    def test_absenteeism_rate_reflects_absences_marked_today(self):
        classe = self._classe_lycee_ibn_khaldoun()
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
        from academics.models import Trimestre
        from grades.models import Evaluation

        classe = self._classe_lycee_ibn_khaldoun()
        trimestre = Trimestre.objects.filter(annee_scolaire=classe.annee_scolaire).first()
        matiere = classe.emploi_du_temps.first().matiere
        enseignant = classe.emploi_du_temps.first().enseignant
        Evaluation.objects.create(
            classe=classe, matiere=matiere, enseignant=enseignant, trimestre=trimestre,
            titre="Interro non publiée", date_evaluation=datetime.date.today(), publie=False,
        )

        self._login("admin.direction")
        response = self.client.get("/dashboard/admin/")

        libelles = [item["libelle"] for item in response.context["activite_recente"]]
        self.assertFalse(any("Interro non publiée" in libelle for libelle in libelles))


class LanguageSwitchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def _login(self, username):
        from accounts.management.commands.seed_demo import DEMO_PASSWORD

        self.assertTrue(self.client.login(username=username, password=DEMO_PASSWORD))

    def test_default_language_is_french_ltr(self):
        self._login("admin.direction")
        response = self.client.get("/dashboard/admin/")
        body = response.content.decode()
        self.assertIn('dir="ltr"', body)
        self.assertIn("Page d'accueil", body)

    def test_switching_to_arabic_persists_and_flips_to_rtl(self):
        self._login("admin.direction")
        self.client.post("/i18n/setlang/", {"language": "ar", "next": "/dashboard/admin/"})
        response = self.client.get("/dashboard/admin/")
        body = response.content.decode()
        self.assertIn('dir="rtl"', body)
        self.assertIn("الصفحة الرئيسية", body)
        self.assertIn("bootstrap.rtl.min.css", body)

    def test_switching_back_to_french_restores_ltr(self):
        self._login("admin.direction")
        self.client.post("/i18n/setlang/", {"language": "ar", "next": "/dashboard/admin/"})
        self.client.post("/i18n/setlang/", {"language": "fr", "next": "/dashboard/admin/"})
        response = self.client.get("/dashboard/admin/")
        body = response.content.decode()
        self.assertIn('dir="ltr"', body)
        self.assertIn("bootstrap.min.css", body)
        self.assertNotIn("bootstrap.rtl.min.css", body)


class AdminAnalyticsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def _login(self, username):
        from accounts.management.commands.seed_demo import DEMO_PASSWORD

        self.assertTrue(self.client.login(username=username, password=DEMO_PASSWORD))

    def test_admin_analytics_loads_with_moyennes_par_classe(self):
        self._login("admin.direction")

        response = self.client.get("/dashboard/admin/analytics/")

        self.assertEqual(response.status_code, 200)
        moyennes = response.context["moyennes_par_classe"]
        self.assertTrue(moyennes)
        self.assertTrue(any(ligne["moyenne"] is not None for ligne in moyennes))

    def test_repartition_moyennes_sums_to_total_eleves_with_notes(self):
        self._login("admin.direction")

        response = self.client.get("/dashboard/admin/analytics/")

        repartition = response.context["repartition_moyennes"]
        nb_total = sum(ligne["nb_eleves"] for ligne in repartition)
        nb_attendu = sum(ligne["nb_notes"] for ligne in response.context["moyennes_par_classe"])
        self.assertEqual(nb_total, nb_attendu)
        self.assertGreater(nb_total, 0)

    def test_absenteisme_covers_six_weeks(self):
        self._login("admin.direction")

        response = self.client.get("/dashboard/admin/analytics/")

        self.assertEqual(len(response.context["absenteisme"]), 6)

    def test_trimestre_selector_switches_the_selected_trimestre(self):
        from academics.models import Trimestre

        self._login("admin.direction")
        response = self.client.get("/dashboard/admin/analytics/")
        autre_trimestre = Trimestre.objects.filter(
            annee_scolaire=response.context["annee"]
        ).exclude(pk=response.context["trimestre"].pk).first()

        response = self.client.get("/dashboard/admin/analytics/", {"trimestre": autre_trimestre.pk})

        self.assertEqual(response.context["trimestre"], autre_trimestre)

    def test_non_admin_cannot_access_analytics(self):
        self._login("eleve.202600001")
        response = self.client.get("/dashboard/admin/analytics/")
        self.assertEqual(response.status_code, 403)
