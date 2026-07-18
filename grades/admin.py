from django.contrib import admin

from .models import AppreciationGenerale, AppreciationMatiere, Evaluation, Note


class NoteInline(admin.TabularInline):
    model = Note
    extra = 0
    autocomplete_fields = ("eleve",)


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("titre", "matiere", "classe", "trimestre", "type_evaluation", "date_evaluation", "publie")
    list_filter = ("trimestre", "type_evaluation", "classe", "publie")
    autocomplete_fields = ("classe", "matiere", "enseignant")
    inlines = [NoteInline]


@admin.register(AppreciationMatiere)
class AppreciationMatiereAdmin(admin.ModelAdmin):
    list_display = ("eleve", "matiere", "trimestre")
    autocomplete_fields = ("eleve",)


@admin.register(AppreciationGenerale)
class AppreciationGeneraleAdmin(admin.ModelAdmin):
    list_display = ("eleve", "trimestre")
    autocomplete_fields = ("eleve",)
