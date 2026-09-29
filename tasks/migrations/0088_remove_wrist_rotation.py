# Elimina "Rotación de muñecas" del catálogo (pedido de Alex, 2026-09-29).
# Al borrar el Exercise, sus ítems en rutinas/circuitos (FK CASCADE) se van
# con él. El contador de cámara ("wristrotation") ya se quitó de workout.js,
# views.COUNTERS y seed_warmup_routines.py.

from django.db import migrations

SLUG = "wrist-rotation-interlaced"


def remove_exercise(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug=SLUG).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0087_task_reading_pending_seconds_and_more"),
    ]

    operations = [
        migrations.RunPython(remove_exercise, migrations.RunPython.noop),
    ]
