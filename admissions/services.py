from django.contrib.auth.hashers import make_password
from django.utils import timezone

from accounts.csv_import import generer_mot_de_passe_temporaire, generer_username
from accounts.models import Eleve, Utilisateur
from notifications.services import notifier_email_brut

from .models import Candidature

_MESSAGES_STATUT = {
    Candidature.Statut.EN_EXAMEN: (
        "Votre candidature est en cours d'examen",
        "Votre dossier de candidature (réf. {reference}) pour {nom_complet} est maintenant en cours d'examen par l'établissement.",
    ),
    Candidature.Statut.ACCEPTE: (
        "Votre candidature a été acceptée",
        "Félicitations ! La candidature (réf. {reference}) de {nom_complet} a été acceptée. "
        "L'établissement vous contactera prochainement pour finaliser l'inscription.",
    ),
    Candidature.Statut.REFUSE: (
        "Réponse concernant votre candidature",
        "Nous vous informons que la candidature (réf. {reference}) de {nom_complet} n'a pas été retenue cette année.",
    ),
    Candidature.Statut.LISTE_ATTENTE: (
        "Votre candidature est en liste d'attente",
        "La candidature (réf. {reference}) de {nom_complet} a été placée en liste d'attente. "
        "Nous vous recontacterons si une place se libère.",
    ),
}


def changer_statut(candidature, nouveau_statut, admin_user, notes=""):
    candidature.statut = nouveau_statut
    candidature.date_traitement = timezone.now()
    candidature.traite_par = admin_user
    if notes:
        candidature.notes_admin = notes
    candidature.save()

    message = _MESSAGES_STATUT.get(nouveau_statut)
    if message:
        sujet, gabarit = message
        notifier_email_brut(
            candidature.email_parent,
            sujet,
            gabarit.format(reference=candidature.reference, nom_complet=candidature.nom_complet),
        )
    return candidature


def convertir_en_eleve(candidature, classe):
    """Turns an ACCEPTE candidature into a real student account, reusing the
    same temp-password / must-change-password pattern as CSV import."""
    if candidature.statut != Candidature.Statut.ACCEPTE:
        raise ValueError("Seule une candidature acceptée peut être convertie en élève.")
    if candidature.eleve_cree_id:
        raise ValueError("Cette candidature a déjà été convertie.")

    annee = classe.annee_scolaire.libelle.replace("-", "")
    matricule = f"{annee}{Eleve.objects.filter(matricule__startswith=annee).count() + 1:05d}"
    username = generer_username("eleve", matricule)
    mot_de_passe = generer_mot_de_passe_temporaire()

    user = Utilisateur.objects.create(
        username=username, first_name=candidature.prenom, last_name=candidature.nom, role=Utilisateur.Role.ELEVE,
        password=make_password(mot_de_passe), must_change_password=True, etablissement=candidature.etablissement,
    )
    eleve = Eleve.objects.create(
        user=user, classe=classe, matricule=matricule,
        date_naissance=candidature.date_naissance, sexe=candidature.sexe,
    )
    candidature.eleve_cree = eleve
    candidature.save(update_fields=["eleve_cree"])

    notifier_email_brut(
        candidature.email_parent,
        "Inscription confirmée",
        f"L'inscription de {candidature.nom_complet} est confirmée dans la classe {classe}. "
        f"Identifiant : {username} — un mot de passe temporaire vous sera communiqué par l'établissement.",
    )
    return eleve, username, mot_de_passe
