from django.contrib import admin

from .models import Observation


@admin.register(Observation)
class ObservationAdmin(admin.ModelAdmin):
    list_display = ("eleve", "type_observation", "motif", "date", "saisie_par")
    list_filter = ("type_observation", "date")
    autocomplete_fields = ("eleve", "matiere")
