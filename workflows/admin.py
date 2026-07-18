from django.contrib import admin

from academics.admin_mixins import EtablissementScopedAdmin

from .models import WorkflowExecution, WorkflowRegle


@admin.register(WorkflowRegle)
class WorkflowRegleAdmin(EtablissementScopedAdmin, admin.ModelAdmin):
    list_display = ("nom", "declencheur", "seuil", "destinataire", "actif")
    list_filter = ("declencheur", "actif")
    search_fields = ("nom",)


@admin.register(WorkflowExecution)
class WorkflowExecutionAdmin(EtablissementScopedAdmin, admin.ModelAdmin):
    etablissement_lookup = "regle__etablissement"
    list_display = ("regle", "eleve", "cle_unicite", "date_execution")
    list_filter = ("regle",)
    search_fields = ("eleve__matricule", "eleve__user__first_name", "eleve__user__last_name")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
