# Añade "Movilidad lateral de cuello" al catálogo — cuarto de la familia
# de calentamientos/estiramientos con cámara en "Deporte -> Estiramientos
# y calentamientos" (ver 0031/0032/0033 para el resto de la familia y el
# body_area="warmup" ya dejado listo en 0029).
#
# Se cuenta por repeticiones (un vaivén completo centro -> lado -> centro
# de la cabeza/cuello), igual de espíritu que círculos de brazos, así que
# va con mode="pose" (cámara cuenta reps) y counter_key en COUNTERS
# (tasks/views.py), no en POSTURE_COUNTERS. El contador de cámara
# ("necklateral") vive en workout.js (processNeckLateral) y se ha añadido
# también a COUNTERS en tasks/views.py, GROUND_STYLE_COUNTERS y
# NO_REST_COUNTERS en workout.js, a la vez que esta migración (no hay
# forma de que una migración de datos toque JS). circuit.js no necesita
# ningún cambio: mode="pose" ya se enruta solo a runCamera(), igual que
# jumping jack, curls o círculos de brazos.
#
# Pedido por el usuario con un vídeo de referencia (WhatsApp, 2026-09-05):
# de pie o sentada/o, de frente a la cámara, la cabeza gira o se inclina
# hacia un lado y vuelve al centro. A diferencia de círculos de brazos
# (giro continuo, sin torso que vigilar), aquí el propio usuario pidió
# explícitamente comprobar que el cuello/torso no se desplace de sitio
# mientras la cabeza gira — ver processNeckLateral para el detalle de esa
# comprobación (se avisa si el punto medio de los hombros se desplaza de
# más, pero no se penaliza la repetición).
#
# Mismo patrón que 0031/0032/0033 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="neck-lateral-mobility", name="Movilidad lateral de cuello", mode="pose", counter_key="necklateral", order=1),
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
        ("tasks", "0033_add_arm_circles"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
