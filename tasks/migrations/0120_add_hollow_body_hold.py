# Ejercicio nuevo "Hollow body (aguante)" (slug "hollow-body-hold"), pedido por Alex (2026-10-12): tumbado boca arriba,
# piernas rectas y juntas y brazos sobre la cabeza; se pega la zona lumbar al suelo y se despegan a la vez hombros+cabeza y
# piernas (forma de plátano), y se aguanta (guias de StrengthLog, The Barbell Physio y MasterClass). Se cuentan SEGUNDOS.
#
# mode="timed" con counter_key propio "hollowbodyhold" -> createHollowBodyChecker en workout.js (web y app), codigo original,
# y por eso va en POSTURE_COUNTERS (views.py / circuit.js / plan-session.js / session-runner.js / workout-view.js), igual que
# plancha o silla en pared. Core / tren inferior, nivel "intermediate", MET 3.8 (como la plancha: isometrico de core,
# Compendio de Actividades Fisicas 2011). order 66. get_or_create idempotente, mismo patron que 0116-0119.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="hollow-body-hold", name="Hollow body (aguante)", mode="timed", counter_key="hollowbodyhold",
         body_area="lower_body", level="intermediate", met=3.8, order=66),
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
        ("tasks", "0119_add_glute_bridge"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
