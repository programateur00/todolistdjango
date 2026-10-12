# Ejercicio nuevo "Split jumps" (slug "split-jump"), pedido por Alex (2026-10-12): desde una zancada (una pierna delante, la
# otra detrás) se salta con los dos pies fuera del suelo y se aterriza otra vez en zancada, con la misma pierna delante o
# cambiándola en el aire (técnica según Bodybuilding.com "split jump", FitnessVolt y Redefining Strength).
#
# PROPIO counter_key "splitjump" -> processSplitJump en workout.js (web y app), código original: un salto es un
# valle -> pico -> valle de la cadera en el que los DOS tobillos suben a la vez y que acaba con los pies separados en
# zancada (ver el bloque SPLITJUMP_*). Hay que ponerse DE PERFIL. Umbrales PENDIENTES de afinar con vídeo real de cámara.
#
# Tren inferior (pliométrico), nivel "advanced" (igual que jump-squat 0104 y tuck-jump 0117), MET 8.0 (calistenia vigorosa
# con saltos, Compendio de Actividades Físicas 2011). order 68. En views.COUNTERS, calories.SECONDS_PER_REP, workout.js
# (web y app), workout-view.js y task_workout.html se da de alta aparte. get_or_create idempotente, mismo patrón que 0117.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="split-jump", name="Split jumps", mode="pose", counter_key="splitjump",
         body_area="lower_body", level="advanced", met=8.0, order=68),
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
        ("tasks", "0121_add_switchblade_jump"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
