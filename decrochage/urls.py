from django.urls import path

from . import views

app_name = "decrochage"

urlpatterns = [
    path("", views.alerte_liste, name="alerte_liste"),
    path("<int:alerte_id>/", views.alerte_detail, name="alerte_detail"),
]
