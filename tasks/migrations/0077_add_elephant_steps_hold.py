# Añade "Pasos de elefante (aguante)" -- versión cronometrada del mismo
# ejercicio que "Elephant steps" (0075), pedida explícitamente por Alex:
# "añade este ejercicio que deberia ir como los de cronometro, agunatando,
# como el L sit hold, o el superman hold". De pie, de perfil a la cámara,
# doblado por la cadera con el pecho hacia las piernas -- se aguanta el
# tiempo objetivo en vez de contar repeticiones.
#
# Analizado con el mismo vídeo de referencia real (elephant_steps.mp4,
# transcripción vosk-model-small-es-0.42 + pose real fotograma a fotograma
# con PoseLandmarker/VIDEO mode) que ya se usó para calibrar la versión de
# repeticiones. Mismo criterio de postura que processElephantSteps: se mide
# el ÁNGULO DE CADERA (hombro-cadera-rodilla), nunca el de rodilla -- Alex
# pidió explícitamente que quien no llegue a tocar el suelo con las piernas
# rectas pueda doblar las rodillas y que eso cuente igual, mientras note
# tensión. Ver checkElephantStepsHold / ELEPHANTSTEPSHOLD_* en workout.js.
#
# mode="timed", counter_key="elephantstepshold" -- añadido también a
# POSTURE_COUNTERS en tasks/views.py, mobile-app/www/js/workout-view.js,
# mobile-app/www/js/session-runner.js y libreta-todo-django/static/js/circuit.js
# (mismo patrón que plancha/silla en pared/L-sit hold/superman hold: postura
# con cámara propia, se puede abrir suelto o dentro de un circuito).
# body_area="warmup", mismo grupo que los otros estiramientos con aguante
# (isquios sentado, cuádriceps de pie) -- es una postura mantenida de
# flexibilidad, no trabajo de fuerza cíclico como la versión de reps.
#
# Mismo patrón que 0068/.../0076 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="elephant-steps-hold", name="Pasos de elefante (aguante)", mode="timed", counter_key="elephantstepshold", order=35),
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
        ("tasks", "0076_add_burpee"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
