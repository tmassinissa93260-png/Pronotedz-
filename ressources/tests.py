from django.core.management import call_command
from django.test import TestCase

from accounts.management.commands.seed_demo import DEMO_PASSWORD

from .models import Reservation, Ressource


class ReservationDoubleBookingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_cannot_double_book_the_same_ressource_creneau(self):
        reservation_existante = Reservation.objects.first()
        self.assertTrue(self.client.login(username="prof.mathématiques", password=DEMO_PASSWORD))

        response = self.client.post(
            "/ressources/nouvelle/",
            {
                "date": reservation_existante.date.isoformat(),
                "creneau": reservation_existante.creneau_id,
                "ressource": reservation_existante.ressource_id,
                "motif": "conflit",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Reservation.objects.filter(ressource=reservation_existante.ressource, date=reservation_existante.date, creneau=reservation_existante.creneau).count(),
            1,
        )

    def test_teacher_can_reserve_a_free_slot(self):
        self.assertTrue(self.client.login(username="prof.arabe", password=DEMO_PASSWORD))
        ressource = Ressource.objects.get(nom="Salle informatique")
        reservation_existante = Reservation.objects.first()

        response = self.client.post(
            "/ressources/nouvelle/",
            {
                "date": reservation_existante.date.isoformat(),
                "creneau": reservation_existante.creneau_id,
                "ressource": ressource.pk,
                "motif": "cours d'info",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Reservation.objects.filter(ressource=ressource).exists())
