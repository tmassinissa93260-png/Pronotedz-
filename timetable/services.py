from accounts.models import Enseignant

from .models import CreneauHoraire, EmploiDuTempsEntry


def build_grid(entries_qs):
    """Arrange a queryset of EmploiDuTempsEntry into a day x créneau grid.

    Assumes the queryset is already scoped (one classe, or one enseignant)
    so there is at most one entry per créneau — enforced in the DB by the
    unique_together constraints on EmploiDuTempsEntry.
    """
    entries = entries_qs.select_related("matiere", "enseignant__user", "salle", "creneau")
    entries_by_creneau_id = {entry.creneau_id: entry for entry in entries}

    creneaux = list(CreneauHoraire.objects.order_by("ordre", "jour_semaine"))
    ordres = sorted({c.ordre for c in creneaux})
    jours_presents = sorted({c.jour_semaine for c in creneaux})
    jours = [(j, label) for j, label in CreneauHoraire.Jour.choices if j in jours_presents]

    creneaux_par_jour_ordre = {(c.jour_semaine, c.ordre): c for c in creneaux}

    lignes = []
    for ordre in ordres:
        cellules = []
        heure_debut = heure_fin = None
        for jour, _ in jours:
            creneau = creneaux_par_jour_ordre.get((jour, ordre))
            entry = entries_by_creneau_id.get(creneau.id) if creneau else None
            if creneau and heure_debut is None:
                heure_debut, heure_fin = creneau.heure_debut, creneau.heure_fin
            cellules.append(entry)
        lignes.append({"ordre": ordre, "heure_debut": heure_debut, "heure_fin": heure_fin, "cellules": cellules})

    return {"jours": jours, "lignes": lignes}


def suggerer_remplacants(entry):
    """Teachers who teach the same matière and have no class of their own at
    this exact créneau, so they're free to cover an absent colleague."""
    occupes = EmploiDuTempsEntry.objects.filter(
        creneau=entry.creneau, annee_scolaire=entry.annee_scolaire,
    ).values_list("enseignant_id", flat=True)
    return (
        Enseignant.objects.filter(matieres_enseignees=entry.matiere)
        .exclude(pk=entry.enseignant_id)
        .exclude(pk__in=occupes)
        .select_related("user")
    )


def _minutes(t):
    return t.hour * 60 + t.minute


def build_day(entries_qs, date):
    """Arrange one day's entries into a vertical timeline (top/height in %)
    for the dashboard's day-widget, Pronote-style.
    """
    jour_semaine = CreneauHoraire.PYTHON_WEEKDAY_TO_JOUR.get(date.weekday())
    if jour_semaine is None:
        return {"blocks": [], "heures": [], "vide": True, "date": date}

    entries = list(
        entries_qs.filter(creneau__jour_semaine=jour_semaine)
        .select_related("matiere", "enseignant__user", "salle", "creneau")
        .order_by("creneau__ordre")
    )
    if not entries:
        return {"blocks": [], "heures": [], "vide": True, "date": date}

    debut_min = min(_minutes(e.creneau.heure_debut) for e in entries)
    fin_max = max(_minutes(e.creneau.heure_fin) for e in entries)
    total_minutes = fin_max - debut_min

    blocks = []
    for entry in entries:
        start = _minutes(entry.creneau.heure_debut) - debut_min
        duree = _minutes(entry.creneau.heure_fin) - _minutes(entry.creneau.heure_debut)
        blocks.append(
            {
                "entry": entry,
                "top": round(start / total_minutes * 100, 2),
                "height": round(duree / total_minutes * 100, 2),
            }
        )

    heures = []
    heure = debut_min - (debut_min % 60)
    while heure <= fin_max:
        if debut_min <= heure <= fin_max:
            heures.append({"label": f"{heure // 60:02d}h00", "top": round((heure - debut_min) / total_minutes * 100, 2)})
        heure += 60

    return {"blocks": blocks, "heures": heures, "vide": False, "date": date}
