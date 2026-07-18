from django.urls import path

from . import views

app_name = "pwa"

urlpatterns = [
    path("sw.js", views.service_worker, name="service_worker"),
    path("offline/", views.offline, name="offline"),
]
