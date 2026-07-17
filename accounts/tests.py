from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase

from academics.models import AnneeScolaire, Etablissement
from accounts.contacts import contacts_autorises
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


class MultiTenantIsolationTests(TestCase):
    """seed_demo creates two independent établissements (Lycée Ibn Khaldoun
    and Collège El Amir Abdelkader) precisely so isolation between them is
    exercised, not just asserted in the abstract."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_second_etablissement_scoped_dashboard_counts(self):
        self.assertTrue(self.client.login(username="admin.oran", password=DEMO_PASSWORD))
        response = self.client.get("/dashboard/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["nb_eleves"], 3)
        self.assertEqual(response.context["nb_enseignants"], 1)

    def test_admin_panel_hides_other_etablissement(self):
        self.assertTrue(self.client.login(username="admin.oran", password=DEMO_PASSWORD))
        response = self.client.get("/admin/academics/etablissement/")
        self.assertContains(response, "Amir Abdelkader")
        self.assertNotContains(response, "Ibn Khaldoun")

    def test_admin_panel_hides_other_etablissement_users(self):
        self.assertTrue(self.client.login(username="admin.oran", password=DEMO_PASSWORD))
        response = self.client.get("/admin/accounts/utilisateur/")
        self.assertContains(response, "admin.oran")
        self.assertNotContains(response, "admin.direction")

    def test_admin_panel_hides_other_etablissement_classes(self):
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))
        response = self.client.get("/admin/academics/classe/")
        self.assertContains(response, "1AS Sciences 1")
        self.assertNotContains(response, "1AM 1")

    def test_admin_cannot_message_across_etablissements(self):
        admin_oran = Utilisateur.objects.get(username="admin.oran")
        admin_direction = Utilisateur.objects.get(username="admin.direction")
        contacts = contacts_autorises(admin_oran)
        self.assertFalse(contacts.filter(pk=admin_direction.pk).exists())

    def test_eleve_cannot_reach_admin_of_other_etablissement(self):
        eleve_lyc = Utilisateur.objects.get(username="eleve.202600001")
        admin_oran = Utilisateur.objects.get(username="admin.oran")
        contacts = contacts_autorises(eleve_lyc)
        self.assertFalse(contacts.filter(pk=admin_oran.pk).exists())

    def test_csv_import_scopes_new_students_to_the_importing_admins_school(self):
        self.assertTrue(self.client.login(username="admin.oran", password=DEMO_PASSWORD))
        csv_contenu = "nom,prenom,matricule,classe\nNouvel,Eleve,999020,1AM 1\n"
        self.client.post("/accounts/import-csv/", {"type_import": "eleves", "fichier": _csv_file(csv_contenu)})

        nouvel_eleve = Eleve.objects.get(matricule="999020")
        self.assertEqual(nouvel_eleve.user.etablissement, Utilisateur.objects.get(username="admin.oran").etablissement)

    def test_active_annee_scolaire_lookup_does_not_cross_etablissements(self):
        annee_oran = AnneeScolaire.objects.get(etablissement__nom="Collège El Amir Abdelkader", est_active=True)
        annee_lyc = AnneeScolaire.objects.get(etablissement__nom="Lycée Ibn Khaldoun", est_active=True)
        self.assertNotEqual(annee_oran.pk, annee_lyc.pk)
        self.assertTrue(Etablissement.objects.count() >= 2)
