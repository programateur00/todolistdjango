# Añade "Círculos de brazos" al catálogo — tercero de la familia de
# calentamientos/estiramientos con cámara en "Deporte -> Estiramientos y
# calentamientos" (ver 0031/0032 para el resto de la familia y el
# body_area="warmup" ya dejado listo en 0029).
#
# A diferencia de los dos anteriores (armcrossstretch/tricepsoverheadstretch,
# ejercicios ISOMÉTRICOS con mode="timed"), este SÍ se cuenta por
# repeticiones — un círculo completo de los dos brazos a la vez, igual de
# espíritu que jumping jack — así que va con mode="pose" (cámara cuenta
# reps) y counter_key en COUNTERS (tasks/views.py), no en POSTURE_COUNTERS.
# El contador de cámara ("armcircles") vive en workout.js
# (processArmCircles) y se ha añadido también a COUNTERS en
# tasks/views.py, GROUND_STYLE_COUNTERS y NO_REST_COUNTERS en workout.js,
# a la vez que esta migración (no hay forma de que una migración de datos
# toque JS). circuit.js no necesita ningún cambio: mode="pose" ya se
# enruta solo a runCamera(), igual que jumping jack o los curls.
#
# Pedido por el usuario con un vídeo de referencia (WhatsApp, 2026-09-05):
# de pie, de frente a la cámara, los dos brazos extendidos giran a la vez
# —primero hacia delante y luego, dentro de la MISMA serie, la cámara
# cambia sola el sentido esperado a "hacia atrás" (ver processArmCircles
# para el detalle del cambio de fase).
#
# Mismo patrón que 0031/0032 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="arm-circles", name="Círculos de brazos", mode="pose", counter_key="armcircles", order=1),
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
        ("tasks", "0032_add_triceps_overhead_stretch"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
