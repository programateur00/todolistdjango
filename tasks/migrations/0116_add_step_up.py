# Ejercicio nuevo "Step ups" (slug "step-up"), pedido por Alex (2026-10-12): de pie delante de un escalón, banco o
# caja estable, se apoya un pie encima, se empuja hasta quedar de pie sobre la superficie (el otro pie sube o se
# queda en el aire) y se baja al suelo; alternando pierna o siempre la misma (MasterClass, Fitbod).
#
# PROPIO counter_key "stepup" -> processStepUp en workout.js (web y app). Una repetición solo cuenta si la cámara ve
# las TRES cosas: un pie en alto con el otro abajo, la cadera subiendo con el cuerpo hasta quedar de pie encima, y la
# vuelta de cadera y tobillos al nivel del suelo (ver el bloque STEPUP_*). No vale el contador "squat" (la cadera
# SUBE en vez de bajar), ni "heelraise" ni "kneeraises" (ahí no sube la cadera con un pie apoyado en alto).
#
# Tren inferior, nivel "beginner" (peso corporal, altura de escalón a elegir), MET 4.0. order 62.
# get_or_create idempotente, mismo patrón que 0112/0115.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="step-up", name="Step ups", mode="pose", counter_key="stepup",
         body_area="lower_body", level="beginner", met=4.0, order=62),
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
        ("tasks", "0115_add_rocking_push_ups"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
