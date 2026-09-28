# Añade "Tuck Lever Bar" (colgarte de la barra y subir las piernas
# dobladas muy por encima de la cabeza, cerca de la propia barra) al
# catálogo de tren inferior -- a petición explícita de Alex, que mandó
# un vídeo de referencia real (tucklever.mp4, 2026-09-27) explicando el
# ejercicio.
#
# Es un ejercicio ISOMÉTRICO (se aguanta, no se cuenta en repeticiones)
# -- mismo patrón que kneehold en barra/plancha/silla en pared:
# mode="timed" con counter_key puesto, no mode="pose". Nombre en inglés
# a propósito, igual que "Kneehold Bar"/"Scissor Kicks": así es como se
# nombró al pedirlo.
#
# El contador de cámara ("tucklever") vive en workout.js
# (checkTuckLeverPosture, junto a checkKneeHoldBarPosture) y se
# comparte con circuit.js para poder jugarlo también dentro de un
# circuito -- ver POSTURE_COUNTERS en views.py y en esos dos ficheros
# JS (más session-runner.js/workout-view.js en la app móvil), que
# también hay que actualizar a la vez que esta migración (no hay forma
# de que una migración de datos toque JS).
#
# A diferencia de kneehold en barra (que solo pide subir las rodillas
# hasta la altura de la cadera), tuck lever exige mucho más: las
# piernas dobladas tienen que subir por encima del HOMBRO, cerca de la
# barra -- analizado con el vídeo de referencia real (transcripción
# vosk-model-small-es-0.42 + contact sheets fotograma a fotograma +
# simulación con pose real PoseLandmarker VIDEO sobre todo el vídeo a
# ~10fps). Ver el comentario junto a checkTuckLeverPosture en
# workout.js para el detalle completo (por qué no sirve mirar
# cadera-hombro como en el pino, y por qué el chequeo de la pierna es
# más laxo una vez ya aguantando).
#
# Mismo patrón que 0015/0068/.../0077 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="tuck-lever-bar", name="Tuck Lever Bar", mode="timed", counter_key="tucklever", order=36),
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
        ("tasks", "0079_planitem_weekly_linear"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
