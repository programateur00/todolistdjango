# "V-ups" (0106) pasa a tener contador PROPIO, "vup" (processVUp en workout.js),
# en vez de compartir "doublecrunch": con ese contador salía un rodillas al
# pecho (Alex, 2026-10-11). Para quien ya tuviera aplicada 0106 con el
# contador anterior; en una base nueva 0106 ya lo crea con "vup" y esto no
# cambia nada. Solo toca ese slug.

from django.db import migrations


def to_vup_counter(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug="v-up").update(counter_key="vup")


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0108_jump_squat_own_counter"),
    ]

    operations = [
        migrations.RunPython(to_vup_counter, migrations.RunPython.noop),
    ]
