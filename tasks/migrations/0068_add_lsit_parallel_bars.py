# Añade el L-sit en paralelas al catálogo, en sus dos variantes (2026-09-20):
#
#   - "l-sit" (mode="pose", counter_key="lsit"): repeticiones. Se arma al
#     SUBIRTE a las paralelas (la cámara aprende tu altura de pie y detecta
#     que el tronco sube) y cuenta cada vez que subes las piernas rectas
#     a la L (rodilla y tobillo a la altura de la cadera) y las bajas del
#     todo.
#   - "l-sit-hold" (mode="timed", counter_key="lsithold"): el mismo chequeo
#     de "piernas en L" pero aguantado -- se cuentan segundos, igual que
#     plancha/silla en pared/kneehold (por eso es "timed" con counter_key,
#     ver POSTURE_COUNTERS en views.py).
#
# Los dos contadores viven en workout.js (LSitTracker / processLSit /
# createLSitHoldChecker), en la copia web y en la de la app móvil.
# body_area="lower_body" (en la app: "Tren inferior / core") -- mismo
# grupo que leg-raise y kneehold-bar: es trabajo de core/flexores de cadera.
#
# Mismo patrón que 0052 (get_or_create idempotente; no toca filas ya
# existentes con ese slug).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="l-sit", name="L-sit en paralelas", mode="pose", counter_key="lsit", order=26),
    dict(slug="l-sit-hold", name="L-sit en paralelas (hold)", mode="timed", counter_key="lsithold", order=27),
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
        ("tasks", "0067_planitem_course_progress"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
