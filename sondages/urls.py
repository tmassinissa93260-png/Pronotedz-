from django.urls import path

from . import views

app_name = "sondages"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("nouveau/", views.creer, name="creer"),
    path("<int:sondage_id>/", views.detail, name="detail"),
]
