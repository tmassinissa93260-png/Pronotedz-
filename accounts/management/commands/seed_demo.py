import datetime

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction

from academics.models import (
    AnneeScolaire,
    Classe,
    CoefficientMatiere,
    Etablissement,
    Filiere,
    Matiere,
    Niveau,
    Salle,
    Trimestre,
)
from accounts.models import Eleve, Enseignant, Parent, PersonnelAdministratif, Utilisateur
from attendance.models import Absence, Seance
from grades.models import Evaluation, Note
from homework.models import CahierDeTexte, Devoir
from timetable.models import CreneauHoraire, EmploiDuTempsEntry

DEMO_PASSWORD = "Pronotedz2026!"

MATIERES = [
    ("Mathématiques", "MATH", "#2f5fa8"),
    ("Physique-Chimie", "PHYS", "#c0392b"),
    ("Français", "FR", "#27ae60"),
    ("Arabe", "AR", "#8e44ad"),
    ("Anglais", "ANG", "#e67e22"),
    ("Histoire-Géographie", "HG", "#16a085"),
]

COEFFICIENTS = {
    "Sciences": {"Mathématiques": 4, "Physique-Chimie": 4, "Français": 2, "Arabe": 2, "Anglais": 2, "Histoire-Géographie": 2},
    "Lettres et Philosophie": {"Mathématiques": 2, "Physique-Chimie": 1, "Français": 4, "Arabe": 4, "Anglais": 3, "Histoire-Géographie": 4},
}


class Command(BaseCommand):
    help = "Crée un jeu de données de démonstration (établissement, classes, comptes, notes, absences...)."

    @transaction.atomic
    def handle(self, *args, **options):
        etablissement = self._make_etablissement()
        annee = self._make_annee_scolaire()
        trimestres = self._make_trimestres(annee)
        etablissement.annee_scolaire_courante = annee
        etablissement.save()

        niveau = Niveau.objects.get_or_create(libelle="1AS", defaults={"cycle": Niveau.Cycle.LYCEE, "ordre": 1})[0]
        filiere_sciences = Filiere.objects.get_or_create(libelle="Sciences")[0]
        filiere_lettres = Filiere.objects.get_or_create(libelle="Lettres et Philosophie")[0]

        matieres = self._make_matieres()
        self._make_coefficients(matieres, niveau, filiere_sciences, filiere_lettres)
        salles = self._make_salles()

        admin_user = self._make_admin()
        enseignants = self._make_enseignants(matieres)

        classe_sciences = Classe.objects.get_or_create(
            libelle="1AS Sciences 1", niveau=niveau, filiere=filiere_sciences, annee_scolaire=annee,
            defaults={"professeur_principal": enseignants["Mathématiques"]},
        )[0]
        classe_lettres = Classe.objects.get_or_create(
            libelle="1AS Lettres 1", niveau=niveau, filiere=filiere_lettres, annee_scolaire=annee,
            defaults={"professeur_principal": enseignants["Français"]},
        )[0]

        creneaux = self._make_creneaux()
        self._make_emploi_du_temps(classe_sciences, classe_lettres, creneaux, matieres, enseignants, salles, annee)

        eleves_sciences = self._make_eleves(classe_sciences, "20260", 1, 6)
        eleves_lettres = self._make_eleves(classe_lettres, "20260", 7, 6)
        self._make_parents(eleves_sciences, eleves_lettres)

        trimestre_actif = trimestres[0]
        self._make_notes(classe_sciences, matieres, enseignants, trimestre_actif, eleves_sciences)
        self._make_notes(classe_lettres, matieres, enseignants, trimestre_actif, eleves_lettres)

        self._make_absences_et_cahier(classe_sciences, annee)

        self.stdout.write(self.style.SUCCESS("Jeu de données de démonstration créé."))
        self.stdout.write(f"Mot de passe commun à tous les comptes de démo : {DEMO_PASSWORD}")
        self.stdout.write(f"Admin : {admin_user.username}")
        self.stdout.write("Enseignants : " + ", ".join(e.user.username for e in enseignants.values()))
        self.stdout.write("Élèves : " + ", ".join(e.user.username for e in eleves_sciences + eleves_lettres))

    # -- Établissement / année / trimestres -------------------------------

    def _make_etablissement(self):
        etablissement = Etablissement.objects.first()
        if not etablissement:
            etablissement = Etablissement.objects.create(
                nom="Lycée Ibn Khaldoun",
                code="LYC-ALG-001",
                adresse="12 rue des Frères Bouadou",
                wilaya="Alger",
                commune="El Biar",
                telephone="021 00 00 00",
                email="contact@ibnkhaldoun-demo.dz",
                type_etablissement=Etablissement.TypeEtablissement.LYCEE,
            )
        return etablissement

    def _make_annee_scolaire(self):
        return AnneeScolaire.objects.get_or_create(
            libelle="2025-2026",
            defaults={
                "date_debut": datetime.date(2025, 9, 1),
                "date_fin": datetime.date(2026, 6, 30),
                "est_active": True,
            },
        )[0]

    def _make_trimestres(self, annee):
        specs = [
            (1, datetime.date(2025, 9, 1), datetime.date(2025, 12, 19), True),
            (2, datetime.date(2026, 1, 4), datetime.date(2026, 3, 20), False),
            (3, datetime.date(2026, 4, 5), datetime.date(2026, 6, 30), False),
        ]
        trimestres = []
        for numero, debut, fin, actif in specs:
            trimestre = Trimestre.objects.get_or_create(
                annee_scolaire=annee, numero=numero,
                defaults={"date_debut": debut, "date_fin": fin, "est_actif": actif},
            )[0]
            trimestres.append(trimestre)
        return trimestres

    # -- Structure pédagogique ---------------------------------------------

    def _make_matieres(self):
        matieres = {}
        for nom, code, couleur in MATIERES:
            matieres[nom] = Matiere.objects.get_or_create(nom=nom, defaults={"code": code, "couleur": couleur})[0]
        return matieres

    def _make_coefficients(self, matieres, niveau, filiere_sciences, filiere_lettres):
        for filiere_libelle, filiere_obj in (("Sciences", filiere_sciences), ("Lettres et Philosophie", filiere_lettres)):
            for nom_matiere, coefficient in COEFFICIENTS[filiere_libelle].items():
                CoefficientMatiere.objects.get_or_create(
                    matiere=matieres[nom_matiere], niveau=niveau, filiere=filiere_obj,
                    defaults={"coefficient": coefficient},
                )

    def _make_salles(self):
        return {
            "Salle 1": Salle.objects.get_or_create(nom="Salle 1")[0],
            "Salle 2": Salle.objects.get_or_create(nom="Salle 2")[0],
            "Labo Physique": Salle.objects.get_or_create(nom="Labo Physique", defaults={"type_salle": "labo"})[0],
        }

    def _make_creneaux(self):
        jours = [CreneauHoraire.Jour.DIMANCHE, CreneauHoraire.Jour.LUNDI, CreneauHoraire.Jour.MARDI,
                 CreneauHoraire.Jour.MERCREDI, CreneauHoraire.Jour.JEUDI]
        horaires = [
            (datetime.time(8, 0), datetime.time(9, 30)),
            (datetime.time(9, 30), datetime.time(11, 0)),
            (datetime.time(11, 0), datetime.time(12, 30)),
            (datetime.time(14, 0), datetime.time(15, 30)),
        ]
        creneaux = []
        for jour in jours:
            for ordre, (debut, fin) in enumerate(horaires, start=1):
                creneau = CreneauHoraire.objects.get_or_create(
                    jour_semaine=jour, ordre=ordre, defaults={"heure_debut": debut, "heure_fin": fin},
                )[0]
                creneaux.append(creneau)
        return creneaux

    # -- Comptes --------------------------------------------------------

    def _make_user(self, username, first_name, last_name, role):
        user, created = Utilisateur.objects.get_or_create(
            username=username,
            defaults={
                "first_name": first_name, "last_name": last_name, "role": role,
                "password": make_password(DEMO_PASSWORD),
            },
        )
        return user

    def _make_admin(self):
        user = self._make_user("admin.direction", "Karim", "Belaid", Utilisateur.Role.ADMIN)
        user.is_staff = True
        user.is_superuser = True
        user.save()
        PersonnelAdministratif.objects.get_or_create(user=user, defaults={"fonction": PersonnelAdministratif.Fonction.DIRECTEUR})
        return user

    def _make_enseignants(self, matieres):
        noms = {
            "Mathématiques": ("Yacine", "Chérif"), "Physique-Chimie": ("Amel", "Ferhat"),
            "Français": ("Sofiane", "Boudiaf"), "Arabe": ("Nadia", "Zerrouki"),
            "Anglais": ("Riad", "Meziane"), "Histoire-Géographie": ("Lynda", "Ouyahia"),
        }
        enseignants = {}
        for nom_matiere, (prenom, nom) in noms.items():
            username = f"prof.{nom_matiere.lower().split('-')[0]}"
            user = self._make_user(username, prenom, nom, Utilisateur.Role.ENSEIGNANT)
            user.is_staff = True
            user.save()
            enseignant = Enseignant.objects.get_or_create(user=user)[0]
            enseignant.matieres_enseignees.add(matieres[nom_matiere])
            enseignants[nom_matiere] = enseignant
        return enseignants

    def _make_eleves(self, classe, prefix, start_index, count):
        prenoms = ["Amina", "Yanis", "Sarah", "Mohamed", "Lina", "Adam", "Rania", "Bilal", "Nour", "Ilyes", "Maya", "Rayan"]
        eleves = []
        for i in range(count):
            index = start_index + i
            matricule = f"{prefix}{index:04d}"
            username = f"eleve.{matricule}"
            prenom = prenoms[(index - 1) % len(prenoms)]
            user = self._make_user(username, prenom, f"Élève{index}", Utilisateur.Role.ELEVE)
            eleve = Eleve.objects.get_or_create(
                user=user, defaults={"classe": classe, "matricule": matricule, "sexe": Eleve.Sexe.M if i % 2 == 0 else Eleve.Sexe.F},
            )[0]
            eleves.append(eleve)
        return eleves

    def _make_parents(self, eleves_sciences, eleves_lettres):
        parent1_user = self._make_user("parent.benali", "Farid", "Benali", Utilisateur.Role.PARENT)
        parent1 = Parent.objects.get_or_create(user=parent1_user)[0]
        parent1.enfants.add(eleves_sciences[0], eleves_lettres[0])

        parent2_user = self._make_user("parent.hamdi", "Samira", "Hamdi", Utilisateur.Role.PARENT)
        parent2 = Parent.objects.get_or_create(user=parent2_user)[0]
        parent2.enfants.add(eleves_sciences[1])

    # -- Emploi du temps --------------------------------------------------

    def _make_emploi_du_temps(self, classe_sciences, classe_lettres, creneaux, matieres, enseignants, salles, annee):
        noms_matieres = list(matieres.keys())
        for i, creneau in enumerate(creneaux):
            matiere_a = noms_matieres[i % 6]
            matiere_b = noms_matieres[(i + 3) % 6]
            self._creer_entree(classe_sciences, matiere_a, creneau, matieres, enseignants, salles, annee, "Salle 1")
            self._creer_entree(classe_lettres, matiere_b, creneau, matieres, enseignants, salles, annee, "Salle 2")

    def _creer_entree(self, classe, nom_matiere, creneau, matieres, enseignants, salles, annee, salle_defaut):
        salle = salles["Labo Physique"] if nom_matiere == "Physique-Chimie" else salles[salle_defaut]
        EmploiDuTempsEntry.objects.get_or_create(
            classe=classe, creneau=creneau, annee_scolaire=annee,
            defaults={"matiere": matieres[nom_matiere], "enseignant": enseignants[nom_matiere], "salle": salle},
        )

    # -- Notes ------------------------------------------------------------

    def _make_notes(self, classe, matieres, enseignants, trimestre, eleves):
        for nom_matiere, matiere in matieres.items():
            evaluation = Evaluation.objects.get_or_create(
                classe=classe, matiere=matiere, trimestre=trimestre, titre="Devoir n°1",
                defaults={
                    "enseignant": enseignants[nom_matiere], "type_evaluation": Evaluation.TypeEvaluation.DEVOIR,
                    "coefficient_evaluation": 1, "date_evaluation": trimestre.date_debut + datetime.timedelta(days=30),
                },
            )[0]
            for i, eleve in enumerate(eleves):
                valeur = 8 + (i * 2) % 12  # spread of values between 8 and 20
                Note.objects.get_or_create(evaluation=evaluation, eleve=eleve, defaults={"valeur": valeur})

    # -- Absences & cahier de texte ----------------------------------------

    def _make_absences_et_cahier(self, classe, annee):
        entry = EmploiDuTempsEntry.objects.filter(classe=classe, annee_scolaire=annee).order_by("creneau__jour_semaine", "creneau__ordre").first()
        if not entry:
            return
        date_seance = datetime.date(2025, 10, 5)
        seance = Seance.get_or_create_for(entry, date_seance)
        eleves = list(classe.eleves.all())
        if eleves:
            Absence.objects.get_or_create(seance=seance, eleve=eleves[0], defaults={"motif": "Maladie", "justifiee": True})
        CahierDeTexte.objects.get_or_create(
            seance=seance, defaults={"contenu": "Introduction au chapitre : fonctions et applications."}
        )
        Devoir.objects.get_or_create(
            seance_donnee=seance, classe=classe, matiere=entry.matiere, enseignant=entry.enseignant,
            date_a_faire_pour=date_seance + datetime.timedelta(days=7),
            defaults={"consigne": "Exercices 3, 5 et 8 page 42 du manuel."},
        )
