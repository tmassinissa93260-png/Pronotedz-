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
from actualites.models import Publication
from attendance.models import Absence, Seance
from documents.models import Document
from grades.models import Evaluation, Note
from homework.models import CahierDeTexte, Devoir
from messaging.models import Conversation, Message
from rendezvous.models import DisponibiliteRDV, RendezVous
from ressources.models import Reservation, Ressource
from sondages.models import ChoixReponse, QuestionSondage, Sondage
from timetable.models import CreneauHoraire, EmploiDuTempsEntry
from vie_scolaire.models import Observation

DEMO_PASSWORD = "Pronotedz2026!"

MATIERES = [
    ("Mathématiques", "MATH", "#f3c9a3"),
    ("Physique-Chimie", "PHYS", "#cba3d8"),
    ("Français", "FR", "#b8b0e8"),
    ("Arabe", "AR", "#a8d99a"),
    ("Anglais", "ANG", "#e3d7ad"),
    ("Histoire-Géographie", "HG", "#9adcdc"),
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
        parent_benali, parent_hamdi = self._make_parents(eleves_sciences, eleves_lettres)

        trimestre_actif = trimestres[0]
        self._make_notes(classe_sciences, matieres, enseignants, trimestre_actif, eleves_sciences)
        self._make_notes(classe_lettres, matieres, enseignants, trimestre_actif, eleves_lettres)

        self._make_absences_et_cahier(classe_sciences, annee)

        self._make_messagerie(admin_user, enseignants, parent_benali)
        self._make_vie_scolaire(eleves_sciences, enseignants)
        self._make_actualites(admin_user)
        self._make_rendezvous(enseignants, parent_benali, eleves_sciences)
        self._make_ressources(enseignants)
        self._make_documents(admin_user, enseignants, classe_sciences)
        self._make_sondages(admin_user)

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

        return parent1, parent2

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

    # -- Messagerie ---------------------------------------------------------

    def _make_messagerie(self, admin_user, enseignants, parent_benali):
        prof_maths = enseignants["Mathématiques"].user
        conversation, created = Conversation.objects.get_or_create(
            sujet="Réunion de rentrée", createur=admin_user,
        )
        if created:
            conversation.participants.add(admin_user, prof_maths)
            Message.objects.create(conversation=conversation, expediteur=admin_user, contenu="Bonjour, la réunion de rentrée aura lieu jeudi à 14h en salle des professeurs.")
            Message.objects.create(conversation=conversation, expediteur=prof_maths, contenu="Bien reçu, merci !")

        conversation2, created2 = Conversation.objects.get_or_create(
            sujet="Question sur les devoirs", createur=parent_benali.user,
        )
        if created2:
            conversation2.participants.add(parent_benali.user, prof_maths)
            Message.objects.create(conversation=conversation2, expediteur=parent_benali.user, contenu="Bonjour, quels exercices pour la semaine prochaine ?")

    # -- Vie scolaire ---------------------------------------------------------

    def _make_vie_scolaire(self, eleves_sciences, enseignants):
        Observation.objects.get_or_create(
            eleve=eleves_sciences[2], type_observation=Observation.TypeObservation.ENCOURAGEMENT,
            motif="Excellent travail", date=datetime.date(2025, 10, 10),
            defaults={"description": "Participation active en classe.", "saisie_par": enseignants["Mathématiques"].user, "matiere": None},
        )

    # -- Actualités -----------------------------------------------------------

    def _make_actualites(self, admin_user):
        Publication.objects.get_or_create(
            titre="Rentrée scolaire 2025-2026", auteur=admin_user,
            defaults={"contenu": "Toute l'équipe pédagogique vous souhaite une excellente rentrée !", "audience": Publication.Audience.TOUS, "epingle": True},
        )
        Publication.objects.get_or_create(
            titre="Réunion parents-professeurs", auteur=admin_user,
            defaults={"contenu": "Une réunion parents-professeurs est organisée le mois prochain.", "audience": Publication.Audience.ELEVES_PARENTS},
        )

    # -- Rendez-vous ---------------------------------------------------------

    def _make_rendezvous(self, enseignants, parent_benali, eleves_sciences):
        prof_maths = enseignants["Mathématiques"]
        dispo_libre = DisponibiliteRDV.objects.get_or_create(
            enseignant=prof_maths, date=datetime.date(2026, 9, 15), heure_debut=datetime.time(17, 0),
            defaults={"heure_fin": datetime.time(17, 20)},
        )[0]
        dispo_reservee = DisponibiliteRDV.objects.get_or_create(
            enseignant=prof_maths, date=datetime.date(2026, 9, 15), heure_debut=datetime.time(17, 20),
            defaults={"heure_fin": datetime.time(17, 40)},
        )[0]
        RendezVous.objects.get_or_create(
            disponibilite=dispo_reservee, defaults={
                "parent": parent_benali, "eleve_concerne": eleves_sciences[0], "motif": "Point sur les résultats du trimestre",
            },
        )

    # -- Ressources -----------------------------------------------------------

    def _make_ressources(self, enseignants):
        videoprojecteur = Ressource.objects.get_or_create(nom="Vidéoprojecteur mobile", defaults={"type_ressource": Ressource.TypeRessource.MATERIEL})[0]
        Ressource.objects.get_or_create(nom="Salle informatique", defaults={"type_ressource": Ressource.TypeRessource.SALLE})
        creneau = CreneauHoraire.objects.filter(jour_semaine=CreneauHoraire.Jour.DIMANCHE, ordre=1).first()
        if creneau:
            Reservation.objects.get_or_create(
                ressource=videoprojecteur, enseignant=enseignants["Histoire-Géographie"], date=datetime.date(2025, 10, 12), creneau=creneau,
                defaults={"motif": "Projection d'un documentaire"},
            )

    # -- Documents ------------------------------------------------------------

    def _make_documents(self, admin_user, enseignants, classe_sciences):
        from django.core.files.base import ContentFile

        Document.objects.get_or_create(
            titre="Règlement intérieur", defaults={
                "description": "Règlement intérieur de l'établissement.", "categorie": Document.Categorie.REGLEMENT,
                "depose_par": admin_user, "classe": None,
                "fichier": ContentFile(b"Reglement interieur (document de demonstration).", name="reglement_interieur.txt"),
            },
        )
        Document.objects.get_or_create(
            titre="Support de cours - Fonctions", classe=classe_sciences, defaults={
                "description": "Support du chapitre sur les fonctions.", "categorie": Document.Categorie.SUPPORT_COURS,
                "depose_par": enseignants["Mathématiques"].user,
                "fichier": ContentFile(b"Support de cours sur les fonctions (document de demonstration).", name="support_fonctions.txt"),
            },
        )

    # -- Sondages ---------------------------------------------------------

    def _make_sondages(self, admin_user):
        sondage, created = Sondage.objects.get_or_create(
            titre="Satisfaction cantine scolaire", defaults={
                "description": "Votre avis sur la cantine de l'établissement.", "audience": Sondage.Audience.TOUS,
                "cree_par": admin_user,
            },
        )
        if created:
            question = QuestionSondage.objects.create(sondage=sondage, texte="Êtes-vous satisfait de la cantine ?")
            for texte in ["Très satisfait", "Satisfait", "Peu satisfait", "Pas du tout satisfait"]:
                ChoixReponse.objects.create(question=question, texte=texte)
