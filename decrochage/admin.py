from django.contrib import admin

from academics.admin_mixins import EtablissementScopedAdmin

from .models import AlerteDecrochage


@admin.register(AlerteDecrochage)
class AlerteDecrochageAdmin(EtablissementScopedAdmin, admin.ModelAdmin):
    etablissement_lookup = "eleve__user__etablissement"
    list_display = ("eleve", "score_risque", "statut", "date_detection")
    list_filter = ("statut",)
