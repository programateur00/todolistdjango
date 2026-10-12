# Ejercicios nuevos "Flexiones de rodillas" (slug "knee-push-up") y "Flexiones de
# rodillas declinadas" (slug "decline-knee-push-up"), pedidos por Alex
# (2026-10-11): mismo gesto que "Flexiones" pero con el apoyo en las RODILLAS en
# vez de los pies y los tobillos en el aire; en la declinada, las rodillas
# descansan sobre una silla/banco y las manos en el suelo.
#
# A DIFERENCIA de "Flexiones diamante/anchas" (0100, que comparten
# counter_key="pushup"), aquí cada uno lleva su PROPIO counter_key
# ("kneepushup" / "kneedeclinepushup" -> processKneePushup en workout.js):
# processPushup mide la línea del cuerpo hombro-cadera-TOBILLO
# (PUSHUP_LINE_MIN_DEG) y con las piernas dobladas hacia arriba esa línea no se
# cumple nunca; el contador nuevo mide hombro-cadera-RODILLA y exige tobillos
# por encima de la rodilla para armar.
#
# Nivel "beginner" los dos (la de rodillas es la regresión de la flexión normal,
# que ya es beginner; la declinada de rodillas queda a ese nivel de exigencia).
# MET menor que "push-up" (6.0, 0096): se mueve menos peso. order 43/44. En
# views.COUNTERS, workout.js (web y app), workout-view.js y task_workout.html
# se dan de alta aparte. get_or_create idempotente, mismo patrón que 0085/0099/0100.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="knee-push-up", name="Flexiones de rodillas",
         mode="pose", counter_key="kneepushup", body_area="upper_body",
         level="beginner", met=4.5, order=43),
    dict(slug="decline-knee-push-up", name="Flexiones de rodillas declinadas",
         mode="pose", counter_key="kneedeclinepushup", body_area="upper_body",
         level="beginner", met=5.0, order=44),
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
        ("tasks", "0100_add_diamond_wide_pushup"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
