from django.urls import path

from . import views

app_name = "academics"

urlpatterns = [
    path("groupe/", views.groupe_tableau_bord, name="groupe_tableau_bord"),
]
