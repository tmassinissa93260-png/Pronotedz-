from django.contrib import admin

from .models import ChoixReponse, QuestionSondage, ReponseUtilisateur, Sondage


class ChoixInline(admin.TabularInline):
    model = ChoixReponse
    extra = 2


class QuestionInline(admin.StackedInline):
    model = QuestionSondage
    extra = 1


@admin.register(Sondage)
class SondageAdmin(admin.ModelAdmin):
    list_display = ("titre", "audience", "date_creation", "date_cloture")
    list_filter = ("audience",)
    inlines = [QuestionInline]


@admin.register(QuestionSondage)
class QuestionSondageAdmin(admin.ModelAdmin):
    list_display = ("texte", "sondage", "ordre")
    inlines = [ChoixInline]


admin.site.register(ReponseUtilisateur)
