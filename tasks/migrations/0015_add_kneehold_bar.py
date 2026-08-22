# Añade "Kneehold Bar" (colgarse de la barra, subir las rodillas y
# aguantar) al catálogo de tren inferior, a petición del usuario — mismo
# grupo que plancha/crunch/elevación de piernas/silla en pared: lo que
# se trabaja es el abdomen y la cadera al subir las rodillas, no el
# agarre (que solo sostiene el cuerpo, igual que el suelo sostiene una
# plancha). Corregido de tren superior a tren inferior en
# 0016_kneehold_bar_lower_body — ver ese archivo si esta migración ya
# se había aplicado con el valor antiguo.
#
# Es un ejercicio ISOMÉTRICO (se aguanta, no se cuenta en repeticiones) —
# mismo patrón que plancha/plancha lateral/silla en pared: mode="timed"
# con counter_key puesto, no mode="pose". El nombre se deja en inglés a
# propósito, igual que "Scissor Kicks" (ver 0013_rename_scissor_kick):
# así es como lo pidió quien lo encargó.
#
# El contador de cámara ("kneeholdbar") vive en workout.js
# (checkKneeHoldBarPosture) y se comparte con circuit.js para poder
# jugarlo también dentro de un circuito — ver POSTURE_COUNTERS en
# views.py y en esos dos archivos JS (más session-runner.js/workout-view.js
# en la app móvil), que también hay que actualizar a la vez que esta
# migración (no hay forma de que una migración de datos toque JS).
#
# A diferencia de plancha/plancha lateral/silla en pared, aquí SÍ hace
# falta verte colgado de la barra (brazos estirados, agarre activo) —
# reutiliza la misma detección de "colgado" que ya usan las dominadas
# (HANG_MARGIN_FACTOR), pero sin la calibración de altura de barra: no
# se cuentan repeticiones, así que no hace falta saber dónde está la
# barra, solo que sigues agarrada/o a ella.
#
# Mismo patrón que 0014 (siembra el catálogo para instalaciones nuevas,
# get_or_create idempotente para quien ya la haya aplicado): este
# ejercicio no existía antes, así que no hace falta ningún "pasa de
# estado viejo a nuevo" como en 0011, solo crearlo si falta.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="kneehold-bar", name="Kneehold Bar", mode="timed", counter_key="kneeholdbar", order=18),
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
        ("tasks", "0014_add_wall_sit"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
