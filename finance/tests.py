import datetime
from decimal import Decimal

from django.core import mail
from django.core.management import call_command
from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse

from academics.models import Niveau
from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Eleve, Parent

from .models import Facture, FraisScolarite, Paiement
from .services import enregistrer_paiement, generer_factures, recalculer_statut


class GenererFacturesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.niveau = Niveau.objects.get(libelle="1AS")
        cls.annee = Eleve.objects.get(matricule="202600001").classe.annee_scolaire

    def test_generer_factures_creates_one_per_eleve_of_the_niveau(self):
        frais = FraisScolarite.objects.create(
            annee_scolaire=self.annee, niveau=self.niveau, libelle="Sortie pédagogique",
            montant=Decimal("1500"), date_echeance=datetime.date.today() + datetime.timedelta(days=30),
        )
        nb_eleves = Eleve.objects.filter(classe__niveau=self.niveau, classe__annee_scolaire=self.annee).count()

        nb_creees = generer_factures(frais)

        self.assertEqual(nb_creees, nb_eleves)
        self.assertEqual(Facture.objects.filter(frais=frais).count(), nb_eleves)

    def test_generer_factures_is_idempotent(self):
        frais = FraisScolarite.objects.create(
            annee_scolaire=self.annee, niveau=self.niveau, libelle="Sortie pédagogique 2",
            montant=Decimal("1500"), date_echeance=datetime.date.today() + datetime.timedelta(days=30),
        )
        generer_factures(frais)

        nb_creees_second_appel = generer_factures(frais)

        self.assertEqual(nb_creees_second_appel, 0)


class RecalculerStatutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.eleve = Eleve.objects.get(matricule="202600003")
        cls.frais = FraisScolarite.objects.get(libelle="Frais d'inscription 2025-2026")
        cls.facture = Facture.objects.get(eleve=cls.eleve, frais=cls.frais)

    def test_facture_en_retard_when_overdue_and_unpaid(self):
        recalculer_statut(self.facture)
        self.assertEqual(self.facture.statut, Facture.Statut.EN_RETARD)

    def test_facture_partiellement_payee_after_partial_payment(self):
        enregistrer_paiement(
            self.facture, Decimal("2000"), datetime.date.today(), Paiement.Mode.ESPECES, "", None,
        )
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.PARTIELLEMENT_PAYEE)

    def test_facture_payee_after_full_payment(self):
        enregistrer_paiement(
            self.facture, self.facture.montant, datetime.date.today(), Paiement.Mode.ESPECES, "", None,
        )
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(self.facture.montant_restant, 0)

    def test_paiement_gets_a_unique_receipt_number(self):
        paiement = enregistrer_paiement(
            self.facture, Decimal("1000"), datetime.date.today(), Paiement.Mode.ESPECES, "", None,
        )
        self.assertTrue(paiement.numero_recu)


class FraisAdminViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.niveau = Niveau.objects.get(libelle="1AS")
        cls.annee = Eleve.objects.get(matricule="202600001").classe.annee_scolaire

    def test_frais_creer_generates_factures_for_the_niveau(self):
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))
        nb_eleves = Eleve.objects.filter(classe__niveau=self.niveau, classe__annee_scolaire=self.annee).count()

        response = self.client.post(
            reverse("finance:frais_creer"),
            {
                "niveau": self.niveau.pk, "annee_scolaire": self.annee.pk, "libelle": "Frais de cantine",
                "montant": "2500", "date_echeance": "2026-12-01",
            },
        )

        self.assertRedirects(response, reverse("finance:frais_liste"))
        frais = FraisScolarite.objects.get(libelle="Frais de cantine")
        self.assertEqual(Facture.objects.filter(frais=frais).count(), nb_eleves)

    def test_frais_creer_rejects_invalid_montant(self):
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))

        response = self.client.post(
            reverse("finance:frais_creer"),
            {
                "niveau": self.niveau.pk, "annee_scolaire": self.annee.pk, "libelle": "Frais invalide",
                "montant": "pas-un-nombre", "date_echeance": "2026-12-01",
            },
        )

        self.assertRedirects(response, reverse("finance:frais_creer"))
        self.assertFalse(FraisScolarite.objects.filter(libelle="Frais invalide").exists())

    def test_non_admin_cannot_access_frais_liste(self):
        self.assertTrue(self.client.login(username="eleve.202600001", password=DEMO_PASSWORD))
        response = self.client.get(reverse("finance:frais_liste"))
        self.assertEqual(response.status_code, 403)


class FactureDetailViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.eleve = Eleve.objects.get(matricule="202600004")
        cls.frais = FraisScolarite.objects.get(libelle="Trimestre 1")
        cls.facture = Facture.objects.get(eleve=cls.eleve, frais=cls.frais)

    def test_admin_can_record_a_payment(self):
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))

        response = self.client.post(
            reverse("finance:facture_detail", args=[self.facture.pk]),
            {"montant": "5000", "date_paiement": "2026-01-15", "mode_paiement": "ESPECES", "reference": ""},
        )

        self.assertRedirects(response, reverse("finance:facture_detail", args=[self.facture.pk]))
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.PAYEE)

    def test_receipt_pdf_is_downloadable(self):
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))
        paiement = enregistrer_paiement(
            self.facture, Decimal("1000"), datetime.date.today(), Paiement.Mode.ESPECES, "", None,
        )

        response = self.client.get(reverse("finance:recu_pdf", args=[paiement.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_admin_of_another_etablissement_cannot_access_the_facture(self):
        self.assertTrue(self.client.login(username="admin.oran", password=DEMO_PASSWORD))
        response = self.client.get(reverse("finance:facture_detail", args=[self.facture.pk]))
        self.assertEqual(response.status_code, 404)


class TableauBordViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_tableau_bord_shows_expected_and_collected_totals(self):
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))

        response = self.client.get(reverse("finance:tableau_bord"))

        self.assertEqual(response.status_code, 200)
        total_attendu = Facture.objects.filter(
            eleve__user__etablissement=response.wsgi_request.user.etablissement
        ).aggregate(total=Sum("montant"))["total"]
        self.assertContains(response, str(total_attendu))


class MesFraisViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_eleve_sees_their_own_factures(self):
        self.assertTrue(self.client.login(username="eleve.202600001", password=DEMO_PASSWORD))
        response = self.client.get(reverse("finance:mes_frais"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Frais d&#x27;inscription 2025-2026")

    def test_parent_can_switch_between_children(self):
        parent = Parent.objects.get(user__username="parent.benali")
        enfant = parent.enfants.first()
        self.assertTrue(self.client.login(username="parent.benali", password=DEMO_PASSWORD))

        response = self.client.get(reverse("finance:mes_frais"), {"enfant": enfant.pk})

        self.assertEqual(response.status_code, 200)

    def test_non_eleve_non_parent_cannot_access_mes_frais(self):
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))
        response = self.client.get(reverse("finance:mes_frais"))
        self.assertEqual(response.status_code, 403)


class DetecterImpayesCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_marks_overdue_unpaid_factures_and_notifies_parents(self):
        call_command("detecter_impayes")

        facture_impayee = Facture.objects.get(
            eleve=Eleve.objects.get(matricule="202600003"),
            frais__libelle="Frais d'inscription 2025-2026",
        )
        self.assertEqual(facture_impayee.statut, Facture.Statut.EN_RETARD)
        self.assertTrue(len(mail.outbox) > 0)
