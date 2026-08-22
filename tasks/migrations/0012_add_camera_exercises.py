# Añade dos ejercicios nuevos de abdominales con cámara, a petición del
# usuario: doble crunch (torso ya levantado y sube/baja las rodillas al
# pecho) y tijeretas (piernas estiradas a un palmo del suelo,
# alternando cuál va arriba). Los contadores viven en workout.js,
# indexados por counter_key ("doublecrunch" / "scissor") — ver
# COUNTERS en views.py.
#
# Mismo patrón que 0002 (siembra el catálogo para instalaciones nuevas)
# pero sin necesitar un 0011-style "pasa de estado viejo a nuevo": estos
# ejercicios no EXISTÍAN antes, así que no hay nada que migrar, solo
# crearlos si faltan (get_or_create, idempotente para quien ya la haya
# aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="double-crunch", name="Doble crunch", mode="pose", counter_key="doublecrunch", order=13),
    dict(slug="scissor-kick", name="Scissor Kicks", mode="pose", counter_key="scissor", order=14),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for e in NEW_EXERCISES:
        Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode=e["mode"], counter_key=e["counter_key"],
            body_area="lower_body", config={}, is_active=True, order=e["order"],
        ))


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0011_camera_exercise_updates"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
