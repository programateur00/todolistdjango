# Rellena Exercise.level (añadido en 0084_add_exercise_level) para los
# ejercicios de fuerza (upper_body/lower_body), a petición de Alex, de
# cara a poder generar planes de deporte automáticamente por nivel más
# adelante. Solo 3 niveles a propósito (Principiante/Intermedio/
# Avanzado) -- ningún "principiante-intermedio": donde el ejercicio
# estaba a caballo, Alex decidió a cuál de los tres forzarlo.
#
# Se dejan SIN nivel (level="", el default del campo) a propósito:
#   - Todo body_area="warmup" (calentamiento/estiramientos cronometrados)
#     -- se siguen usando como calentamiento antes de la tarea (como ya
#     hay) o sueltos, pero no entran en la selección por nivel.
#   - "elephant-steps" (lower_body, pese a no ser warmup): Alex aclaró
#     que en la práctica es un estiramiento/movilidad, no un ejercicio
#     de abdomen, así que se trata igual que el resto de calentamiento
#     para este propósito.
#   - "running": tiene (o va a tener) su propio sistema de nivel vía el
#     plan -- a propósito NO tocado aquí, ni sin nivel ni con uno fijo.
#
# También crea "Dominadas anchas con peso" (slug "wide-weighted-pullup"),
# pedido explícito de Alex: copia exacta de "Dominadas con peso"
# (weighted-pullup) -- mismo mode/counter_key/body_area, mismo contador
# de cámara (no hace falta ningún cambio en workout.js: "wide-pullup" y
# "weighted-pullup" YA comparten counter_key="pullup" desde el catálogo
# original en 0002_seed_exercise_catalog, así que agarre ancho + peso es
# la misma lógica de cámara, solo cambia el nombre) -- para que el
# usuario pueda tener las dos variantes (ancho normal y ancho con peso)
# como objetivos separados. Dado de alta también en
# Exercise.WEIGHTED_SLUGS (tasks/models.py) para que los formularios de
# objetivo (plan_item_form/plan_item_bulk_form) le enseñen los campos de
# peso -- mismo criterio que weighted-pullup/weighted-dips/weighted-squat
# (ver el bug de 2026-09-26 sobre WEIGHTED_SLUGS en la nota de proyecto:
# sin esto, el peso introducido no se guardaría en este ejercicio).
#
# get_or_create idempotente para el ejercicio nuevo (mismo patrón que
# 0019/0080/0081/0082/0083); el resto es un UPDATE de datos simple,
# también idempotente (repetirlo dos veces deja el mismo resultado).

from django.db import migrations

NEW_EXERCISE = dict(
    slug="wide-weighted-pullup", name="Dominadas anchas con peso",
    mode="pose", counter_key="pullup", body_area="upper_body", order=39,
)

LEVELS = {
    # upper_body
    "push-up": "beginner",
    "dumbbell-curl": "beginner",
    "scapular-pull": "beginner",
    "dead-hang": "beginner",
    "bench-dip": "beginner",
    "jumping-pullup": "beginner",
    "dips": "intermediate",
    "pullup": "intermediate",
    "chinup": "intermediate",
    "pike-push-up": "intermediate",
    "incline-push-up": "intermediate",
    "wide-pullup": "intermediate",
    "wide-weighted-pullup": "advanced",
    "weighted-pullup": "advanced",
    "weighted-dips": "advanced",
    "archer-pullup": "advanced",
    "handstand": "advanced",
    "handstand-push-up": "advanced",
    # lower_body
    "squat": "intermediate",
    "situp": "intermediate",
    "split-squat": "beginner",
    "bicycle-crunch": "beginner",
    "crunch": "beginner",
    "leg-raise": "beginner",
    "plank": "beginner",
    "wall-sit": "beginner",
    "superman": "beginner",
    "superman-hold": "beginner",
    "side-plank": "intermediate",
    "double-crunch": "intermediate",
    "scissor-kick": "intermediate",
    "weighted-squat": "intermediate",
    "kneehold-bar": "intermediate",
    "burpee": "intermediate",
    "l-sit": "advanced",
    "l-sit-hold": "advanced",
    "tuck-lever-bar": "advanced",
}


def set_levels(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.get_or_create(slug=NEW_EXERCISE["slug"], defaults=dict(
        name=NEW_EXERCISE["name"], mode=NEW_EXERCISE["mode"], counter_key=NEW_EXERCISE["counter_key"],
        body_area=NEW_EXERCISE["body_area"], config={}, is_active=True, order=NEW_EXERCISE["order"],
    ))
    for slug, level in LEVELS.items():
        Exercise.objects.filter(slug=slug).update(level=level)


def unset_levels(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=LEVELS.keys()).update(level="")
    Exercise.objects.filter(slug=NEW_EXERCISE["slug"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0084_add_exercise_level"),
    ]

    operations = [
        migrations.RunPython(set_levels, unset_levels),
    ]
