from django.urls import path

from . import views

app_name = "actualites"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("nouvelle/", views.creer, name="creer"),
    path("<int:publication_id>/lu/", views.marquer_lu, name="marquer_lu"),
    path("<int:publication_id>/suivi/", views.suivi_lecture, name="suivi_lecture"),
]
