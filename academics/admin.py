from django.contrib import admin

from .admin_mixins import EtablissementScopedAdmin
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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        etablissement = getattr(request.user, "etablissement", None)
        return qs.filter(pk=etablissement.pk) if etablissement else qs.none()

    def has_add_permission(self, request):
        # Only a platform operator with no établissement of their own may
        # create new schools; a school admin manages exactly one.
        return request.user.is_superuser and request.user.etablissement_id is None


class TrimestreInline(admin.TabularInline):
    model = Trimestre
    extra = 3


@admin.register(AnneeScolaire)
class AnneeScolaireAdmin(EtablissementScopedAdmin, admin.ModelAdmin):
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
class SalleAdmin(EtablissementScopedAdmin, admin.ModelAdmin):
    list_display = ("nom", "capacite", "type_salle")
    search_fields = ("nom",)


@admin.register(Classe)
class ClasseAdmin(EtablissementScopedAdmin, admin.ModelAdmin):
    etablissement_lookup = "annee_scolaire__etablissement"
    list_display = ("libelle", "niveau", "filiere", "annee_scolaire", "professeur_principal")
    list_filter = ("niveau", "annee_scolaire")
    search_fields = ("libelle",)
    autocomplete_fields = ("professeur_principal",)
