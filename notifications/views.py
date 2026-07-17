from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Notification


@login_required
def liste(request):
    notifications = Notification.objects.filter(destinataire=request.user)
    return render(request, "notifications/liste.html", {"notifications": notifications})


@login_required
def marquer_lu(request, notification_id):
    notification = get_object_or_404(Notification, pk=notification_id, destinataire=request.user)
    notification.lu = True
    notification.save()
    return redirect(notification.lien or "notifications:liste")


@login_required
def marquer_tout_lu(request):
    Notification.objects.filter(destinataire=request.user, lu=False).update(lu=True)
    return redirect("notifications:liste")
