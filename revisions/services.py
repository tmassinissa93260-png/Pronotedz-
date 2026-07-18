import datetime
import math

from .models import AnnaleExamen, DateExamen, ProgrammeChapitre, ProgressionChapitre

NIVEAUX_EXAMEN = ("4AM", "3AS")


def est_classe_examen(eleve):
    return eleve.classe.niveau.libelle in NIVEAUX_EXAMEN


def date_examen_pour(eleve):
    return DateExamen.objects.filter(niveau=eleve.classe.niveau, annee_scolaire=eleve.classe.annee_scolaire).first()


def chapitres_avec_statut(eleve):
    chapitres = ProgrammeChapitre.objects.filter(niveau=eleve.classe.niveau).select_related("matiere").order_by("matiere__nom", "ordre")
    statuts = {
        p.chapitre_id: p.statut
        for p in ProgressionChapitre.objects.filter(eleve=eleve, chapitre__niveau=eleve.classe.niveau)
    }
    return [
        {"chapitre": chapitre, "statut": statuts.get(chapitre.pk, ProgressionChapitre.Statut.A_FAIRE)}
        for chapitre in chapitres
    ]


def progression_par_matiere(lignes):
    par_matiere = {}
    for ligne in lignes:
        matiere = ligne["chapitre"].matiere
        entree = par_matiere.setdefault(matiere, {"total": 0, "maitrises": 0})
        entree["total"] += 1
        if ligne["statut"] == ProgressionChapitre.Statut.MAITRISE:
            entree["maitrises"] += 1
    for entree in par_matiere.values():
        entree["pourcentage"] = round(100 * entree["maitrises"] / entree["total"]) if entree["total"] else 0
    return par_matiere


def generer_planning(eleve, aujourdhui=None):
    """Splits the not-yet-mastered chapters into weekly batches between now
    and the exam date. Recomputed fresh every time from current progress —
    marking a chapter as mastered immediately shrinks the remaining plan."""
    aujourdhui = aujourdhui or datetime.date.today()
    lignes = chapitres_avec_statut(eleve)
    restants = [l["chapitre"] for l in lignes if l["statut"] != ProgressionChapitre.Statut.MAITRISE]
    date_examen = date_examen_pour(eleve)
    if not date_examen or not restants:
        return []

    jours_restants = (date_examen.date_examen - aujourdhui).days
    if jours_restants <= 0:
        return [restants]

    nb_semaines = max(1, jours_restants // 7)
    par_semaine = math.ceil(len(restants) / nb_semaines)
    return [restants[i:i + par_semaine] for i in range(0, len(restants), par_semaine)]


def annales_pour(eleve):
    return AnnaleExamen.objects.filter(niveau=eleve.classe.niveau).select_related("matiere")
