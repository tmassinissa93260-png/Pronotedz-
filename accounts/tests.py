from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase

from academics.models import AnneeScolaire
from accounts.management.commands.seed_demo import DEMO_PASSWORD

from .models import Eleve, Utilisateur


def _csv_file(contenu):
    return SimpleUploadedFile("import.csv", contenu.encode("utf-8"), content_type="text/csv")


class ImportCSVTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_admin_can_import_eleves_with_temp_password(self):
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))
        csv_contenu = "nom,prenom,matricule,classe\nBenzema,Karim,999001,1AS Sciences 1\n"

        response = self.client.post(
            "/accounts/import-csv/", {"type_import": "eleves", "fichier": _csv_file(csv_contenu)}
        )
        self.assertEqual(response.status_code, 200)

        eleve = Eleve.objects.get(matricule="999001")
        self.assertTrue(eleve.user.must_change_password)
        self.assertContains(response, "999001")

    def test_import_reports_error_for_unknown_classe(self):
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))
        csv_contenu = "nom,prenom,matricule,classe\nInconnu,Test,999002,Classe Inexistante\n"

        response = self.client.post(
            "/accounts/import-csv/", {"type_import": "eleves", "fichier": _csv_file(csv_contenu)}
        )
        self.assertContains(response, "introuvable")
        self.assertFalse(Eleve.objects.filter(matricule="999002").exists())

    def test_import_reports_error_for_duplicate_matricule(self):
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))
        csv_contenu = "nom,prenom,matricule,classe\nDupliqué,Test,202600001,1AS Sciences 1\n"

        response = self.client.post(
            "/accounts/import-csv/", {"type_import": "eleves", "fichier": _csv_file(csv_contenu)}
        )
        self.assertContains(response, "déjà utilisé")

    def test_non_admin_cannot_access_import_csv(self):
        self.assertTrue(self.client.login(username="prof.mathématiques", password=DEMO_PASSWORD))
        response = self.client.get("/accounts/import-csv/")
        self.assertEqual(response.status_code, 403)


class ForceChangePasswordTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_user_with_must_change_password_is_redirected_everywhere(self):
        annee = AnneeScolaire.objects.filter(est_active=True).first()
        csv_contenu = "nom,prenom,matricule,classe\nNouveau,Eleve,999010,1AS Sciences 1\n"
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))
        self.client.post("/accounts/import-csv/", {"type_import": "eleves", "fichier": _csv_file(csv_contenu)})
        self.client.logout()

        nouvel_eleve = Utilisateur.objects.get(eleve__matricule="999010")
        self.client.force_login(nouvel_eleve)

        response = self.client.get("/dashboard/eleve/", follow=True)
        self.assertRedirects(response, "/accounts/changer-mot-de-passe/")

    def test_changing_password_clears_the_flag_and_unblocks_navigation(self):
        annee = AnneeScolaire.objects.filter(est_active=True).first()
        csv_contenu = "nom,prenom,matricule,classe\nNouveau,Eleve,999011,1AS Sciences 1\n"
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))
        self.client.post("/accounts/import-csv/", {"type_import": "eleves", "fichier": _csv_file(csv_contenu)})
        self.client.logout()

        nouvel_eleve = Utilisateur.objects.get(eleve__matricule="999011")
        self.client.force_login(nouvel_eleve)

        response = self.client.post(
            "/accounts/changer-mot-de-passe/",
            {"mot_de_passe1": "NouveauMdp123", "mot_de_passe2": "NouveauMdp123"},
        )
        self.assertEqual(response.status_code, 302)

        nouvel_eleve.refresh_from_db()
        self.assertFalse(nouvel_eleve.must_change_password)

        response = self.client.get("/dashboard/eleve/")
        self.assertEqual(response.status_code, 200)
