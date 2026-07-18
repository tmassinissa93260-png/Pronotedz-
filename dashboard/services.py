import datetime

from grades.services import moyenne_generale


def moyennes_et_reussite_par_classe(classes, trimestre):
    """For each classe: average of all élèves' moyenne_generale and the
    share of élèves at or above 10/20, for comparison across classes."""
    resultats = []
    for classe in classes:
        moyennes = [
            m for m in (moyenne_generale(eleve, trimestre) for eleve in classe.eleves.all())
            if m is not None
        ] if trimestre else []
        resultats.append(
            {
                "classe": classe,
                "moyenne": round(sum(moyennes) / len(moyennes), 2) if moyennes else None,
                "taux_reussite": round(100 * sum(1 for m in moyennes if m >= 10) / len(moyennes), 1) if moyennes else None,
                "nb_notes": len(moyennes),
            }
        )
    return resultats


def repartition_des_moyennes(classes, trimestre):
    """Histogram of every élève's moyenne_generale across the given classes,
    bucketed into /20 ranges — surfaces the overall shape of the year's
    results at a glance (are most élèves struggling, average, excelling?)."""
    tranches = [(0, 8), (8, 10), (10, 12), (12, 14), (14, 16), (16, 20.01)]
    compteurs = {t: 0 for t in tranches}
    total = 0

    if trimestre:
        for classe in classes:
            for eleve in classe.eleves.all():
                moyenne = moyenne_generale(eleve, trimestre)
                if moyenne is None:
                    continue
                total += 1
                for borne_bas, borne_haut in tranches:
                    if borne_bas <= moyenne < borne_haut:
                        compteurs[(borne_bas, borne_haut)] += 1
                        break

    return [
        {
            "label": f"{borne_bas:g}-{min(borne_haut, 20):g}",
            "nb_eleves": compteurs[(borne_bas, borne_haut)],
            "pct": round(100 * compteurs[(borne_bas, borne_haut)] / total, 1) if total else 0,
        }
        for borne_bas, borne_haut in tranches
    ]


def absenteisme_hebdomadaire(annee, nb_semaines=6):
    """Distinct élèves marqués absents chaque semaine, sur les nb_semaines
    dernières semaines — pour repérer une dérive avant qu'elle ne s'installe."""
    from attendance.models import Absence

    aujourdhui = datetime.date.today()
    semaines = []
    max_absences = 1
    for i in range(nb_semaines - 1, -1, -1):
        fin = aujourdhui - datetime.timedelta(days=7 * i)
        debut = fin - datetime.timedelta(days=6)
        nb = (
            Absence.objects.filter(
                seance__date__gte=debut, seance__date__lte=fin, eleve__classe__annee_scolaire=annee,
            )
            .values("eleve")
            .distinct()
            .count()
            if annee
            else 0
        )
        semaines.append({"debut": debut, "fin": fin, "nb_absences": nb})
        max_absences = max(max_absences, nb)

    for semaine in semaines:
        semaine["pct"] = round(100 * semaine["nb_absences"] / max_absences, 1)
    return semaines
