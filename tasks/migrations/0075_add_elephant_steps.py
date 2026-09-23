# Añade "Elephant steps" al catálogo -- pedido por Alex con un vídeo de
# referencia real (elephant_steps_reps.mp4, ~78s, subido 2026-09-23).
#
# De pie, de perfil a la cámara: doblar la cadera para tocar el suelo
# (rodillas dobladas si hace falta -- Alex pidió explícitamente que NO
# se exija pierna recta, solo intentarlo con el tiempo) y volver a
# soltar. Analizado con audio (transcripción vosk-model-small-es-0.42,
# calidad baja por ruido de gimnasio) y con pose REAL sobre el vídeo
# (PoseLandmarker + modelo vendorizado, VIDEO mode, misma técnica ya
# usada con rotación de codos/círculos de brazos el 2026-09-22): el
# vídeo real muestra un vaivén rápido de amplitud corta (ángulo de
# cadera entre ~25°-43°, cada toque ~1-2s) con paradas de pie completas
# entre ráfagas a modo de descanso, no un único ciclo pie-a-tocar-y-pie
# por serie.
#
# Se cuenta por repeticiones (mode="pose"), contador "elephantsteps" en
# workout.js (processElephantSteps, ambas copias: mobile-app y
# libreta-todo-django), añadido también a COUNTERS en tasks/views.py y
# en el COUNTERS de mobile-app/www/js/workout-view.js (para poder
# abrirlo suelto, no solo dentro de un circuito). body_area="lower_body",
# mismo grupo que sentadillas/split squat/superman/l-sit (más
# trabajo de pierna/cadera que un estiramiento cronometrado puro).
#
# Umbrales ELEPHANTSTEPS_* calibrados directamente contra la pose real
# de ESTE vídeo de referencia -- primer valor con un solo cuerpo,
# pendiente de confirmar con cámara real (sobre todo móvil, que es
# donde Alex pidió más atención porque "siempre da problemas") y de
# relajar si a alguien menos flexible no le llega a bajar del umbral.
#
# Mismo patrón que 0068/.../0074 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="elephant-steps", name="Elephant steps", mode="pose", counter_key="elephantsteps", order=32),
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
        ("tasks", "0074_add_high_leg_raise"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
