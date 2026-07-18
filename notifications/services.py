import logging

from django.conf import settings
from django.core.mail import send_mail

from .models import Notification

logger = logging.getLogger(__name__)


def notifier(destinataire, type_notification, titre, contenu="", lien=""):
    """Creates an in-app Notification and dispatches it over every enabled
    channel. Email is wired up now; _envoyer_sms/_envoyer_whatsapp are the
    seams to plug those channels in later without touching call sites.
    """
    notification = Notification.objects.create(
        destinataire=destinataire, type_notification=type_notification, titre=titre, contenu=contenu, lien=lien,
    )
    _envoyer_email(notification)
    # _envoyer_sms(notification)       # à activer quand un fournisseur SMS sera choisi
    # _envoyer_whatsapp(notification)  # idem pour l'API WhatsApp Business
    return notification


def notifier_plusieurs(destinataires, type_notification, titre, contenu="", lien=""):
    return [notifier(d, type_notification, titre, contenu, lien) for d in destinataires]


def notifier_email_brut(email, sujet, contenu):
    """Sends a plain email outside the Notification model, for recipients who
    have no Utilisateur account yet (e.g. prospective families in the
    admissions pipeline)."""
    if not email:
        return
    try:
        send_mail(
            subject=f"[Pronotedz] {sujet}",
            message=contenu,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,
        )
    except Exception:
        logger.exception("Échec de l'envoi d'email brut à %s", email)


def _envoyer_email(notification):
    destinataire = notification.destinataire
    if not destinataire.email:
        return
    try:
        send_mail(
            subject=f"[Pronotedz] {notification.titre}",
            message=notification.contenu or notification.titre,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[destinataire.email],
            fail_silently=True,
        )
    except Exception:
        logger.exception("Échec de l'envoi d'email pour la notification %s", notification.pk)
