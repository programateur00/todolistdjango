# Ejercicio nuevo "Rocking push-ups" (slug "rocking-push-up"), pedido por Alex (2026-10-12): desde plancha alta,
# una flexión y después se balancea la cadera hacia atrás, hacia los talones (brazos estirados, como la postura
# del niño), y se vuelve a la plancha. Es el "rocking push-up" de Original Strength / "rocking chair push-up".
#
# PROPIO counter_key "rockingpushup" -> processRockingPushup en workout.js (web y app): una repetición cuenta
# solo con las dos cosas hechas (flexión completa de codo + balanceo de cadera, medido con el ángulo
# hombro-cadera-RODILLA). No vale el contador "pushup": en el balanceo la línea del cuerpo se rompe a propósito.
#
# Tren superior (es una flexión), nivel "intermediate", MET algo menor que "push-up" (6.0, 0096): se mueve
# más despacio. order 61. En views.COUNTERS, workout.js (web y app), workout-view.js y task_workout.html se
# da de alta aparte. get_or_create idempotente, mismo patrón que 0101/0103.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="rocking-push-up", name="Rocking push-ups",
         mode="pose", counter_key="rockingpushup", body_area="upper_body",
         level="intermediate", met=5.0, order=61),
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
        ("tasks", "0114_readingpdf"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
