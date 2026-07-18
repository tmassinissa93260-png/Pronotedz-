import datetime
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from academics.models import Matiere
from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Eleve, Enseignant, Utilisateur
from attendance.models import Retard, Seance
from grades.models import Evaluation, Note
from homework.models import Devoir
from timetable.models import EmploiDuTempsEntry

from .models import WorkflowExecution, WorkflowRegle
from .services import evaluer_devoirs_non_rendus, evaluer_notes_basses, evaluer_retards_frequents, executer_toutes_les_regles


class NotesBassesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.regle = WorkflowRegle.objects.get(nom="Alerte note basse")

    def test_declenche_pour_les_notes_sous_le_seuil(self):
        nb = evaluer_notes_basses(self.regle)

        self.assertGreater(nb, 0)
        self.assertTrue(WorkflowExecution.objects.filter(regle=self.regle).exists())

    def test_ne_redeclenche_pas_pour_la_meme_note(self):
        evaluer_notes_basses(self.regle)
        nb_second_appel = evaluer_notes_basses(self.regle)

        self.assertEqual(nb_second_appel, 0)

    def test_ignore_les_notes_egales_au_seuil(self):
        eleve = Eleve.objects.get(matricule="202600001")
        matiere = Matiere.objects.get(nom="Mathématiques")
        enseignant = Enseignant.objects.filter(matieres_enseignees=matiere).first()
        trimestre = eleve.classe.annee_scolaire.trimestres.first()
        evaluation = Evaluation.objects.create(
            classe=eleve.classe, matiere=matiere, enseignant=enseignant, trimestre=trimestre,
            titre="Contrôle au seuil", date_evaluation=datetime.date.today(),
        )
        note = Note.objects.create(evaluation=evaluation, eleve=eleve, valeur=self.regle.seuil)

        evaluer_notes_basses(self.regle)

        self.assertFalse(WorkflowExecution.objects.filter(regle=self.regle, cle_unicite=f"note-{note.pk}").exists())


class RetardsFrequentsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.regle = WorkflowRegle.objects.get(nom="Retards fréquents")
        cls.eleve = Eleve.objects.get(matricule="202600001")

    def _creer_retards(self, nombre):
        aujourdhui = datetime.date.today()
        for i in range(nombre):
            Retard.objects.create(
                eleve=self.eleve, date=aujourdhui - datetime.timedelta(days=i),
                heure_arrivee=datetime.time(8, 15), duree_minutes=10,
            )

    def test_declenche_a_partir_du_seuil(self):
        self._creer_retards(3)

        nb = evaluer_retards_frequents(self.regle)

        self.assertEqual(nb, 1)

    def test_ne_declenche_pas_sous_le_seuil(self):
        self._creer_retards(2)

        nb = evaluer_retards_frequents(self.regle)

        self.assertEqual(nb, 0)

    def test_ne_redeclenche_pas_la_meme_semaine(self):
        self._creer_retards(3)
        evaluer_retards_frequents(self.regle)

        nb_second_appel = evaluer_retards_frequents(self.regle)

        self.assertEqual(nb_second_appel, 0)


class DevoirsNonRendusTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.regle = WorkflowRegle.objects.get_or_create(
            etablissement=Eleve.objects.get(matricule="202600001").user.etablissement,
            nom="Devoirs non rendus",
            defaults={
                "declencheur": WorkflowRegle.Declencheur.DEVOIR_NON_RENDU, "seuil": Decimal("2"),
                "destinataire": WorkflowRegle.Destinataire.PARENT,
                "message": "{eleve} n'a pas rendu le devoir de {devoir}.",
            },
        )[0]

    def test_declenche_pour_chaque_eleve_sans_rendu(self):
        eleve = Eleve.objects.get(matricule="202600001")
        entry = EmploiDuTempsEntry.objects.filter(classe=eleve.classe).select_related("matiere", "enseignant").first()
        seance = Seance.get_or_create_for(entry, datetime.date.today() - datetime.timedelta(days=10))
        devoir = Devoir.objects.create(
            seance_donnee=seance, classe=eleve.classe, matiere=entry.matiere, enseignant=entry.enseignant,
            date_a_faire_pour=datetime.date.today() - datetime.timedelta(days=5), consigne="Exercices 1 à 4",
        )

        nb = evaluer_devoirs_non_rendus(self.regle)

        self.assertGreater(nb, 0)
        self.assertTrue(WorkflowExecution.objects.filter(regle=self.regle, cle_unicite=f"devoir-{devoir.pk}").exists())


class ExecuterToutesLesReglesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_ignore_les_regles_inactives(self):
        WorkflowRegle.objects.update(actif=False)

        nb = executer_toutes_les_regles()

        self.assertEqual(nb, 0)

    def test_commande_de_management_execute_les_regles(self):
        from io import StringIO

        out = StringIO()
        call_command("executer_workflows", stdout=out)

        self.assertIn("déclenchement", out.getvalue())


class WorkflowAdminScopingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def test_admin_ne_voit_que_les_regles_de_son_etablissement(self):
        self.assertTrue(self.client.login(username="admin.direction", password=DEMO_PASSWORD))

        response = self.client.get(reverse("admin:workflows_workflowregle_changelist"))

        self.assertContains(response, "Alerte note basse")

    def test_admin_dun_autre_etablissement_ne_voit_pas_les_regles(self):
        self.assertTrue(self.client.login(username="admin.oran", password=DEMO_PASSWORD))

        response = self.client.get(reverse("admin:workflows_workflowregle_changelist"))

        self.assertNotContains(response, "Alerte note basse")
