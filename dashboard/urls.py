from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dispatch, name="dispatch"),
    path("admin/", views.admin_home, name="admin_home"),
    path("enseignant/", views.enseignant_home, name="enseignant_home"),
    path("eleve/", views.eleve_home, name="eleve_home"),
    path("parent/", views.parent_home, name="parent_home"),
]
