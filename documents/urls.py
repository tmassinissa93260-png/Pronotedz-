from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("deposer/", views.deposer, name="deposer"),
]
