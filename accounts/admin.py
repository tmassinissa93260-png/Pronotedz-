from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from academics.admin_mixins import EtablissementScopedAdmin

from .models import Enseignant, Eleve, Parent, PersonnelAdministratif, Utilisateur


class PersonnelAdministratifInline(admin.StackedInline):
    model = PersonnelAdministratif
    can_delete = False


class EnseignantInline(admin.StackedInline):
    model = Enseignant
    can_delete = False
    filter_horizontal = ("matieres_enseignees",)


class EleveInline(admin.StackedInline):
    model = Eleve
    can_delete = False


@admin.register(Utilisateur)
class UtilisateurAdmin(EtablissementScopedAdmin, UserAdmin):
    list_display = (
        "username",
        "first_name",
        "last_name",
        "role",
        "email",
        "is_active",
    )
    list_filter = ("role", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        (
            "Pronotedz",
            {"fields": ("role", "telephone", "photo", "must_change_password")},
        ),
    )

    def get_inlines(self, request, obj):
        if obj is None:
            return []
        return {
            Utilisateur.Role.ADMIN: [PersonnelAdministratifInline],
            Utilisateur.Role.ENSEIGNANT: [EnseignantInline],
            Utilisateur.Role.ELEVE: [EleveInline],
        }.get(obj.role, [])


@admin.register(Parent)
class ParentAdmin(EtablissementScopedAdmin, admin.ModelAdmin):
    etablissement_lookup = "user__etablissement"
    list_display = ("user",)
    filter_horizontal = ("enfants",)
    autocomplete_fields = ("user",)


@admin.register(Eleve)
class EleveAdmin(EtablissementScopedAdmin, admin.ModelAdmin):
    etablissement_lookup = "user__etablissement"
    list_display = ("user", "matricule", "classe")
    list_filter = ("classe",)
    search_fields = ("matricule", "user__first_name", "user__last_name")
    autocomplete_fields = ("user", "classe")


@admin.register(Enseignant)
class EnseignantAdmin(EtablissementScopedAdmin, admin.ModelAdmin):
    etablissement_lookup = "user__etablissement"
    list_display = ("user", "civilite")
    filter_horizontal = ("matieres_enseignees",)
    autocomplete_fields = ("user",)
    search_fields = ("user__username", "user__first_name", "user__last_name")
