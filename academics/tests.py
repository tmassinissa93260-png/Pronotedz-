from decimal import Decimal

from django.core.management import call_command
from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse

from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Eleve, Enseignant, Utilisateur
from finance.models import Facture

from .models import Classe, Etablissement, GroupeScolaire, Niveau


class GroupeTableauBordTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.admin = Utilisateur.objects.get(username="admin.direction")
        cls.groupe = cls.admin.groupe_gere

    def test_admin_gerant_un_groupe_a_deux_campus(self):
        self.assertIsNotNone(self.groupe)
        self.assertEqual(Etablissement.objects.filter(groupe=self.groupe).count(), 2)

    def test_tableau_bord_agrege_les_deux_campus(self):
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))

        response = self.client.get(reverse("academics:groupe_tableau_bord"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["campus"]), 2)

        nb_eleves_attendu = Eleve.objects.filter(user__etablissement__groupe=self.groupe).count()
        nb_classes_attendu = Classe.objects.filter(annee_scolaire__etablissement__groupe=self.groupe).count()
        nb_enseignants_attendu = Enseignant.objects.filter(user__etablissement__groupe=self.groupe).count()
        total_attendu = Facture.objects.filter(
            eleve__user__etablissement__groupe=self.groupe
        ).aggregate(total=Sum("montant"))["total"] or Decimal("0")

        self.assertEqual(response.context["totaux"]["nb_eleves"], nb_eleves_attendu)
        self.assertEqual(response.context["totaux"]["nb_classes"], nb_classes_attendu)
        self.assertEqual(response.context["totaux"]["nb_enseignants"], nb_enseignants_attendu)
        self.assertEqual(response.context["totaux"]["total_attendu"], total_attendu)

    def test_admin_sans_groupe_gere_recoit_403(self):
        self.assertTrue(self.client.login(username="admin.oran", password=DEMO_PASSWORD))

        response = self.client.get(reverse("academics:groupe_tableau_bord"))

        self.assertEqual(response.status_code, 403)

    def test_anonyme_est_redirige_vers_la_connexion(self):
        response = self.client.get(reverse("academics:groupe_tableau_bord"))
        self.assertEqual(response.status_code, 302)

    def test_nav_link_visible_seulement_pour_admin_gerant_un_groupe(self):
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))
        response = self.client.get(reverse("dashboard:admin_home"))
        self.assertContains(response, "Groupe scolaire")

        self.client.logout()
        self.assertTrue(self.client.login(username="admin.oran", password=DEMO_PASSWORD))
        response = self.client.get(reverse("dashboard:admin_home"))
        self.assertNotContains(response, "Groupe scolaire")


class PortailPublicTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.etablissement = Etablissement.objects.get(nom="Lycée Ibn Khaldoun")

    def test_portail_accessible_sans_connexion(self):
        response = self.client.get(reverse("portail_public", args=[self.etablissement.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.etablissement.nom)

    def test_portail_affiche_seulement_les_actualites_publiques(self):
        response = self.client.get(reverse("portail_public", args=[self.etablissement.slug]))
        self.assertContains(response, "Portes ouvertes 2026")
        self.assertNotContains(response, "Réunion parents-professeurs")

    def test_portail_liste_les_niveaux_de_letablissement(self):
        response = self.client.get(reverse("portail_public", args=[self.etablissement.slug]))
        niveaux_attendus = Niveau.objects.filter(
            classes__annee_scolaire__etablissement=self.etablissement
        ).distinct()
        self.assertEqual(set(response.context["niveaux"]), set(niveaux_attendus))

    def test_portail_lien_vers_la_candidature(self):
        response = self.client.get(reverse("portail_public", args=[self.etablissement.slug]))
        self.assertContains(response, reverse("admissions:candidature_form", args=[self.etablissement.slug]))

    def test_slug_inconnu_renvoie_404(self):
        response = self.client.get(reverse("portail_public", args=["ecole-qui-nexiste-pas"]))
        self.assertEqual(response.status_code, 404)

    def test_page_liens_admin_contient_le_lien_du_portail(self):
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))
        response = self.client.get(reverse("admissions:portail_liens"))
        self.assertContains(response, reverse("portail_public", args=[self.etablissement.slug]))
