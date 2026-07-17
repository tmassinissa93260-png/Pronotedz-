from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("titre", "categorie", "classe", "depose_par", "date_depot")
    list_filter = ("categorie", "classe")
    autocomplete_fields = ("classe",)
