from django.urls import path

from . import views

app_name = "rapport_parent"

urlpatterns = [
    path("preferences/", views.preferences_notifications, name="preferences_notifications"),
]
