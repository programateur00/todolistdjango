# Añade "Dominadas de arquero" al catálogo, a petición del usuario: al
# subir, un brazo se dobla ~90° (el que tira) y el otro va estirado (se
# desliza por la barra), alternando de lado en cada repetición. El
# contador vive en workout.js, en processArcherPullup(), indexado por
# counter_key "archerpullup" (ver processResult en workout.js) — también
# hay que darlo de alta en COUNTERS (tasks/views.py) para que
# task_workout lo trate como soportado por cámara.
#
# Mismo patrón que 0012/0014/0015/0017/0018 (siembra el catálogo para
# instalaciones nuevas, get_or_create idempotente) — este ejercicio no
# existía antes, así que no hace falta migrar nada de estado viejo, solo
# crearlo si falta.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="archer-pullup", name="Dominadas de arquero", mode="pose", counter_key="archerpullup", order=21),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for e in NEW_EXERCISES:
        Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode=e["mode"], counter_key=e["counter_key"],
            body_area="upper_body", config={}, is_active=True, order=e["order"],
        ))


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0018_add_dead_hang"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
