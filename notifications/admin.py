from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("destinataire", "type_notification", "titre", "lu", "date_creation")
    list_filter = ("type_notification", "lu")
