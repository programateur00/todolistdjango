# Añade "Tijeras de brazos" al catálogo -- quinto de la familia de
# calentamientos/estiramientos con cámara en "Deporte -> Estiramientos y
# calentamientos" (ver 0031/0032/0033/0034 para el resto de la familia y
# el body_area="warmup" ya dejado listo en 0029).
#
# Se cuenta por repeticiones (un vaivén completo brazos extendidos en
# cruz -> cruzados por delante del pecho -> extendidos), igual de
# espíritu que círculos de brazos/movilidad lateral de cuello, así que
# va con mode="pose" (cámara cuenta reps) y counter_key en COUNTERS
# (tasks/views.py), no en POSTURE_COUNTERS. El contador de cámara
# ("armscissors") vive en workout.js (processArmScissors) y se ha
# añadido también a COUNTERS en tasks/views.py, GROUND_STYLE_COUNTERS y
# NO_REST_COUNTERS en workout.js, a la vez que esta migración (no hay
# forma de que una migración de datos toque JS). circuit.js no necesita
# ningún cambio: mode="pose" ya se enruta solo a runCamera(), igual que
# el resto de ejercicios contados por repeticiones.
#
# Pedido por el usuario con un vídeo de referencia (WhatsApp, 2026-09-06):
# de pie, de frente a la cámara, los brazos se extienden en cruz (a los
# lados) y se cruzan por delante, volviendo después a extendidos. Nueva
# serie al bajar los brazos unos segundos (cierre automático por
# quietud, mismo patrón que el resto de la familia -- ver ARMSCISSORS_STILL_MS).
#
# Mismo patrón que 0031/0032/0033/0034 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="arm-scissors", name="Tijeras de brazos", mode="pose", counter_key="armscissors", order=1),
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
        ("tasks", "0034_add_neck_lateral_mobility"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
