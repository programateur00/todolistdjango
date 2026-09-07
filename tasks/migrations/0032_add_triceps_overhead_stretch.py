# Añade "Estiramiento de tríceps por encima de la cabeza" al catálogo —
# segundo de la familia de estiramientos con cámara, en "Deporte ->
# Estiramientos y calentamientos" (mismo patrón que 0031, ver ese
# fichero para el porqué de la familia).
#
# Es un ejercicio ISOMÉTRICO (se aguanta, no se cuenta en repeticiones)
# — mismo patrón que el cruzado de brazo: mode="timed" con counter_key
# puesto, no mode="pose". El contador de cámara
# ("tricepsoverheadstretch") vive en workout.js (checkStandbyPosture +
# checkTricepsOverheadStretch) y se ha añadido también a
# POSTURE_COUNTERS en tasks/views.py y circuit.js, a la vez que esta
# migración (no hay forma de que una migración de datos toque JS).
#
# La cámara se coloca DE FRENTE (igual que el cruzado de brazo, a
# petición expresa) — hace falta ver los dos brazos y la cabeza a la
# vez para comprobar que uno se dobla por detrás de la nuca y el otro
# agarra el codo.
#
# Mismo patrón que 0031 (siembra el catálogo, get_or_create idempotente
# para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="triceps-overhead-stretch", name="Estiramiento de tríceps por encima de la cabeza", mode="timed", counter_key="tricepsoverheadstretch", order=1),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for e in NEW_EXERCISES:
        Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode=e["mode"], counter_key=e["counter_key"],
            body_area="warmup", config={}, is_active=True, order=e["order"],
        ))


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0031_add_arm_cross_stretch"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
