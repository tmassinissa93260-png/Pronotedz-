from django.core.management.base import BaseCommand

from accounts.models import Eleve, Utilisateur
from notifications.models import Notification
from notifications.services import notifier

from ...models import AlerteDecrochage
from ...services import SEUIL_ALERTE, calculer_score, calculer_signaux


class Command(BaseCommand):
    help = "Analyse les signaux faibles de décrochage scolaire pour chaque élève et crée des alertes si nécessaire."

    def handle(self, *args, **options):
        nb_alertes_creees = 0
        for eleve in Eleve.objects.select_related("classe", "classe__professeur_principal__user", "user__etablissement"):
            signaux = calculer_signaux(eleve)
            if not signaux:
                continue
            score = calculer_score(signaux)
            if score < SEUIL_ALERTE:
                continue

            alerte_existante = AlerteDecrochage.objects.filter(
                eleve=eleve, statut__in=[AlerteDecrochage.Statut.NOUVELLE, AlerteDecrochage.Statut.EN_COURS],
            ).exists()
            if alerte_existante:
                continue

            alerte = AlerteDecrochage.objects.create(eleve=eleve, score_risque=score, signaux=signaux)
            nb_alertes_creees += 1

            destinataires = list(
                Utilisateur.objects.filter(role=Utilisateur.Role.ADMIN, etablissement=eleve.user.etablissement)
            )
            professeur_principal = eleve.classe.professeur_principal
            if professeur_principal:
                destinataires.append(professeur_principal.user)

            for destinataire in destinataires:
                notifier(
                    destinataire, Notification.Type.DECROCHAGE,
                    titre=f"Signal de décrochage — {eleve.user.get_full_name()}",
                    contenu=f"Score de risque : {score}. {len(signaux)} signal(aux) détecté(s).",
                    lien=f"/decrochage/{alerte.pk}/",
                )

        self.stdout.write(f"{nb_alertes_creees} nouvelle(s) alerte(s) de décrochage créée(s).")
