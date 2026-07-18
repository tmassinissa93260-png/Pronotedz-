from django.contrib import admin

from .models import ChoixQCM, QCM, QuestionQCM, ReponseEleve, TentativeQCM


class ChoixInline(admin.TabularInline):
    model = ChoixQCM
    extra = 2


class QuestionInline(admin.StackedInline):
    model = QuestionQCM
    extra = 1


@admin.register(QCM)
class QCMAdmin(admin.ModelAdmin):
    list_display = ("titre", "classe", "matiere", "enseignant", "date_ouverture", "date_limite")
    list_filter = ("classe", "matiere")
    autocomplete_fields = ("classe", "matiere", "enseignant")
    inlines = [QuestionInline]


@admin.register(QuestionQCM)
class QuestionQCMAdmin(admin.ModelAdmin):
    list_display = ("texte", "qcm", "points")
    inlines = [ChoixInline]


admin.site.register(TentativeQCM)
admin.site.register(ReponseEleve)
