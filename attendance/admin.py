from django.contrib import admin

from .models import Absence, Justificatif, Retard, Seance


@admin.register(Seance)
class SeanceAdmin(admin.ModelAdmin):
    list_display = ("date", "emploi_du_temps_entry", "statut")
    list_filter = ("statut", "date")
    date_hierarchy = "date"


@admin.register(Absence)
class AbsenceAdmin(admin.ModelAdmin):
    list_display = ("eleve", "seance", "justifiee", "date_saisie")
    list_filter = ("justifiee",)
    autocomplete_fields = ("eleve",)


@admin.register(Retard)
class RetardAdmin(admin.ModelAdmin):
    list_display = ("eleve", "date", "heure_arrivee", "duree_minutes", "justifie")
    list_filter = ("justifie", "date")
    autocomplete_fields = ("eleve",)


@admin.register(Justificatif)
class JustificatifAdmin(admin.ModelAdmin):
    list_display = ("__str__", "statut", "date_soumission")
    list_filter = ("statut",)
