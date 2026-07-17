from django.urls import path

from . import views

app_name = "grades"

urlpatterns = [
    path("evaluations/", views.evaluation_liste, name="evaluation_liste"),
    path("evaluations/<int:evaluation_id>/notes/", views.saisie_notes, name="saisie_notes"),
    path("bulletin/", views.bulletin, name="bulletin"),
]
