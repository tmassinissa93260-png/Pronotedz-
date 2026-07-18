from django.contrib import admin

from academics.admin_mixins import EtablissementScopedAdmin

from .models import Document


@admin.register(Document)
class DocumentAdmin(EtablissementScopedAdmin, admin.ModelAdmin):
    list_display = ("titre", "categorie", "classe", "depose_par", "date_depot")
    list_filter = ("categorie", "classe")
    autocomplete_fields = ("classe",)
