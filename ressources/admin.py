from django.contrib import admin

from .models import Reservation, Ressource


@admin.register(Ressource)
class RessourceAdmin(admin.ModelAdmin):
    list_display = ("nom", "type_ressource")
    list_filter = ("type_ressource",)
    search_fields = ("nom",)


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("ressource", "date", "creneau", "enseignant")
    list_filter = ("date", "ressource")
    autocomplete_fields = ("ressource", "enseignant")
