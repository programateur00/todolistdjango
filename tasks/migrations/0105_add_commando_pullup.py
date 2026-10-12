# Ejercicio nuevo "Dominadas commando" (slug "commando-pullup"), pedido por Alex
# (2026-10-11). Tren superior.
#
# Dominada con agarre alterno "uno detrás del otro" (una mano delante de la
# otra en la barra), con el cuerpo alineado con la barra: en cada repetición
# la cabeza sube por un lado de la barra, y en la siguiente por el otro.
#
# Sin contador nuevo: misma regla que 0100/0104 -- las variantes que la cámara
# no distingue comparten el contador del ejercicio base y hacerlas bien es
# cosa del usuario. counter_key="pullup" (processResult/processPullup en
# workout.js): mide la nariz subiendo hasta ~la altura de la barra (la barra
# se calibra con la altura de las muñecas) y volviendo a bajar. En la commando
# la cabeza queda al lado de la barra con la barbilla a su altura o por encima,
# así que el criterio "nariz <= barra + 0.25 anchos de hombro" se cumple igual.
# Sin tocar workout.js ni las apps (solo la lista NEEDS_BAR_SLUGS de
# plan-view.js, que es un aviso en el selector).
#
# Nivel "advanced" (más exigente que "pullup", que es "intermediate":
# trabajo unilateral y asimétrico). MET 8.0 como "pullup" (0096). order 52,
# detrás de "sumo-squat"/"jump-squat" (50/51). get_or_create idempotente.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="commando-pullup", name="Dominadas commando",
         mode="pose", counter_key="pullup", body_area="upper_body",
         level="advanced", met=8.0, order=52),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for ex in NEW_EXERCISES:
        Exercise.objects.get_or_create(slug=ex["slug"], defaults=dict(
            name=ex["name"], mode=ex["mode"], counter_key=ex["counter_key"],
            body_area=ex["body_area"], level=ex["level"], met=ex["met"],
            config={}, is_active=True, order=ex["order"],
        ))


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0104_add_squat_variants"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
