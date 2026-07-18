from django.db import migrations, models
from django.utils.text import slugify


def backfill_slugs(apps, schema_editor):
    Etablissement = apps.get_model("academics", "Etablissement")
    seen = set()
    for etablissement in Etablissement.objects.all():
        base = slugify(etablissement.nom) or "etablissement"
        slug = base
        suffixe = 1
        while slug in seen:
            suffixe += 1
            slug = f"{base}-{suffixe}"
        seen.add(slug)
        etablissement.slug = slug
        etablissement.save(update_fields=["slug"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0006_salle_etablissement"),
    ]

    operations = [
        migrations.AddField(
            model_name="etablissement",
            name="slug",
            field=models.SlugField(
                blank=True,
                null=True,
                help_text="Utilisé dans les URLs publiques (candidature, portail vitrine).",
                max_length=220,
            ),
        ),
        migrations.RunPython(backfill_slugs, noop),
        migrations.AlterField(
            model_name="etablissement",
            name="slug",
            field=models.SlugField(
                blank=True,
                unique=True,
                help_text="Utilisé dans les URLs publiques (candidature, portail vitrine).",
                max_length=220,
            ),
        ),
    ]
