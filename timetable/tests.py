import datetime

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from academics.models import Matiere, Salle
from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Enseignant, Utilisateur
from attendance.models import Seance
from notifications.models import Notification

from .models import CreneauHoraire, EmploiDuTempsEntry
from .services import suggerer_remplacants


def _prochain_jour_ouvre():
    """Any date matching a créneau created by seed_demo (Dimanche-Jeudi —
    Python weekday() 6, 0, 1, 2, 3 — Vendredi/Samedi are skipped)."""
    date = datetime.date.today()
    while date.weekday() in (4, 5):
        date += datetime.timedelta(days=1)
    return date


class EmploiDuTempsEntryCleanTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_clean_passes_without_conflict(self):
        entry = EmploiDuTempsEntry.objects.first()
        entry.full_clean()  # no exception

    def test_clean_detects_classe_conflict(self):
        existant = EmploiDuTempsEntry.objects.select_related("classe", "creneau", "annee_scolaire").first()
        autre_matiere = Matiere.objects.exclude(pk=existant.matiere_id).first()
        autre_enseignant = Enseignant.objects.filter(matieres_enseignees=autre_matiere).first()
        autre_salle = Salle.objects.exclude(pk=existant.salle_id).first()

        conflit = EmploiDuTempsEntry(
            classe=existant.classe, matiere=autre_matiere, enseignant=autre_enseignant,
            salle=autre_salle, creneau=existant.creneau, annee_scolaire=existant.annee_scolaire,
        )
        with self.assertRaises(ValidationError) as ctx:
            conflit.full_clean()
        self.assertIn("a déjà un cours à ce créneau", str(ctx.exception))

    def test_clean_detects_enseignant_conflict(self):
        existant = EmploiDuTempsEntry.objects.select_related("classe", "creneau", "annee_scolaire").first()
        autre_classe = EmploiDuTempsEntry.objects.exclude(classe=existant.classe).first().classe
        autre_salle = Salle.objects.exclude(pk=existant.salle_id).first()

        conflit = EmploiDuTempsEntry(
            classe=autre_classe, matiere=existant.matiere, enseignant=existant.enseignant,
            salle=autre_salle, creneau=existant.creneau, annee_scolaire=existant.annee_scolaire,
        )
        with self.assertRaises(ValidationError):
            conflit.full_clean()


class SuggererRemplacantsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.entry = EmploiDuTempsEntry.objects.select_related("matiere", "creneau", "annee_scolaire").first()

    def test_no_candidates_when_no_other_teacher_teaches_the_subject(self):
        candidats = suggerer_remplacants(self.entry)
        self.assertEqual(list(candidats), [])

    def test_free_teacher_of_the_same_subject_is_suggested(self):
        remplacant_user = Utilisateur.objects.create_user(
            username="prof.remplacant", first_name="Kamel", last_name="Aitali",
            role=Utilisateur.Role.ENSEIGNANT, etablissement=self.entry.annee_scolaire.etablissement,
        )
        remplacant = Enseignant.objects.create(user=remplacant_user)
        remplacant.matieres_enseignees.add(self.entry.matiere)

        candidats = suggerer_remplacants(self.entry)

        self.assertIn(remplacant, list(candidats))

    def test_teacher_busy_at_the_same_creneau_is_excluded(self):
        autre_entry = EmploiDuTempsEntry.objects.filter(creneau=self.entry.creneau).exclude(pk=self.entry.pk).first()
        autre_entry.enseignant.matieres_enseignees.add(self.entry.matiere)

        candidats = suggerer_remplacants(self.entry)

        self.assertNotIn(autre_entry.enseignant, list(candidats))


class RemplacementViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.date = _prochain_jour_ouvre()
        jour_semaine = CreneauHoraire.PYTHON_WEEKDAY_TO_JOUR[cls.date.weekday()]
        cls.entry = EmploiDuTempsEntry.objects.filter(creneau__jour_semaine=jour_semaine).select_related("matiere").first()

        remplacant_user = Utilisateur.objects.create_user(
            username="prof.remplacant", first_name="Kamel", last_name="Aitali",
            role=Utilisateur.Role.ENSEIGNANT, etablissement=cls.entry.annee_scolaire.etablissement,
        )
        cls.remplacant = Enseignant.objects.create(user=remplacant_user)
        cls.remplacant.matieres_enseignees.add(cls.entry.matiere)

    def test_remplacements_jour_lists_entries_for_that_day(self):
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))

        response = self.client.get(reverse("timetable:remplacements_jour"), {"date": self.date.isoformat()})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(self.entry.classe))

    def test_non_admin_cannot_access_remplacements_jour(self):
        self.assertTrue(self.client.login(username="eleve.202600001", password=DEMO_PASSWORD))
        response = self.client.get(reverse("timetable:remplacements_jour"))
        self.assertEqual(response.status_code, 403)

    def test_assigner_remplacant_updates_seance_and_notifies_eleves(self):
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))

        response = self.client.post(
            reverse("timetable:remplacement_assigner", args=[self.entry.pk, self.date.isoformat()]),
            {"enseignant": self.remplacant.pk},
        )

        self.assertRedirects(
            response, f"{reverse('timetable:remplacements_jour')}?date={self.date.isoformat()}"
        )
        seance = Seance.objects.get(emploi_du_temps_entry=self.entry, date=self.date)
        self.assertEqual(seance.enseignant_remplacant, self.remplacant)
        self.assertEqual(seance.statut, Seance.Statut.REMPLACEE)
        self.assertTrue(
            Notification.objects.filter(
                destinataire__eleve__classe=self.entry.classe, type_notification=Notification.Type.REMPLACEMENT,
            ).exists()
        )

    def test_annuler_remplacement_reverts_seance(self):
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))
        seance = Seance.get_or_create_for(self.entry, self.date)
        seance.enseignant_remplacant = self.remplacant
        seance.statut = Seance.Statut.REMPLACEE
        seance.save()

        response = self.client.get(reverse("timetable:remplacement_annuler", args=[seance.pk]))

        self.assertRedirects(
            response, f"{reverse('timetable:remplacements_jour')}?date={self.date.isoformat()}"
        )
        seance.refresh_from_db()
        self.assertIsNone(seance.enseignant_remplacant)
        self.assertEqual(seance.statut, Seance.Statut.NORMALE)

    def test_admin_of_another_etablissement_cannot_assign_a_replacement(self):
        self.assertTrue(self.client.login(username="admin.oran", password=DEMO_PASSWORD))

        response = self.client.get(
            reverse("timetable:remplacement_assigner", args=[self.entry.pk, self.date.isoformat()])
        )

        self.assertEqual(response.status_code, 404)
