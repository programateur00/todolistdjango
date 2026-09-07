# Añade "Split squat" (zancada estática) al catálogo, a petición del
# usuario con un vídeo de referencia (WhatsApp, 2026-09-04): de perfil,
# de pie con una pierna delante y otra detrás, bajando la cadera hasta
# casi rozar la rodilla trasera el suelo y volviendo a subir.
#
# Pedido en DOS sitios del catálogo a la vez (Deporte -> Tren inferior Y
# Deporte -> Estiramientos y calentamientos), así que -como Exercise.body_area
# es un único valor por fila- se crean DOS filas que comparten el mismo
# counter_key="splitsquat" (mismo contador de cámara, processSplitSquat en
# workout.js), igual de espíritu que "Sentadillas"/"Sentadillas con peso"
# compartiendo counter_key="squat" (ver 0020_add_weighted_squat) pero al
# revés: aquí es el mismo movimiento el que aparece en dos subcategorías,
# no dos variantes del mismo movimiento en una subcategoría.
#
# mode="pose": la cámara cuenta las reps por el ángulo de rodilla, igual
# que sentadillas. El contador ("splitsquat") vive en workout.js
# (processSplitSquat) y se ha añadido también a COUNTERS en
# tasks/views.py y GROUND_STYLE_COUNTERS en workout.js, a la vez que esta
# migración (no hay forma de que una migración de datos toque JS). La
# entrada de tren inferior se ha etiquetado "intermediate" en
# tasks/ai._EXERCISE_DIFFICULTY (unilateral + equilibrio, más exigente
# que la sentadilla a dos piernas) -- la de calentamiento no se etiqueta,
# igual que el resto de la familia de calentamientos (arm-cross-stretch,
# arm-circles, arm-scissors...), que quedan fuera del filtro por nivel.
#
# Mismo patrón que 0031/.../0035 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="split-squat", name="Split squat", counter_key="splitsquat",
         body_area="lower_body", order=23),
    dict(slug="split-squat-warmup", name="Split squat (calentamiento)", counter_key="splitsquat",
         body_area="warmup", order=1),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for e in NEW_EXERCISES:
        Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode="pose", counter_key=e["counter_key"],
            body_area=e["body_area"], config={}, is_active=True, order=e["order"],
        ))


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0035_add_arm_scissors"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
