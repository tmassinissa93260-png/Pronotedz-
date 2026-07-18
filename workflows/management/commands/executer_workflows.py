from django.core.management.base import BaseCommand

from ...services import executer_toutes_les_regles


class Command(BaseCommand):
    help = (
        "Évalue toutes les règles de workflow actives (notes basses, retards fréquents, "
        "devoirs non rendus) et déclenche les notifications correspondantes. Prévu pour "
        "être planifié quotidiennement par un cron externe."
    )

    def handle(self, *args, **options):
        nb = executer_toutes_les_regles()
        self.stdout.write(f"{nb} déclenchement(s) de règle(s) de workflow.")
