# Retira "Mountain climbers" (2026-09-20): se añadió en 0071 y se descartó -- el conteo por cámara no fue fiable.
# Borra la fila del catálogo (y, por cascada, lo que colgara de ella). 0071 se conserva para no romper el historial
# de migraciones donde ya se aplicó. Idempotente; la marcha atrás no la restaura.

from django.db import migrations


def remove_exercise(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug="mountain-climber").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0071_add_mountain_climber"),
    ]

    operations = [
        migrations.RunPython(remove_exercise, migrations.RunPython.noop),
    ]
