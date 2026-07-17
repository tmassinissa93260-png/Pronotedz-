from django.urls import path

from . import views

app_name = "rendezvous"

urlpatterns = [
    path("disponibilites/", views.mes_disponibilites, name="mes_disponibilites"),
    path("reserver/", views.disponibilites_liste, name="disponibilites_liste"),
    path("reserver/<int:disponibilite_id>/", views.reserver, name="reserver"),
    path("mes-rdv/", views.mes_rdv, name="mes_rdv"),
    path("annuler/<int:rdv_id>/", views.annuler, name="annuler"),
]
