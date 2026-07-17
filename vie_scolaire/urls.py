from django.urls import path

from . import views

app_name = "vie_scolaire"

urlpatterns = [
    path("", views.observation_liste, name="observation_liste"),
    path("nouvelle/", views.observation_creer, name="observation_creer"),
    path("mes-observations/", views.mes_observations, name="mes_observations"),
]
