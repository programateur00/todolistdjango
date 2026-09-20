# Recupera el Superman en el catálogo, ahora con cámara y en sus dos variantes (2026-09-20).
# (La 0011 lo había borrado cuando no tenía contador; el slug "superman" queda libre otra vez.)
#
#   - "superman" (mode="pose", counter_key="superman"): repeticiones. Tumbado boca abajo, estirado, con
#     brazos y piernas en el suelo; cuenta cada vez que se levantan A LA VEZ brazos y piernas. La serie se
#     rompe al levantarse o al salir del encuadre.
#   - "superman-hold" (mode="timed", counter_key="supermanhold"): el mismo chequeo (brazos+piernas
#     levantados) pero aguantado -- se cuentan segundos, igual que plancha/L-sit hold (por eso es "timed"
#     con counter_key, ver POSTURE_COUNTERS en views.py).
#
# Los dos contadores viven en workout.js (SupermanTracker / processSuperman / processSupermanHold /
# createSupermanHoldChecker), en la copia web y en la de la app móvil. body_area="lower_body" (en la app:
# "Tren inferior / core") -- mismo grupo que leg-raise y l-sit: trabajo de core/zona lumbar.
#
# Mismo patrón que 0068 (get_or_create idempotente; no toca filas ya existentes con ese slug).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="superman", name="Superman", mode="pose", counter_key="superman", order=28),
    dict(slug="superman-hold", name="Superman (hold)", mode="timed", counter_key="supermanhold", order=29),
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
        ("tasks", "0068_add_lsit_parallel_bars"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
