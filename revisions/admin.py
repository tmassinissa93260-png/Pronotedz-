from django.contrib import admin

from .models import AnnaleExamen, DateExamen, ProgrammeChapitre, ProgressionChapitre


@admin.register(ProgrammeChapitre)
class ProgrammeChapitreAdmin(admin.ModelAdmin):
    list_display = ("matiere", "niveau", "ordre", "titre")
    list_filter = ("niveau", "matiere")


@admin.register(AnnaleExamen)
class AnnaleExamenAdmin(admin.ModelAdmin):
    list_display = ("titre", "matiere", "niveau", "annee")
    list_filter = ("niveau", "matiere")


@admin.register(DateExamen)
class DateExamenAdmin(admin.ModelAdmin):
    list_display = ("niveau", "annee_scolaire", "date_examen")


admin.site.register(ProgressionChapitre)
