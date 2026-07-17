from django.urls import path

from . import views

app_name = "actualites"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("nouvelle/", views.creer, name="creer"),
]
