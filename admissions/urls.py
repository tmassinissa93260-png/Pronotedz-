from django.urls import path

from . import views

app_name = "admissions"

urlpatterns = [
    path("candidature/<slug:slug>/", views.candidature_form, name="candidature_form"),
    path("merci/<str:reference>/", views.candidature_confirmation, name="candidature_confirmation"),
    path("suivi/", views.candidature_suivi, name="candidature_suivi"),
    path("", views.candidature_liste, name="candidature_liste"),
    path("liens/", views.portail_candidature_liens, name="portail_liens"),
    path("<int:candidature_id>/", views.candidature_detail, name="candidature_detail"),
    path("<int:candidature_id>/convertir/", views.candidature_convertir, name="candidature_convertir"),
]
