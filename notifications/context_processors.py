from .models import Notification


def notifications_non_lues(request):
    if not request.user.is_authenticated:
        return {}
    qs = Notification.objects.filter(destinataire=request.user)
    return {
        "notifications_non_lues_count": qs.filter(lu=False).count(),
        "notifications_recentes": qs[:6],
    }
