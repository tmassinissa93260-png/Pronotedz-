import datetime

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from academics.models import Matiere
from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Eleve, Enseignant, Parent, Utilisateur
from attendance.models import Absence, Seance
from grades.models import Evaluation, Note
from homework.models import Devoir
from timetable.models import EmploiDuTempsEntry

from .services import construire_rapport


class ConstruireRapportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.eleve = Eleve.objects.get(matricule="202600001")
        cls.classe = cls.eleve.classe
        cls.matiere = Matiere.objects.get(nom="Mathématiques")
        cls.trimestre = cls.classe.annee_scolaire.trimestres.first()
        cls.enseignant = Enseignant.objects.filter(matieres_enseignees=cls.matiere).first()
        cls.aujourdhui = datetime.date.today()

    def _creer_note(self, valeur, jours_avant):
        evaluation = Evaluation.objects.create(
            classe=self.classe, matiere=self.matiere, enseignant=self.enseignant, trimestre=self.trimestre,
            titre="Contrôle", date_evaluation=self.aujourdhui - datetime.timedelta(days=jours_avant),
        )
        Note.objects.create(evaluation=evaluation, eleve=self.eleve, valeur=valeur)

    def _creer_absence(self, jours_avant):
        entry = EmploiDuTempsEntry.objects.filter(classe=self.classe).first()
        seance = Seance.get_or_create_for(entry, self.aujourdhui - datetime.timedelta(days=jours_avant))
        Absence.objects.create(seance=seance, eleve=self.eleve)

    def _creer_devoir(self, jours_apres):
        entry = EmploiDuTempsEntry.objects.filter(classe=self.classe).first()
        seance = Seance.get_or_create_for(entry, self.aujourdhui)
        Devoir.objects.create(
            seance_donnee=seance, classe=self.classe, matiere=self.matiere, enseignant=self.enseignant,
            date_a_faire_pour=self.aujourdhui + datetime.timedelta(days=jours_apres), consigne="Réviser le chapitre",
        )

    def test_rapport_fr_contient_les_notes_absences_et_devoirs(self):
        self._creer_note(15, jours_avant=2)
        self._creer_absence(jours_avant=1)
        self._creer_devoir(jours_apres=3)

        sujet, corps = construire_rapport(self.eleve, langue="fr", aujourdhui=self.aujourdhui)

        self.assertIn(self.eleve.user.get_full_name(), sujet)
        self.assertIn("Mathématiques : 15", corps)
        self.assertIn("Absences de la semaine", corps)
        self.assertIn("Devoirs à venir", corps)

    def test_rapport_ar_utilise_les_textes_arabes(self):
        self._creer_note(15, jours_avant=2)

        sujet, corps = construire_rapport(self.eleve, langue="ar", aujourdhui=self.aujourdhui)

        self.assertIn("التقرير الأسبوعي", sujet)
        self.assertIn("علامات الأسبوع", corps)

    def test_rapport_sans_donnees_affiche_les_messages_par_defaut(self):
        sujet, corps = construire_rapport(self.eleve, langue="fr", aujourdhui=self.aujourdhui)

        self.assertIn("Aucune note publiée cette semaine.", corps)
        self.assertIn("Aucune absence cette semaine.", corps)
        self.assertIn("Aucun devoir à rendre dans les 7 prochains jours.", corps)

    def test_notes_hors_de_la_fenetre_de_sept_jours_sont_exclues(self):
        self._creer_note(10, jours_avant=15)

        _, corps = construire_rapport(self.eleve, langue="fr", aujourdhui=self.aujourdhui)

        self.assertIn("Aucune note publiée cette semaine.", corps)

    def test_langue_inconnue_retombe_sur_le_francais(self):
        sujet, _ = construire_rapport(self.eleve, langue="es", aujourdhui=self.aujourdhui)

        self.assertIn("Rapport hebdomadaire", sujet)


class EnvoyerRapportsHebdomadairesCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_envoie_un_email_par_enfant_et_par_parent(self):
        nb_attendu = sum(parent.enfants.count() for parent in Parent.objects.all())

        call_command("envoyer_rapports_hebdomadaires")

        self.assertEqual(len(mail.outbox), nb_attendu)
        self.assertGreater(nb_attendu, 0)

    def test_respecte_la_langue_preferee_du_parent(self):
        parent = Parent.objects.get(user__username="parent.benali")
        parent.user.langue_notifications = Utilisateur.LangueNotifications.ARABE
        parent.user.save(update_fields=["langue_notifications"])

        call_command("envoyer_rapports_hebdomadaires")

        emails_parent = [m for m in mail.outbox if m.to == [parent.user.email]]
        self.assertTrue(emails_parent)
        for message in emails_parent:
            self.assertIn("التقرير الأسبوعي", message.subject)


class PreferencesNotificationsViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def setUp(self):
        self.parent = Parent.objects.get(user__username="parent.benali")
        self.url = reverse("rapport_parent:preferences_notifications")

    def test_get_affiche_le_formulaire_pour_un_parent(self):
        self.client.login(username="parent.benali", password=DEMO_PASSWORD)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Langue du rapport hebdomadaire")

    def test_post_enregistre_la_langue_choisie(self):
        self.client.login(username="parent.benali", password=DEMO_PASSWORD)
        response = self.client.post(self.url, {"langue_notifications": "ar"})

        self.assertRedirects(response, self.url)
        self.parent.user.refresh_from_db()
        self.assertEqual(self.parent.user.langue_notifications, "ar")

    def test_valeur_invalide_est_ignoree(self):
        self.client.login(username="parent.benali", password=DEMO_PASSWORD)
        self.client.post(self.url, {"langue_notifications": "xx"})

        self.parent.user.refresh_from_db()
        self.assertEqual(self.parent.user.langue_notifications, "fr")

    def test_role_non_parent_recoit_un_403(self):
        eleve = Eleve.objects.get(matricule="202600001")
        self.client.login(username=eleve.user.username, password=DEMO_PASSWORD)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)
