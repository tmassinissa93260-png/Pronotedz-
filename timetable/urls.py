from django.urls import path

from . import views

app_name = "timetable"

urlpatterns = [
    path("", views.mon_emploi_du_temps, name="grid"),
]
