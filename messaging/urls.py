from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.boite_reception, name="boite_reception"),
    path("nouvelle/", views.nouvelle_conversation, name="nouvelle_conversation"),
    path("<int:conversation_id>/", views.conversation_detail, name="conversation_detail"),
]
