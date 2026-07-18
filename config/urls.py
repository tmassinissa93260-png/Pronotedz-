from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.i18n import set_language

from academics.views import portail_public
from dashboard.views import dispatch as dashboard_dispatch

urlpatterns = [
    path("i18n/setlang/", set_language, name="set_language"),
    path("ecole/<slug:slug>/", portail_public, name="portail_public"),
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
    path("notifications/", include("notifications.urls")),
    path("admissions/", include("admissions.urls")),
    path("assistant-ia/", include("assistant_ia.urls")),
    path("decrochage/", include("decrochage.urls")),
    path("revisions/", include("revisions.urls")),
    path("rapport-parent/", include("rapport_parent.urls")),
    path("finance/", include("finance.urls")),
    path("academics/", include("academics.urls")),
    path("", include("pwa.urls")),
    path("", dashboard_dispatch, name="home"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
