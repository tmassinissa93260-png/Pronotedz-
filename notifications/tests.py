from django.core import mail
from django.core.management import call_command
from django.test import TestCase

from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Eleve, Utilisateur

from .models import Notification
from .services import notifier


class NotifierServiceTests(TestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            username="test.notif", role=Utilisateur.Role.ELEVE, email="eleve@example.com"
        )

    def test_notifier_creates_notification_and_sends_email(self):
        notifier(self.user, Notification.Type.INFO, titre="Titre test", contenu="Contenu test")

        self.assertEqual(Notification.objects.filter(destinataire=self.user).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Titre test", mail.outbox[0].subject)

    def test_notifier_skips_email_when_user_has_no_address(self):
        user_sans_email = Utilisateur.objects.create_user(username="sans.email", role=Utilisateur.Role.ELEVE)
        notifier(user_sans_email, Notification.Type.INFO, titre="Titre")

        self.assertEqual(Notification.objects.filter(destinataire=user_sans_email).count(), 1)
        self.assertEqual(len(mail.outbox), 0)


class NotificationTriggerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_marking_absence_notifies_parent(self):
        from timetable.models import EmploiDuTempsEntry

        Notification.objects.all().delete()
        eleve = Eleve.objects.get(matricule="202600001")  # child of parent.benali
        entry = EmploiDuTempsEntry.objects.filter(classe=eleve.classe).first()

        self.assertTrue(self.client.login(username=entry.enseignant.user.username, password=DEMO_PASSWORD))
        self.client.post(
            f"/absences/appel/{entry.pk}/?date=2026-01-04",
            {"date": "2026-01-04", "absent": [str(eleve.pk)]},
        )

        parent_notifs = Notification.objects.filter(destinataire=eleve.parents.first().user, type_notification=Notification.Type.ABSENCE)
        self.assertTrue(parent_notifs.exists())

    def test_sending_message_notifies_other_participants(self):
        from messaging.models import Conversation

        Notification.objects.all().delete()
        conversation = Conversation.objects.get(sujet="Question sur les devoirs")  # parent.benali <-> prof.mathématiques
        prof_user = conversation.participants.exclude(pk=conversation.createur_id).first()

        self.assertTrue(self.client.login(username="parent.benali", password=DEMO_PASSWORD))
        self.client.post(f"/messagerie/{conversation.pk}/", {"contenu": "Un nouveau message."})

        self.assertTrue(Notification.objects.filter(destinataire=prof_user, type_notification=Notification.Type.MESSAGE).exists())

    def test_publishing_evaluation_notifies_graded_students(self):
        from grades.models import Evaluation

        Notification.objects.all().delete()
        evaluation = Evaluation.objects.filter(matiere__nom="Mathématiques", classe__libelle="1AS Sciences 1").first()
        evaluation.publie = False
        evaluation.save()

        self.assertTrue(self.client.login(username=evaluation.enseignant.user.username, password=DEMO_PASSWORD))
        response = self.client.post(f"/notes/evaluations/{evaluation.pk}/publier/")
        self.assertEqual(response.status_code, 302)

        eleve_note = evaluation.notes.filter(valeur__isnull=False).first()
        self.assertTrue(
            Notification.objects.filter(destinataire=eleve_note.eleve.user, type_notification=Notification.Type.NOTE).exists()
        )

    def test_user_cannot_mark_another_users_notification_as_read(self):
        notification = Notification.objects.create(
            destinataire=Utilisateur.objects.get(username="eleve.202600001"), titre="Privée",
        )
        self.assertTrue(self.client.login(username="eleve.202600002", password=DEMO_PASSWORD))

        response = self.client.get(f"/notifications/{notification.pk}/lu/")
        self.assertEqual(response.status_code, 404)
        notification.refresh_from_db()
        self.assertFalse(notification.lu)
