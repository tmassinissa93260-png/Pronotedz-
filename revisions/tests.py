import datetime

from django.core.management import call_command
from django.test import TestCase

from academics.models import Matiere
from accounts.management.commands.seed_demo import DEMO_PASSWORD
from accounts.models import Eleve

from .models import DateExamen, ProgrammeChapitre, ProgressionChapitre
from .services import chapitres_avec_statut, est_classe_examen, generer_planning, progression_par_matiere


class ServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")
        cls.eleve_examen = Eleve.objects.get(matricule="202630001")
        cls.eleve_normal = Eleve.objects.get(matricule="202600001")

    def test_est_classe_examen_true_for_3as(self):
        self.assertTrue(est_classe_examen(self.eleve_examen))

    def test_est_classe_examen_false_for_1as(self):
        self.assertFalse(est_classe_examen(self.eleve_normal))

    def test_chapitres_avec_statut_reflects_seeded_progress(self):
        lignes = chapitres_avec_statut(self.eleve_examen)
        self.assertTrue(any(l["statut"] == ProgressionChapitre.Statut.MAITRISE for l in lignes))
        self.assertTrue(any(l["statut"] == ProgressionChapitre.Statut.A_FAIRE for l in lignes))

    def test_progression_par_matiere_computes_percentage(self):
        lignes = chapitres_avec_statut(self.eleve_examen)
        stats = progression_par_matiere(lignes)
        maths = Matiere.objects.get(nom="Mathématiques")
        self.assertIn(maths, stats)
        self.assertGreater(stats[maths]["total"], 0)
        self.assertGreaterEqual(stats[maths]["pourcentage"], 0)
        self.assertLessEqual(stats[maths]["pourcentage"], 100)

    def test_generer_planning_excludes_mastered_chapters(self):
        planning = generer_planning(self.eleve_examen)
        chapitres_du_planning = [c for semaine in planning for c in semaine]
        maitrises = ProgressionChapitre.objects.filter(eleve=self.eleve_examen, statut=ProgressionChapitre.Statut.MAITRISE)
        for progression in maitrises:
            self.assertNotIn(progression.chapitre, chapitres_du_planning)

    def test_generer_planning_returns_empty_without_date_examen(self):
        DateExamen.objects.filter(niveau=self.eleve_examen.classe.niveau).delete()
        planning = generer_planning(self.eleve_examen)
        self.assertEqual(planning, [])

    def test_planning_distributes_across_multiple_weeks(self):
        DateExamen.objects.filter(niveau=self.eleve_examen.classe.niveau).update(
            date_examen=datetime.date.today() + datetime.timedelta(days=21)
        )
        planning = generer_planning(self.eleve_examen)
        self.assertGreaterEqual(len(planning), 2)


class ViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo")

    def _login(self, username):
        self.assertTrue(self.client.login(username=username, password=DEMO_PASSWORD))

    def test_exam_class_student_can_access(self):
        self._login("eleve.202630001")
        response = self.client.get("/revisions/")
        self.assertEqual(response.status_code, 200)

    def test_non_exam_class_student_gets_403(self):
        self._login("eleve.202600001")
        response = self.client.get("/revisions/")
        self.assertEqual(response.status_code, 403)

    def test_non_eleve_role_gets_403(self):
        self._login("prof.mathématiques")
        response = self.client.get("/revisions/")
        self.assertEqual(response.status_code, 403)

    def test_updating_chapitre_statut_persists(self):
        self._login("eleve.202630001")
        eleve = Eleve.objects.get(matricule="202630001")
        chapitre = ProgrammeChapitre.objects.filter(niveau=eleve.classe.niveau).first()

        response = self.client.post(
            "/revisions/", {"chapitre_id": chapitre.pk, "statut": ProgressionChapitre.Statut.EN_COURS}
        )
        self.assertRedirects(response, "/revisions/")
        progression = ProgressionChapitre.objects.get(eleve=eleve, chapitre=chapitre)
        self.assertEqual(progression.statut, ProgressionChapitre.Statut.EN_COURS)

    def test_student_cannot_update_chapitre_of_a_different_niveau(self):
        from academics.models import Niveau

        self._login("eleve.202630001")
        autre_niveau = Niveau.objects.exclude(libelle="3AS").first()
        chapitre_autre_niveau = ProgrammeChapitre.objects.create(niveau=autre_niveau, matiere=Matiere.objects.first(), ordre=99, titre="Hors niveau")

        response = self.client.post("/revisions/", {"chapitre_id": chapitre_autre_niveau.pk, "statut": "MAITRISE"})
        self.assertEqual(response.status_code, 404)
