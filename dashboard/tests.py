from django.core.management import call_command
from django.test import TestCase


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
