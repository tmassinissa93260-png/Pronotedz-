from django.contrib import admin

from .models import DisponibiliteRDV, RendezVous


@admin.register(DisponibiliteRDV)
class DisponibiliteRDVAdmin(admin.ModelAdmin):
    list_display = ("enseignant", "date", "heure_debut", "heure_fin", "est_reservee")
    list_filter = ("date",)
    autocomplete_fields = ("enseignant",)


@admin.register(RendezVous)
class RendezVousAdmin(admin.ModelAdmin):
    list_display = ("disponibilite", "parent", "eleve_concerne", "date_demande")
