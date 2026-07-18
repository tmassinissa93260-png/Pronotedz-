from django.core import mail
from django.core.management import call_command
from django.test import TestCase

from academics.models import Etablissement, Niveau
from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Utilisateur

from .models import Candidature
from .services import changer_statut, convertir_en_eleve


class CandidaturePublicFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.etablissement = Etablissement.objects.get(nom="Lycée Ibn Khaldoun")
        cls.niveau = Niveau.objects.get(libelle="1AS")

    def test_submitting_the_form_creates_a_candidature_and_sends_confirmation_email(self):
        response = self.client.post(
            f"/admissions/candidature/{self.etablissement.slug}/",
            {
                "nom": "Kaci", "prenom": "Sofia", "niveau_souhaite": self.niveau.pk,
                "nom_parent": "Ahmed Kaci", "telephone_parent": "0555000000", "email_parent": "ahmed.kaci@example.com",
            },
        )
        candidature = Candidature.objects.get(nom="Kaci")
        self.assertRedirects(response, f"/admissions/merci/{candidature.reference}/")
        self.assertEqual(candidature.etablissement, self.etablissement)
        self.assertEqual(candidature.statut, Candidature.Statut.RECU)

    def test_missing_required_fields_does_not_create_a_candidature(self):
        response = self.client.post(f"/admissions/candidature/{self.etablissement.slug}/", {"nom": "Incomplet"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Candidature.objects.filter(nom="Incomplet").exists())

    def test_confirmation_page_shows_reference(self):
        candidature = Candidature.objects.create(
            etablissement=self.etablissement, niveau_souhaite=self.niveau, nom="Test", prenom="Enfant",
            nom_parent="Parent Test", telephone_parent="0555", email_parent="p@example.com",
        )
        response = self.client.get(f"/admissions/merci/{candidature.reference}/")
        self.assertContains(response, candidature.reference)

    def test_suivi_finds_matching_candidature(self):
        candidature = Candidature.objects.create(
            etablissement=self.etablissement, niveau_souhaite=self.niveau, nom="Test", prenom="Suivi",
            nom_parent="Parent Test", telephone_parent="0555", email_parent="suivi@example.com",
        )
        response = self.client.post("/admissions/suivi/", {"reference": candidature.reference, "email": "suivi@example.com"})
        self.assertContains(response, "Suivi")

    def test_suivi_with_wrong_email_finds_nothing(self):
        candidature = Candidature.objects.create(
            etablissement=self.etablissement, niveau_souhaite=self.niveau, nom="Test", prenom="Suivi2",
            nom_parent="Parent Test", telephone_parent="0555", email_parent="correct@example.com",
        )
        response = self.client.post("/admissions/suivi/", {"reference": candidature.reference, "email": "wrong@example.com"})
        self.assertContains(response, "Aucune candidature")


class CandidatureAdminPipelineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.etablissement = Etablissement.objects.get(nom="Lycée Ibn Khaldoun")
        cls.niveau = Niveau.objects.get(libelle="1AS")
        cls.candidature = Candidature.objects.create(
            etablissement=cls.etablissement, niveau_souhaite=cls.niveau, nom="Amrani", prenom="Yasmine",
            nom_parent="Parent Amrani", telephone_parent="0555111111", email_parent="parent.amrani@example.com",
        )

    def _login(self, username):
        self.assertTrue(self.client.login(username=username, password=DEMO_PASSWORD))

    def test_admin_sees_pipeline_for_their_own_etablissement(self):
        self._login("admin.direction")
        response = self.client.get("/admissions/")
        self.assertContains(response, "Amrani")

    def test_admin_of_another_etablissement_does_not_see_the_candidature(self):
        self._login("admin.oran")
        response = self.client.get("/admissions/")
        self.assertNotContains(response, "Amrani")

    def test_admin_of_another_etablissement_gets_404_on_detail(self):
        self._login("admin.oran")
        response = self.client.get(f"/admissions/{self.candidature.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_non_admin_cannot_access_pipeline(self):
        self._login("prof.mathématiques")
        response = self.client.get("/admissions/")
        self.assertEqual(response.status_code, 403)

    def test_changing_statut_sends_email_and_updates_record(self):
        self._login("admin.direction")
        mail.outbox = []
        response = self.client.post(
            f"/admissions/{self.candidature.pk}/", {"statut": Candidature.Statut.EN_EXAMEN, "notes_admin": "Dossier complet"},
        )
        self.assertEqual(response.status_code, 302)
        self.candidature.refresh_from_db()
        self.assertEqual(self.candidature.statut, Candidature.Statut.EN_EXAMEN)
        self.assertEqual(self.candidature.notes_admin, "Dossier complet")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("parent.amrani@example.com", mail.outbox[0].to)

    def test_conversion_to_eleve_creates_account_and_notification(self):
        from academics.models import Classe

        changer_statut(self.candidature, Candidature.Statut.ACCEPTE, Utilisateur.objects.get(username="admin.direction"))
        classe = Classe.objects.get(libelle="1AS Sciences 1")

        self._login("admin.direction")
        mail.outbox = []
        response = self.client.post(f"/admissions/{self.candidature.pk}/convertir/", {"classe": classe.pk})
        self.assertEqual(response.status_code, 200)

        self.candidature.refresh_from_db()
        self.assertIsNotNone(self.candidature.eleve_cree)
        self.assertEqual(self.candidature.eleve_cree.user.first_name, "Yasmine")
        self.assertTrue(self.candidature.eleve_cree.user.must_change_password)
        self.assertEqual(len(mail.outbox), 1)

    def test_cannot_convert_twice(self):
        from academics.models import Classe

        admin = Utilisateur.objects.get(username="admin.direction")
        changer_statut(self.candidature, Candidature.Statut.ACCEPTE, admin)
        classe = Classe.objects.get(libelle="1AS Sciences 1")
        convertir_en_eleve(self.candidature, classe)

        with self.assertRaises(ValueError):
            convertir_en_eleve(self.candidature, classe)

    def test_cannot_convert_a_candidature_that_is_not_accepted(self):
        from academics.models import Classe

        classe = Classe.objects.get(libelle="1AS Sciences 1")
        with self.assertRaises(ValueError):
            convertir_en_eleve(self.candidature, classe)
