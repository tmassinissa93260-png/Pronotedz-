from django.urls import path

from . import views

app_name = "timetable"

urlpatterns = [
    path("", views.mon_emploi_du_temps, name="grid"),
    path("remplacements/", views.remplacements_jour, name="remplacements_jour"),
    path("remplacements/<int:entry_id>/<str:date>/", views.remplacement_assigner, name="remplacement_assigner"),
    path("remplacements/annuler/<int:seance_id>/", views.remplacement_annuler, name="remplacement_annuler"),
]
