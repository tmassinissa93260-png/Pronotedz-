from django.contrib import admin

from academics.admin_mixins import EtablissementScopedAdmin

from .models import Facture, FraisScolarite, Paiement


class PaiementInline(admin.TabularInline):
    model = Paiement
    extra = 0
    readonly_fields = ("numero_recu",)


@admin.register(FraisScolarite)
class FraisScolariteAdmin(EtablissementScopedAdmin, admin.ModelAdmin):
    etablissement_lookup = "annee_scolaire__etablissement"
    list_display = ("libelle", "niveau", "annee_scolaire", "montant", "date_echeance")
    list_filter = ("niveau", "annee_scolaire")
    search_fields = ("libelle",)


@admin.register(Facture)
class FactureAdmin(EtablissementScopedAdmin, admin.ModelAdmin):
    etablissement_lookup = "eleve__user__etablissement"
    list_display = ("eleve", "frais", "montant", "statut", "date_creation")
    list_filter = ("statut", "frais")
    search_fields = ("eleve__matricule", "eleve__user__first_name", "eleve__user__last_name")
    autocomplete_fields = ("eleve", "frais")
    inlines = [PaiementInline]


@admin.register(Paiement)
class PaiementAdmin(EtablissementScopedAdmin, admin.ModelAdmin):
    etablissement_lookup = "facture__eleve__user__etablissement"
    list_display = ("numero_recu", "facture", "montant", "mode_paiement", "date_paiement")
    list_filter = ("mode_paiement",)
    readonly_fields = ("numero_recu",)
    autocomplete_fields = ("facture",)
