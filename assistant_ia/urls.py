from django.urls import path

from . import views

app_name = "assistant_ia"

urlpatterns = [
    path("", views.conversation_liste, name="conversation_liste"),
    path("nouvelle/", views.conversation_nouvelle, name="conversation_nouvelle"),
    path("<int:conversation_id>/", views.conversation_detail, name="conversation_detail"),
]
