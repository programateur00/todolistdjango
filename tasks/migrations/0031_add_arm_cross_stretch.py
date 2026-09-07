# Añade "Estiramiento cruzado de brazo" al catálogo, a petición del
# usuario: primero de una futura familia de estiramientos con cámara,
# pensados para "Deporte -> Estiramientos y calentamientos"
# (Task.SUBCATEGORY_WARMUP/body_area="warmup" — ver 0029, que ya dejó
# preparado el valor pero sin ningún ejercicio real usándolo todavía).
#
# Es un ejercicio ISOMÉTRICO (se aguanta, no se cuenta en repeticiones)
# — mismo patrón que plancha/silla en pared/etc.: mode="timed" con
# counter_key puesto, no mode="pose". El contador de cámara
# ("armcrossstretch") vive en workout.js (checkStandbyPosture +
# checkArmCrossStretch) y se ha añadido también a POSTURE_COUNTERS en
# tasks/views.py y circuit.js, a la vez que esta migración (no hay forma
# de que una migración de datos toque JS).
#
# La cámara se coloca DE FRENTE (a diferencia de silla en pared, que va
# de perfil): hace falta ver los dos brazos a la vez para comprobar que
# uno se estira cruzando el pecho y el otro lo agarra por el codo.
#
# Mismo patrón que 0012/0014 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="arm-cross-stretch", name="Estiramiento cruzado de brazo", mode="timed", counter_key="armcrossstretch", order=1),
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
        ("tasks", "0030_add_bench_dip"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
