import datetime

from django.core.management import call_command
from django.test import TestCase

from academics.models import AnneeScolaire, Classe, Matiere, Niveau, Salle
from accounts.contacts import contacts_autorises
from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Eleve, Enseignant, Utilisateur
from timetable.models import CreneauHoraire, EmploiDuTempsEntry

from .models import Conversation


class ConversationScopingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_user_cannot_access_conversation_they_are_not_part_of(self):
        self.assertTrue(self.client.login(username="parent.hamdi", password=DEMO_PASSWORD))
        conversation = Conversation.objects.get(sujet="Réunion de rentrée")

        response = self.client.get(f"/messagerie/{conversation.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_participant_can_access_and_post_to_their_conversation(self):
        self.assertTrue(self.client.login(username="parent.benali", password=DEMO_PASSWORD))
        conversation = Conversation.objects.get(sujet="Question sur les devoirs")

        response = self.client.get(f"/messagerie/{conversation.pk}/")
        self.assertEqual(response.status_code, 200)

        response = self.client.post(f"/messagerie/{conversation.pk}/", {"contenu": "Merci pour votre retour."})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(conversation.messages.filter(contenu="Merci pour votre retour.").exists())


class ContactsAutorisesTests(TestCase):
    """Isolated fixtures (not seed_demo) so each teacher genuinely teaches only one classe."""

    @classmethod
    def setUpTestData(cls):
        annee = AnneeScolaire.objects.create(libelle="2025-2026", date_debut=datetime.date(2025, 9, 1), date_fin=datetime.date(2026, 6, 30))
        niveau = Niveau.objects.create(libelle="1AS", cycle=Niveau.Cycle.LYCEE, ordre=1)
        cls.classe_a = Classe.objects.create(libelle="Classe A", niveau=niveau, annee_scolaire=annee)
        cls.classe_b = Classe.objects.create(libelle="Classe B", niveau=niveau, annee_scolaire=annee)

        prof_a_user = Utilisateur.objects.create_user(username="prof.a", role=Utilisateur.Role.ENSEIGNANT)
        cls.prof_a = Enseignant.objects.create(user=prof_a_user)

        eleve_a_user = Utilisateur.objects.create_user(username="eleve.a", role=Utilisateur.Role.ELEVE)
        cls.eleve_a = Eleve.objects.create(user=eleve_a_user, classe=cls.classe_a, matricule="A001")

        eleve_b_user = Utilisateur.objects.create_user(username="eleve.b", role=Utilisateur.Role.ELEVE)
        cls.eleve_b = Eleve.objects.create(user=eleve_b_user, classe=cls.classe_b, matricule="B001")

        matiere = Matiere.objects.create(nom="Matière test")
        salle = Salle.objects.create(nom="Salle test")
        creneau = CreneauHoraire.objects.create(jour_semaine=CreneauHoraire.Jour.DIMANCHE, ordre=1, heure_debut="08:00", heure_fin="09:30")
        EmploiDuTempsEntry.objects.create(classe=cls.classe_a, matiere=matiere, enseignant=cls.prof_a, salle=salle, creneau=creneau, annee_scolaire=annee)

    def test_teacher_contacts_exclude_students_of_classes_they_do_not_teach(self):
        contacts = contacts_autorises(self.prof_a.user)
        self.assertIn(self.eleve_a.user, contacts)
        self.assertNotIn(self.eleve_b.user, contacts)

    def test_eleve_contacts_never_include_other_students(self):
        contacts = contacts_autorises(self.eleve_a.user)
        self.assertNotIn(self.eleve_b.user, contacts)
