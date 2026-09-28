# Añade "Dominadas escapulares" (scapular pulls) al catálogo de tren
# superior, a petición de Alex, que mandó un vídeo de referencia real
# (scpular_pullups.mp4, 2026-09-27) explicando el ejercicio.
#
# A diferencia de las dominadas normales o de arquero: aquí NO se dobla
# el codo -- colgado de la barra con los brazos totalmente estirados, el
# movimiento es solo deprimir/retraer el omóplato para subir el cuerpo
# un poco y volver a bajar con control. Es un ejercicio de REPETICIONES
# (mode="pose" con counter_key, igual que "pullup"/"archerpullup"), NO
# isométrico -- a diferencia de Kneehold Bar/Tuck Lever Bar/Dead Hang
# (esos sí aguantan quietos, mode="timed").
#
# El contador de cámara ("scapularpull") vive en workout.js
# (processScapularPull, junto a processArcherPullup) -- analizado con el
# vídeo de referencia real (transcripción vosk-model-small-es-0.42 +
# contact sheets fotograma a fotograma + simulación con pose real
# PoseLandmarker VIDEO sobre todo el vídeo a ~10fps): el HOMBRO (no la
# nariz, que es lo que usan las dominadas normales) sube y baja de forma
# consistente ~0.18 anchos-de-hombro en dos tomas distintas del mismo
# vídeo (de espaldas y de frente) -- señal clara y por encima del ruido
# de tracking en quieto. A diferencia de una dominada normal, nunca se
# acerca a la barra, así que no hay comprobación de "llegaste arriba":
# solo subir lo suficiente y volver a bajar lo suficiente (ver
# SCAPULARPULL_MOVE_FACTOR/SCAPULARPULL_LIFTOFF_FACTOR en workout.js).
#
# También dado de alta en COUNTERS (tasks/views.py) para que
# task_workout lo trate como soportado por cámara, y en el COUNTERS de
# workout-view.js/exercise-icons.js (app móvil) para que abra suelto
# desde "¿Qué toca hoy?" con la silueta de dominadas (mismo criterio que
# kneehold-bar/archer-pullup, que reutilizan esa misma ilustración).
#
# Mismo patrón que 0019/0080 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="scapular-pull", name="Dominadas escapulares", mode="pose", counter_key="scapularpull", order=37),
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
        ("tasks", "0080_add_tuck_lever"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
