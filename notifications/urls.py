from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("<int:notification_id>/lu/", views.marquer_lu, name="marquer_lu"),
    path("tout-lu/", views.marquer_tout_lu, name="marquer_tout_lu"),
]
