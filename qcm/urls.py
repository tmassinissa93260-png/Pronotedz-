from django.shortcuts import redirect
from django.urls import path

from . import views

app_name = "qcm"


def qcm_dispatch(request):
    if request.user.is_authenticated and request.user.role == request.user.Role.ENSEIGNANT:
        return redirect("qcm:qcm_liste_enseignant")
    return views.qcm_liste_eleve(request)


urlpatterns = [
    path("", qcm_dispatch, name="qcm_liste"),
    path("enseignant/", views.qcm_liste_enseignant, name="qcm_liste_enseignant"),
    path("nouveau/", views.qcm_creer, name="qcm_creer"),
    path("nouveau/generer-ia/", views.qcm_generer_ia, name="qcm_generer_ia"),
    path("<int:qcm_id>/resultats/", views.qcm_resultats, name="qcm_resultats"),
    path("<int:qcm_id>/passer/", views.qcm_passer, name="qcm_passer"),
]
