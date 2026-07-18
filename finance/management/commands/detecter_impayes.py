from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.services import notifier_email_brut

from ...models import Facture
from ...services import recalculer_statut


class Command(BaseCommand):
    help = (
        "Marque en retard les factures impayées dont l'échéance est dépassée et envoie un "
        "rappel par email aux parents. Prévu pour être planifié quotidiennement par un cron externe."
    )

    def handle(self, *args, **options):
        nb_rappels = 0
        factures = (
            Facture.objects.exclude(statut=Facture.Statut.PAYEE)
            .select_related("eleve__user", "frais")
            .filter(frais__date_echeance__lt=timezone.now().date())
        )
        for facture in factures:
            recalculer_statut(facture)
            if facture.statut != Facture.Statut.EN_RETARD:
                continue
            for parent in facture.eleve.parents.select_related("user"):
                notifier_email_brut(
                    parent.user.email,
                    f"Frais en retard — {facture.eleve.user.get_full_name()}",
                    (
                        f"Le paiement de « {facture.frais.libelle} » ({facture.montant_restant} DA restant) "
                        f"pour {facture.eleve.user.get_full_name()} est en retard depuis "
                        f"le {facture.frais.date_echeance:%d/%m/%Y}."
                    ),
                )
                nb_rappels += 1

        self.stdout.write(f"{nb_rappels} rappel(s) d'impayé envoyé(s).")
