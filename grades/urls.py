from django.urls import path

from . import views

app_name = "grades"

urlpatterns = [
    path("evaluations/", views.evaluation_liste, name="evaluation_liste"),
    path("evaluations/<int:evaluation_id>/notes/", views.saisie_notes, name="saisie_notes"),
    path("evaluations/<int:evaluation_id>/publier/", views.publier_evaluation, name="publier_evaluation"),
    path("bulletin/", views.bulletin, name="bulletin"),
    path("bulletin/pdf/", views.bulletin_pdf, name="bulletin_pdf"),
    path("appreciations/", views.saisie_appreciations, name="saisie_appreciations"),
]
