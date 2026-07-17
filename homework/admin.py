from django.contrib import admin

from .models import CahierDeTexte, Devoir


@admin.register(CahierDeTexte)
class CahierDeTexteAdmin(admin.ModelAdmin):
    list_display = ("seance", "saisi_par", "date_saisie", "visible_eleves")


@admin.register(Devoir)
class DevoirAdmin(admin.ModelAdmin):
    list_display = ("matiere", "classe", "date_a_faire_pour", "enseignant")
    list_filter = ("classe", "matiere")
    autocomplete_fields = ("classe", "matiere", "enseignant")
