import datetime

from attendance.models import Absence, Retard
from grades.models import Note
from homework.models import Devoir, RenduDevoir

SEUIL_ALERTE = 4

POIDS = {
    "BAISSE_MOYENNE": 3,
    "ABSENCES": 2,
    "RETARDS": 1,
    "DEVOIRS_NON_RENDUS": 2,
}

RECOMMANDATIONS = {
    "BAISSE_MOYENNE": "Proposer un entretien individuel avec l'élève et ses parents pour identifier les difficultés ; envisager un soutien pédagogique ciblé sur la matière concernée.",
    "ABSENCES": "Contacter la famille pour comprendre la cause des absences répétées et rappeler l'obligation d'assiduité.",
    "RETARDS": "Rappeler les horaires à l'élève et à la famille ; vérifier une éventuelle difficulté de transport ou d'organisation.",
    "DEVOIRS_NON_RENDUS": "Vérifier avec l'élève sa compréhension des consignes et son organisation ; proposer un accompagnement méthodologique.",
}


def _signal_baisse_moyenne(eleve):
    notes = list(
        Note.objects.filter(eleve=eleve, valeur__isnull=False, evaluation__publie=True)
        .select_related("evaluation")
        .order_by("-evaluation__date_evaluation")[:3]
    )
    if len(notes) < 3:
        return None
    plus_recente, precedente, avant_precedente = notes[0], notes[1], notes[2]
    if plus_recente.valeur < precedente.valeur < avant_precedente.valeur:
        return {
            "type": "BAISSE_MOYENNE",
            "description": (
                f"Baisse continue sur les 3 dernières évaluations : "
                f"{avant_precedente.valeur} → {precedente.valeur} → {plus_recente.valeur}/20."
            ),
        }
    return None


def _signal_absences(eleve, aujourdhui):
    il_y_a_14_jours = aujourdhui - datetime.timedelta(days=14)
    nb = Absence.objects.filter(eleve=eleve, seance__date__gte=il_y_a_14_jours, seance__date__lte=aujourdhui).count()
    if nb >= 3:
        return {"type": "ABSENCES", "description": f"{nb} absence(s) au cours des 14 derniers jours."}
    return None


def _signal_retards(eleve, aujourdhui):
    il_y_a_14_jours = aujourdhui - datetime.timedelta(days=14)
    nb = Retard.objects.filter(eleve=eleve, date__gte=il_y_a_14_jours, date__lte=aujourdhui).count()
    if nb >= 3:
        return {"type": "RETARDS", "description": f"{nb} retard(s) au cours des 14 derniers jours."}
    return None


def _signal_devoirs_non_rendus(eleve, aujourdhui):
    il_y_a_30_jours = aujourdhui - datetime.timedelta(days=30)
    devoirs_attendus = Devoir.objects.filter(
        classe=eleve.classe, date_a_faire_pour__gte=il_y_a_30_jours, date_a_faire_pour__lt=aujourdhui,
    )
    rendus_ids = set(
        RenduDevoir.objects.filter(eleve=eleve, devoir__in=devoirs_attendus).values_list("devoir_id", flat=True)
    )
    nb_non_rendus = devoirs_attendus.exclude(pk__in=rendus_ids).count()
    if nb_non_rendus >= 2:
        return {"type": "DEVOIRS_NON_RENDUS", "description": f"{nb_non_rendus} devoir(s) non rendu(s) sur les 30 derniers jours."}
    return None


def calculer_signaux(eleve, aujourdhui=None):
    aujourdhui = aujourdhui or datetime.date.today()
    signaux = [
        _signal_baisse_moyenne(eleve),
        _signal_absences(eleve, aujourdhui),
        _signal_retards(eleve, aujourdhui),
        _signal_devoirs_non_rendus(eleve, aujourdhui),
    ]
    return [s for s in signaux if s]


def calculer_score(signaux):
    return sum(POIDS[s["type"]] for s in signaux)


def recommandations_pour(signaux):
    return [RECOMMANDATIONS[s["type"]] for s in signaux]
