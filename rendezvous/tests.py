import datetime

from django.core.management import call_command
from django.test import TestCase

from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Eleve

from .models import DisponibiliteRDV, RendezVous


class RendezVousScopingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_parent_cannot_book_rdv_for_a_child_that_is_not_theirs(self):
        self.assertTrue(self.client.login(username="parent.hamdi", password=DEMO_PASSWORD))
        autre_enfant = Eleve.objects.get(matricule="202600001")  # belongs to parent.benali
        disponibilite_libre = DisponibiliteRDV.objects.filter(rendez_vous__isnull=True).first()

        response = self.client.post(
            f"/rendez-vous/reserver/{disponibilite_libre.pk}/",
            {"enfant": autre_enfant.pk, "motif": "test"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(RendezVous.objects.filter(disponibilite=disponibilite_libre).exists())

    def test_cannot_double_book_the_same_slot(self):
        self.assertTrue(self.client.login(username="parent.benali", password=DEMO_PASSWORD))
        enfant = Eleve.objects.get(matricule="202600001")
        disponibilite_libre = DisponibiliteRDV.objects.filter(rendez_vous__isnull=True).first()

        response1 = self.client.post(
            f"/rendez-vous/reserver/{disponibilite_libre.pk}/", {"enfant": enfant.pk, "motif": "premier"}
        )
        self.assertEqual(response1.status_code, 302)

        response2 = self.client.post(
            f"/rendez-vous/reserver/{disponibilite_libre.pk}/", {"enfant": enfant.pk, "motif": "deuxieme"}
        )
        self.assertEqual(response2.status_code, 404)
        self.assertEqual(RendezVous.objects.filter(disponibilite=disponibilite_libre).count(), 1)

    def test_parent_can_cancel_own_rdv_freeing_the_slot(self):
        self.assertTrue(self.client.login(username="parent.benali", password=DEMO_PASSWORD))
        rdv = RendezVous.objects.get(eleve_concerne__matricule="202600001")
        disponibilite = rdv.disponibilite

        response = self.client.post(f"/rendez-vous/annuler/{rdv.pk}/")
        self.assertEqual(response.status_code, 302)
        disponibilite.refresh_from_db()
        self.assertFalse(disponibilite.est_reservee)
