# Añade "Movilidad lateral de cadera" al catálogo -- noveno de la familia
# de calentamientos/estiramientos con cámara en "Deporte -> Estiramientos
# y calentamientos" (ver 0031/.../0040 para el resto de la familia y el
# body_area="warmup" ya dejado listo en 0029).
#
# Se cuenta por repeticiones (de pie, de frente a la cámara, con los pies
# bien separados y SIN moverlos del sitio, la cadera se balancea de un
# lado a otro y vuelve al centro -- un vaivén completo cuenta como una
# repetición), así que va con mode="pose" (cámara cuenta reps) y
# counter_key en COUNTERS (tasks/views.py), no en POSTURE_COUNTERS. El
# contador de cámara ("hiplateral") vive en workout.js (processHipLateral)
# y se ha añadido también a COUNTERS en tasks/views.py, GROUND_STYLE_COUNTERS
# y NO_REST_COUNTERS en workout.js, a la vez que esta migración (no hay
# forma de que una migración de datos toque JS). circuit.js no necesita
# ningún cambio: mode="pose" ya se enruta solo a runCamera(), igual que
# el resto de ejercicios contados por repeticiones.
#
# Pedido por el usuario con un vídeo de referencia propio (subido
# 2026-09-07): pies en el suelo, con una distancia entre ellos más ancha
# que la cadera, sin moverse -- la cadera va de un lado a otro. Mismo
# espíritu de vaivén centro/lado que movilidad lateral de cuello (0034),
# pero aquí el punto que se mueve es la cadera (no la nariz) y la
# referencia fija son los tobillos (no los hombros): antes de armar el
# contador se exige que la base de apoyo (tobillo a tobillo) sea más
# ancha que la cadera, y mientras dura el vaivén se vigila que los pies
# no se desplacen (se avisa, no se penaliza, igual que el torso en
# movilidad lateral de cuello).
#
# Mismo patrón que 0031/.../0040 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="hip-lateral-mobility", name="Movilidad lateral de cadera", mode="pose", counter_key="hiplateral", order=1),
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
        ("tasks", "0040_add_seated_hamstring_stretch"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
