from django.urls import path

from . import views

app_name = "ressources"

urlpatterns = [
    path("nouvelle/", views.nouvelle_reservation, name="nouvelle_reservation"),
    path("mes-reservations/", views.mes_reservations, name="mes_reservations"),
    path("annuler/<int:reservation_id>/", views.annuler_reservation, name="annuler_reservation"),
]
