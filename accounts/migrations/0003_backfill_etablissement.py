from django.db import migrations


def backfill_etablissement(apps, schema_editor):
    Etablissement = apps.get_model("academics", "Etablissement")
    AnneeScolaire = apps.get_model("academics", "AnneeScolaire")
    Utilisateur = apps.get_model("accounts", "Utilisateur")

    etablissement = Etablissement.objects.first()
    if not etablissement:
        return
    AnneeScolaire.objects.filter(etablissement__isnull=True).update(etablissement=etablissement)
    Utilisateur.objects.filter(etablissement__isnull=True).update(etablissement=etablissement)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_utilisateur_etablissement"),
        ("academics", "0005_anneescolaire_etablissement_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_etablissement, noop),
    ]
