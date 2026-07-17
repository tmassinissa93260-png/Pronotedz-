from django.contrib import admin

from .models import LectureAccusee, Publication


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ("titre", "audience", "epingle", "date_publication", "auteur")
    list_filter = ("audience", "epingle")


admin.site.register(LectureAccusee)
