from django.urls import path

from . import views

app_name = "revisions"

urlpatterns = [
    path("", views.revisions_accueil, name="revisions_accueil"),
]
