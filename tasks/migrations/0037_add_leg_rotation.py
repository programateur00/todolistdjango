# Añade "Rotación de piernas" al catálogo -- sexto de la familia de
# calentamientos/estiramientos con cámara en "Deporte -> Estiramientos y
# calentamientos" (ver 0031/0032/0033/0034/0035 para el resto de la
# familia y el body_area="warmup" ya dejado listo en 0029).
#
# Se cuenta por repeticiones (de pie, en equilibrio sobre una pierna, se
# levanta la otra rodilla y se gira alrededor de la cadera antes de
# volver a apoyar el pie), así que va con mode="pose" (cámara cuenta
# reps) y counter_key en COUNTERS (tasks/views.py), no en
# POSTURE_COUNTERS. El contador de cámara ("legrotation") vive en
# workout.js (processLegRotation) y se ha añadido también a COUNTERS en
# tasks/views.py, GROUND_STYLE_COUNTERS y NO_REST_COUNTERS en
# workout.js, a la vez que esta migración (no hay forma de que una
# migración de datos toque JS). circuit.js no necesita ningún cambio:
# mode="pose" ya se enruta solo a runCamera(), igual que el resto de
# ejercicios contados por repeticiones.
#
# Pedido por el usuario con dos vídeos de referencia (WhatsApp,
# 2026-09-06): detectar el giro por la rodilla, sin ser muy estricto con
# el umbral; que tocar el suelo con el pie entre repeticiones no rompa
# nada (a diferencia del resto de la familia, aquí apoyar el pie es el
# cierre normal de cada repetición, no un fallo); y que más de 5
# segundos sin hacer nada entre repeticiones cierre la serie sola y
# empiece una nueva (LEGROTATION_STILL_MS=5000, más largo que el resto
# de la familia porque así se pidió explícitamente).
#
# Mismo patrón que 0031/.../0036 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="leg-rotation", name="Rotación de piernas", mode="pose", counter_key="legrotation", order=1),
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
        ("tasks", "0036_add_split_squat"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
