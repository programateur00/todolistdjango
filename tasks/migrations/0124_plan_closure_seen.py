from django.db import migrations, models
from django.db.models import F


def backfill_seen(apps, schema_editor):
    """Los planes ya cerrados antes de este cambio cuentan como vistos: si no,
    la lista de tareas los anunciaría todos de golpe."""
    Plan = apps.get_model("tasks", "Plan")
    Plan.objects.filter(closed_at__isnull=False, closure_seen_at__isnull=True).update(
        closure_seen_at=F("closed_at")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0123_planitem_playlist_position"),
    ]

    operations = [
        migrations.AddField(
            model_name="plan",
            name="closure_seen_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_seen, migrations.RunPython.noop),
    ]
