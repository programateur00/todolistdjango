# Ejercicio nuevo "Russian twists" (slug "russian-twist"), pedido por Alex (2026-10-19): sentado en el suelo con el torso
# inclinado hacia atrás (~45°), rodillas dobladas (pies en el suelo o un poco levantados) y las manos juntas delante del pecho;
# se GIRA el tronco hacia un lado y luego hacia el otro sin mover la pelvis (guias de Physitrack y The Gym Group). Cada giro a
# un lado cuenta 1 repeticion.
#
# PROPIO counter_key "russiantwist" -> processRussianTwist en workout.js (web y app). DE PERFIL: en la posicion inicial se ve un
# solo hombro; al girar a cualquier lado se ven los DOS hombros separados, y esa es la senal de repeticion (ver el bloque
# RUSSIANTWIST_*). Solo se arma sentado de perfil, inclinado hacia atras y con las rodillas dobladas: ver los dos hombros fuera
# de esa posicion no cuenta nada. Umbrales PENDIENTES de afinar con video real.
#
# Core / tren inferior (igual que crunch o abdominales), nivel "intermediate" (equilibrio sentado en V con el torso inclinado),
# MET 3.8 (core calistenico, como el hollow body). order 69. En views.COUNTERS, calories.SECONDS_PER_REP, workout.js (web y
# app), workout-view.js y task_workout.html se da de alta aparte. get_or_create idempotente, mismo patron que 0115-0122.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="russian-twist", name="Russian twists", mode="pose", counter_key="russiantwist",
         body_area="lower_body", level="intermediate", met=3.8, order=69),
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
        ("tasks", "0124_plan_closure_seen"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
