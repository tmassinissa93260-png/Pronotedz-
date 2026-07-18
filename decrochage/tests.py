import datetime

from django.core.management import call_command
from django.test import TestCase

from academics.models import Matiere
from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Eleve, Enseignant, Utilisateur
from attendance.models import Absence, Retard, Seance
from grades.models import Evaluation, Note
from homework.models import Devoir, RenduDevoir
from notifications.models import Notification
from timetable.models import EmploiDuTempsEntry

from .models import AlerteDecrochage
from .services import SEUIL_ALERTE, calculer_score, calculer_signaux


class SignalDetectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.eleve = Eleve.objects.get(matricule="202600001")
        cls.classe = cls.eleve.classe
        cls.matiere = Matiere.objects.first()
        cls.trimestre = cls.classe.annee_scolaire.trimestres.first()
        cls.enseignant = Enseignant.objects.first()

    def _creer_note(self, valeur, jours_avant):
        evaluation = Evaluation.objects.create(
            classe=self.classe, matiere=self.matiere, enseignant=self.enseignant, trimestre=self.trimestre,
            titre=f"Éval {jours_avant}", date_evaluation=datetime.date.today() - datetime.timedelta(days=jours_avant),
        )
        Note.objects.create(evaluation=evaluation, eleve=self.eleve, valeur=valeur)

    def test_baisse_moyenne_detects_three_consecutive_drops(self):
        self._creer_note(16, jours_avant=20)
        self._creer_note(12, jours_avant=10)
        self._creer_note(8, jours_avant=1)

        signaux = calculer_signaux(self.eleve)
        types = [s["type"] for s in signaux]
        self.assertIn("BAISSE_MOYENNE", types)

    def test_no_signal_when_notes_are_stable(self):
        self._creer_note(14, jours_avant=20)
        self._creer_note(15, jours_avant=10)
        self._creer_note(14, jours_avant=1)

        signaux = calculer_signaux(self.eleve)
        types = [s["type"] for s in signaux]
        self.assertNotIn("BAISSE_MOYENNE", types)

    def test_absences_signal_triggers_at_three_in_two_weeks(self):
        entry = EmploiDuTempsEntry.objects.filter(classe=self.classe).first()
        for jours_avant in (1, 3, 5):
            date = datetime.date.today() - datetime.timedelta(days=jours_avant)
            seance = Seance.get_or_create_for(entry, date)
            Absence.objects.create(seance=seance, eleve=self.eleve)

        signaux = calculer_signaux(self.eleve)
        types = [s["type"] for s in signaux]
        self.assertIn("ABSENCES", types)

    def test_retards_signal_triggers_at_three_in_two_weeks(self):
        for jours_avant in (1, 3, 5):
            Retard.objects.create(
                eleve=self.eleve, date=datetime.date.today() - datetime.timedelta(days=jours_avant),
                heure_arrivee=datetime.time(8, 30), duree_minutes=15,
            )
        signaux = calculer_signaux(self.eleve)
        types = [s["type"] for s in signaux]
        self.assertIn("RETARDS", types)

    def test_devoirs_non_rendus_signal_triggers_at_two_overdue(self):
        entry = EmploiDuTempsEntry.objects.filter(classe=self.classe).first()
        seance = Seance.get_or_create_for(entry, datetime.date.today() - datetime.timedelta(days=10))
        for i in range(2):
            Devoir.objects.create(
                seance_donnee=seance, classe=self.classe, matiere=self.matiere, enseignant=self.enseignant,
                date_a_faire_pour=datetime.date.today() - datetime.timedelta(days=5 - i), consigne=f"Devoir {i}",
            )
        signaux = calculer_signaux(self.eleve)
        types = [s["type"] for s in signaux]
        self.assertIn("DEVOIRS_NON_RENDUS", types)

    def test_rendered_devoir_does_not_count_as_non_rendu(self):
        entry = EmploiDuTempsEntry.objects.filter(classe=self.classe).first()
        seance = Seance.get_or_create_for(entry, datetime.date.today() - datetime.timedelta(days=10))
        devoirs = [
            Devoir.objects.create(
                seance_donnee=seance, classe=self.classe, matiere=self.matiere, enseignant=self.enseignant,
                date_a_faire_pour=datetime.date.today() - datetime.timedelta(days=5 - i), consigne=f"Devoir {i}",
            )
            for i in range(2)
        ]
        RenduDevoir.objects.create(devoir=devoirs[0], eleve=self.eleve, fichier="rendus_devoirs/test.txt")
        RenduDevoir.objects.create(devoir=devoirs[1], eleve=self.eleve, fichier="rendus_devoirs/test2.txt")

        signaux = calculer_signaux(self.eleve)
        types = [s["type"] for s in signaux]
        self.assertNotIn("DEVOIRS_NON_RENDUS", types)

    def test_calculer_score_sums_signal_weights(self):
        signaux = [{"type": "BAISSE_MOYENNE", "description": "x"}, {"type": "ABSENCES", "description": "y"}]
        self.assertEqual(calculer_score(signaux), 5)


class DetectionCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def _rendre_a_risque(self, eleve):
        classe = eleve.classe
        matiere = Matiere.objects.first()
        trimestre = classe.annee_scolaire.trimestres.first()
        enseignant = Enseignant.objects.first()
        for valeur, jours in ((16, 20), (10, 10), (4, 1)):
            evaluation = Evaluation.objects.create(
                classe=classe, matiere=matiere, enseignant=enseignant, trimestre=trimestre,
                titre=f"Éval {jours}", date_evaluation=datetime.date.today() - datetime.timedelta(days=jours),
            )
            Note.objects.create(evaluation=evaluation, eleve=eleve, valeur=valeur)
        entry = EmploiDuTempsEntry.objects.filter(classe=classe).first()
        for jours_avant in (1, 3, 5):
            seance = Seance.get_or_create_for(entry, datetime.date.today() - datetime.timedelta(days=jours_avant))
            Absence.objects.create(seance=seance, eleve=eleve)

    def test_command_creates_alert_and_notifies_admin_and_professeur_principal(self):
        eleve = Eleve.objects.get(matricule="202600001")
        self._rendre_a_risque(eleve)
        professeur_principal = eleve.classe.professeur_principal

        call_command("detecter_decrochage")

        alerte = AlerteDecrochage.objects.get(eleve=eleve)
        self.assertGreaterEqual(alerte.score_risque, SEUIL_ALERTE)
        self.assertEqual(alerte.statut, AlerteDecrochage.Statut.NOUVELLE)

        admin = Utilisateur.objects.get(username="admin.direction")
        self.assertTrue(
            Notification.objects.filter(destinataire=admin, type_notification=Notification.Type.DECROCHAGE).exists()
        )
        if professeur_principal:
            self.assertTrue(
                Notification.objects.filter(
                    destinataire=professeur_principal.user, type_notification=Notification.Type.DECROCHAGE
                ).exists()
            )

    def test_command_does_not_duplicate_open_alerts(self):
        eleve = Eleve.objects.get(matricule="202600001")
        self._rendre_a_risque(eleve)

        call_command("detecter_decrochage")
        call_command("detecter_decrochage")

        self.assertEqual(AlerteDecrochage.objects.filter(eleve=eleve).count(), 1)


class DecrochageViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.eleve = Eleve.objects.get(matricule="202600001")
        cls.alerte = AlerteDecrochage.objects.create(
            eleve=cls.eleve, score_risque=6, signaux=[{"type": "ABSENCES", "description": "3 absences"}],
        )

    def _login(self, username):
        self.assertTrue(self.client.login(username=username, password=DEMO_PASSWORD))

    def test_admin_sees_alert_for_own_etablissement(self):
        self._login("admin.direction")
        response = self.client.get("/decrochage/")
        self.assertContains(response, self.eleve.user.get_full_name())

    def test_admin_of_other_etablissement_gets_404_on_detail(self):
        self._login("admin.oran")
        response = self.client.get(f"/decrochage/{self.alerte.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_eleve_role_cannot_access(self):
        self._login("eleve.202600001")
        response = self.client.get("/decrochage/")
        self.assertEqual(response.status_code, 403)

    def test_professeur_principal_sees_only_their_classe(self):
        professeur_principal = self.eleve.classe.professeur_principal
        if professeur_principal is None:
            self.skipTest("Aucun professeur principal configuré pour cette classe dans les données de démo.")
        self._login(professeur_principal.user.username)
        response = self.client.get("/decrochage/")
        self.assertContains(response, self.eleve.user.get_full_name())

    def test_updating_statut_persists_and_records_traite_par(self):
        self._login("admin.direction")
        response = self.client.post(
            f"/decrochage/{self.alerte.pk}/", {"statut": "EN_COURS", "notes_suivi": "Contact pris avec la famille."}
        )
        self.assertRedirects(response, f"/decrochage/{self.alerte.pk}/")
        self.alerte.refresh_from_db()
        self.assertEqual(self.alerte.statut, AlerteDecrochage.Statut.EN_COURS)
        self.assertEqual(self.alerte.notes_suivi, "Contact pris avec la famille.")
