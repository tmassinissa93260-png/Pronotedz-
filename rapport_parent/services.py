import datetime

from attendance.models import Absence
from grades.models import Note
from homework.models import Devoir


def _donnees_semaine(enfant, aujourdhui):
    debut_semaine = aujourdhui - datetime.timedelta(days=7)
    notes = (
        Note.objects.filter(
            eleve=enfant, valeur__isnull=False, evaluation__publie=True,
            evaluation__date_evaluation__gte=debut_semaine, evaluation__date_evaluation__lte=aujourdhui,
        )
        .select_related("evaluation__matiere")
        .order_by("evaluation__date_evaluation")
    )
    absences = (
        Absence.objects.filter(eleve=enfant, seance__date__gte=debut_semaine, seance__date__lte=aujourdhui)
        .select_related("seance__emploi_du_temps_entry__matiere")
    )
    devoirs_a_venir = (
        Devoir.objects.filter(classe=enfant.classe, date_a_faire_pour__gte=aujourdhui, date_a_faire_pour__lte=aujourdhui + datetime.timedelta(days=7))
        .select_related("matiere")
        .order_by("date_a_faire_pour")
    )
    return notes, absences, devoirs_a_venir


_TEXTES = {
    "fr": {
        "sujet": "Rapport hebdomadaire — {enfant}",
        "intro": "Voici le résumé de la semaine pour {enfant} :",
        "notes_titre": "Notes de la semaine :",
        "notes_ligne": "{matiere} : {valeur}/20",
        "aucune_note": "Aucune note publiée cette semaine.",
        "absences_titre": "Absences de la semaine :",
        "absence_ligne": "{date} — {matiere}",
        "aucune_absence": "Aucune absence cette semaine.",
        "devoirs_titre": "Devoirs à venir (7 prochains jours) :",
        "devoir_ligne": "{matiere} pour le {date}",
        "aucun_devoir": "Aucun devoir à rendre dans les 7 prochains jours.",
    },
    "ar": {
        "sujet": "التقرير الأسبوعي — {enfant}",
        "intro": "فيما يلي ملخص الأسبوع لـ {enfant}:",
        "notes_titre": "علامات الأسبوع:",
        "notes_ligne": "{matiere} : {valeur}/20",
        "aucune_note": "لم يتم نشر أي علامة هذا الأسبوع.",
        "absences_titre": "غيابات الأسبوع:",
        "absence_ligne": "{date} — {matiere}",
        "aucune_absence": "لا يوجد غياب هذا الأسبوع.",
        "devoirs_titre": "الواجبات القادمة (السبعة أيام القادمة):",
        "devoir_ligne": "{matiere} بتاريخ {date}",
        "aucun_devoir": "لا يوجد واجب مستحق خلال السبعة أيام القادمة.",
    },
}


def construire_rapport(enfant, langue="fr", aujourdhui=None):
    aujourdhui = aujourdhui or datetime.date.today()
    langue = langue if langue in _TEXTES else "fr"
    textes = _TEXTES[langue]
    notes, absences, devoirs_a_venir = _donnees_semaine(enfant, aujourdhui)

    lignes = [textes["intro"].format(enfant=enfant.user.get_full_name())]

    lignes.append("")
    lignes.append(textes["notes_titre"])
    if notes:
        for note in notes:
            lignes.append(textes["notes_ligne"].format(matiere=note.evaluation.matiere.nom, valeur=note.valeur))
    else:
        lignes.append(textes["aucune_note"])

    lignes.append("")
    lignes.append(textes["absences_titre"])
    if absences:
        for absence in absences:
            lignes.append(
                textes["absence_ligne"].format(
                    date=absence.seance.date.strftime("%d/%m/%Y"), matiere=absence.seance.emploi_du_temps_entry.matiere.nom,
                )
            )
    else:
        lignes.append(textes["aucune_absence"])

    lignes.append("")
    lignes.append(textes["devoirs_titre"])
    if devoirs_a_venir:
        for devoir in devoirs_a_venir:
            lignes.append(textes["devoir_ligne"].format(matiere=devoir.matiere.nom, date=devoir.date_a_faire_pour.strftime("%d/%m/%Y")))
    else:
        lignes.append(textes["aucun_devoir"])

    sujet = textes["sujet"].format(enfant=enfant.user.get_full_name())
    corps = "\n".join(lignes)
    return sujet, corps
