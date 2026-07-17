from .models import CreneauHoraire


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
