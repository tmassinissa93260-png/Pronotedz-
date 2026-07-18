from django.core.management.base import BaseCommand

from accounts.models import Parent
from notifications.services import notifier_email_brut

from ...services import construire_rapport


def _envoyer_whatsapp(numero, corps):
    """Seam for a future WhatsApp Business API integration — same idea as
    notifications._envoyer_sms. No-op until a provider is chosen; the
    weekly report already reaches parents by email in the meantime."""
    pass


class Command(BaseCommand):
    help = (
        "Envoie à chaque parent un résumé hebdomadaire par enfant (notes, absences, "
        "devoirs à venir) dans sa langue préférée. Prévu pour être planifié chaque "
        "vendredi (cron externe : `python manage.py envoyer_rapports_hebdomadaires`)."
    )

    def handle(self, *args, **options):
        nb_envoyes = 0
        for parent in Parent.objects.select_related("user").prefetch_related("enfants__user"):
            for enfant in parent.enfants.all():
                sujet, corps = construire_rapport(enfant, langue=parent.user.langue_notifications)
                notifier_email_brut(parent.user.email, sujet, corps)
                _envoyer_whatsapp(parent.user.telephone, corps)
                nb_envoyes += 1

        self.stdout.write(f"{nb_envoyes} rapport(s) hebdomadaire(s) envoyé(s).")
