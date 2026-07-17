from django.contrib import admin

from .models import (
    AnneeScolaire,
    Classe,
    CoefficientMatiere,
    Etablissement,
    Filiere,
    Matiere,
    Niveau,
    Salle,
    Trimestre,
)


@admin.register(Etablissement)
class EtablissementAdmin(admin.ModelAdmin):
    list_display = ("nom", "wilaya", "type_etablissement", "annee_scolaire_courante")

    def has_add_permission(self, request):
        return not Etablissement.objects.exists()


class TrimestreInline(admin.TabularInline):
    model = Trimestre
    extra = 3


@admin.register(AnneeScolaire)
class AnneeScolaireAdmin(admin.ModelAdmin):
    list_display = ("libelle", "date_debut", "date_fin", "est_active")
    inlines = [TrimestreInline]


@admin.register(Niveau)
class NiveauAdmin(admin.ModelAdmin):
    list_display = ("libelle", "cycle", "ordre")
    list_filter = ("cycle",)


@admin.register(Filiere)
class FiliereAdmin(admin.ModelAdmin):
    list_display = ("libelle",)


class CoefficientMatiereInline(admin.TabularInline):
    model = CoefficientMatiere
    extra = 1


@admin.register(Matiere)
class MatiereAdmin(admin.ModelAdmin):
    list_display = ("nom", "code", "couleur")
    search_fields = ("nom", "code")
    inlines = [CoefficientMatiereInline]


@admin.register(Salle)
class SalleAdmin(admin.ModelAdmin):
    list_display = ("nom", "capacite", "type_salle")
    search_fields = ("nom",)


@admin.register(Classe)
class ClasseAdmin(admin.ModelAdmin):
    list_display = ("libelle", "niveau", "filiere", "annee_scolaire", "professeur_principal")
    list_filter = ("niveau", "annee_scolaire")
    search_fields = ("libelle",)
    autocomplete_fields = ("professeur_principal",)
