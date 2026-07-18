from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("changer-mot-de-passe/", views.changer_mot_de_passe, name="changer_mot_de_passe"),
    path("import-csv/", views.import_csv, name="import_csv"),
]
