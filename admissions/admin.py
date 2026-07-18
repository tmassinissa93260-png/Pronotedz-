from django.contrib import admin

from academics.admin_mixins import EtablissementScopedAdmin

from .models import Candidature


@admin.register(Candidature)
class CandidatureAdmin(EtablissementScopedAdmin, admin.ModelAdmin):
    list_display = ("reference", "nom_complet", "niveau_souhaite", "statut", "date_soumission")
    list_filter = ("statut", "niveau_souhaite")
    search_fields = ("reference", "nom", "prenom", "email_parent")
    readonly_fields = ("reference", "date_soumission")
