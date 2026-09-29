# Split squat del calentamiento de tren inferior: de 30 a 15 reps (Alex, 2026-09-30).
# Actualiza los RoutineItem existentes para que el cambio se aplique solo al migrar,
# sin re-lanzar seed_warmup_routines (que tambien queda a 15). Idempotente.

from django.db import migrations


def set_15_reps(apps, schema_editor):
    RoutineItem = apps.get_model("tasks", "RoutineItem")
    RoutineItem.objects.filter(
        exercise__slug="split-squat-warmup",
        routine__is_warmup_bookend=True,
    ).update(target_reps=15)


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0088_remove_wrist_rotation"),
    ]

    operations = [
        migrations.RunPython(set_15_reps, migrations.RunPython.noop),
    ]
