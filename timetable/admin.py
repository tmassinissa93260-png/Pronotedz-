from django.contrib import admin

from .models import CreneauHoraire, EmploiDuTempsEntry


@admin.register(CreneauHoraire)
class CreneauHoraireAdmin(admin.ModelAdmin):
    list_display = ("jour_semaine", "ordre", "heure_debut", "heure_fin")
    list_filter = ("jour_semaine",)
    ordering = ("jour_semaine", "ordre")


@admin.register(EmploiDuTempsEntry)
class EmploiDuTempsEntryAdmin(admin.ModelAdmin):
    list_display = ("classe", "matiere", "enseignant", "salle", "creneau", "annee_scolaire")
    list_filter = ("classe", "annee_scolaire", "enseignant")
    autocomplete_fields = ("classe", "matiere", "enseignant", "salle")
