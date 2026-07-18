from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("tableau-de-bord/", views.tableau_bord, name="tableau_bord"),
    path("frais/", views.frais_liste, name="frais_liste"),
    path("frais/creer/", views.frais_creer, name="frais_creer"),
    path("factures/", views.facture_liste, name="facture_liste"),
    path("factures/<int:facture_id>/", views.facture_detail, name="facture_detail"),
    path("paiements/<int:paiement_id>/recu.pdf", views.recu_pdf, name="recu_pdf"),
    path("mes-frais/", views.mes_frais, name="mes_frais"),
]
