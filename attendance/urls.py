from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    path("appel/", views.appel_liste, name="appel_liste"),
    path("appel/<int:entry_id>/", views.appel_seance, name="appel_seance"),
    path("historique/", views.historique, name="historique"),
]
