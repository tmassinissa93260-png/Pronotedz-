from django.shortcuts import redirect
from django.urls import path

from . import views

app_name = "homework"


def cahier_liste_dispatch(request):
    if request.user.is_authenticated and request.user.role == request.user.Role.ENSEIGNANT:
        return redirect("homework:cahier_liste_enseignant")
    return views.cahier_classe(request)


urlpatterns = [
    path("", cahier_liste_dispatch, name="cahier_liste"),
    path("enseignant/", views.cahier_liste_enseignant, name="cahier_liste_enseignant"),
    path("seance/<int:entry_id>/", views.cahier_seance, name="cahier_seance"),
]
