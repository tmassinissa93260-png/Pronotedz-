import csv
import io
import secrets

from django.contrib.auth.hashers import make_password
from django.utils.text import slugify

from academics.models import Classe, Matiere

from .models import Eleve, Enseignant, Parent, Utilisateur


def generer_username(prefixe, base_texte):
    base = slugify(base_texte).replace("-", "")[:20] or "user"
    username = f"{prefixe}.{base}"
    suffixe = 1
    while Utilisateur.objects.filter(username=username).exists():
        suffixe += 1
        username = f"{prefixe}.{base}{suffixe}"
    return username


def generer_mot_de_passe_temporaire():
    return secrets.token_urlsafe(9)


def _lire_csv(fichier):
    return csv.DictReader(io.TextIOWrapper(fichier, encoding="utf-8-sig"))


def importer_eleves(fichier, annee_scolaire):
    """Colonnes attendues : nom, prenom, matricule, classe."""
    nb_crees = 0
    erreurs = []
    comptes = []
    for i, ligne in enumerate(_lire_csv(fichier), start=2):
        try:
            nom, prenom = ligne["nom"].strip(), ligne["prenom"].strip()
            matricule = ligne["matricule"].strip()
            classe_libelle = ligne["classe"].strip()
        except KeyError as exc:
            erreurs.append(f"Ligne {i} : colonne manquante {exc}.")
            continue

        classe = Classe.objects.filter(libelle=classe_libelle, annee_scolaire=annee_scolaire).first()
        if not classe:
            erreurs.append(f"Ligne {i} : classe « {classe_libelle} » introuvable pour l'année en cours.")
            continue
        if Eleve.objects.filter(matricule=matricule).exists():
            erreurs.append(f"Ligne {i} : matricule « {matricule} » déjà utilisé.")
            continue

        username = generer_username("eleve", matricule)
        mot_de_passe = generer_mot_de_passe_temporaire()
        user = Utilisateur.objects.create(
            username=username, first_name=prenom, last_name=nom, role=Utilisateur.Role.ELEVE,
            password=make_password(mot_de_passe), must_change_password=True,
        )
        Eleve.objects.create(user=user, classe=classe, matricule=matricule)
        comptes.append({"nom_complet": f"{prenom} {nom}", "username": username, "mot_de_passe": mot_de_passe})
        nb_crees += 1
    return nb_crees, erreurs, comptes


def importer_enseignants(fichier):
    """Colonnes attendues : nom, prenom, matieres (séparées par ';')."""
    nb_crees = 0
    erreurs = []
    comptes = []
    for i, ligne in enumerate(_lire_csv(fichier), start=2):
        try:
            nom, prenom = ligne["nom"].strip(), ligne["prenom"].strip()
            matieres_brutes = ligne.get("matieres", "")
        except KeyError as exc:
            erreurs.append(f"Ligne {i} : colonne manquante {exc}.")
            continue

        username = generer_username("prof", f"{prenom}{nom}")
        mot_de_passe = generer_mot_de_passe_temporaire()
        user = Utilisateur.objects.create(
            username=username, first_name=prenom, last_name=nom, role=Utilisateur.Role.ENSEIGNANT,
            password=make_password(mot_de_passe), must_change_password=True,
        )
        enseignant = Enseignant.objects.create(user=user)
        for nom_matiere in [m.strip() for m in matieres_brutes.split(";") if m.strip()]:
            matiere = Matiere.objects.filter(nom__iexact=nom_matiere).first()
            if matiere:
                enseignant.matieres_enseignees.add(matiere)
            else:
                erreurs.append(f"Ligne {i} : matière « {nom_matiere} » introuvable (compte créé sans cette matière).")
        comptes.append({"nom_complet": f"{prenom} {nom}", "username": username, "mot_de_passe": mot_de_passe})
        nb_crees += 1
    return nb_crees, erreurs, comptes


def importer_parents(fichier):
    """Colonnes attendues : nom, prenom, matricules_enfants (séparés par ';')."""
    nb_crees = 0
    erreurs = []
    comptes = []
    for i, ligne in enumerate(_lire_csv(fichier), start=2):
        try:
            nom, prenom = ligne["nom"].strip(), ligne["prenom"].strip()
            matricules_bruts = ligne.get("matricules_enfants", "")
        except KeyError as exc:
            erreurs.append(f"Ligne {i} : colonne manquante {exc}.")
            continue

        enfants = []
        for matricule in [m.strip() for m in matricules_bruts.split(";") if m.strip()]:
            eleve = Eleve.objects.filter(matricule=matricule).first()
            if eleve:
                enfants.append(eleve)
            else:
                erreurs.append(f"Ligne {i} : élève de matricule « {matricule} » introuvable.")

        if not enfants:
            erreurs.append(f"Ligne {i} : aucun enfant valide, compte non créé.")
            continue

        username = generer_username("parent", f"{prenom}{nom}")
        mot_de_passe = generer_mot_de_passe_temporaire()
        user = Utilisateur.objects.create(
            username=username, first_name=prenom, last_name=nom, role=Utilisateur.Role.PARENT,
            password=make_password(mot_de_passe), must_change_password=True,
        )
        parent = Parent.objects.create(user=user)
        parent.enfants.add(*enfants)
        comptes.append({"nom_complet": f"{prenom} {nom}", "username": username, "mot_de_passe": mot_de_passe})
        nb_crees += 1
    return nb_crees, erreurs, comptes
