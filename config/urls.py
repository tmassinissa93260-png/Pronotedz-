from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from dashboard.views import dispatch as dashboard_dispatch

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("emploi-du-temps/", include("timetable.urls")),
    path("absences/", include("attendance.urls")),
    path("notes/", include("grades.urls")),
    path("cahier-de-texte/", include("homework.urls")),
    path("messagerie/", include("messaging.urls")),
    path("vie-scolaire/", include("vie_scolaire.urls")),
    path("actualites/", include("actualites.urls")),
    path("rendez-vous/", include("rendezvous.urls")),
    path("ressources/", include("ressources.urls")),
    path("documents/", include("documents.urls")),
    path("sondages/", include("sondages.urls")),
    path("qcm/", include("qcm.urls")),
    path("", dashboard_dispatch, name="home"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
