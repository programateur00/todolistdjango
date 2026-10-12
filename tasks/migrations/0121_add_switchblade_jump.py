# Ejercicio nuevo "Switchblade jumps" (slug "switchblade-jump"), pedido por Alex (2026-10-12): salto en tijera de calistenia
# -- despegas, en el aire abres las piernas estiradas (una hacia delante, otra hacia atrás) y te tocas el pie de delante
# con la mano, y aterrizas con los pies juntos. Referencias: Shorts de YouTube "How to do SWITCHBLADE jump | calisthenics
# workout" (@fit-geek5200) y "How To Do Switchblade Jumps" (@arkadyefron).
#
# PROPIO counter_key "switchblade" -> processSwitchblade en workout.js (web y app), código nuevo sin reutilizar el de otros
# ejercicios: una repetición cuenta solo si hay salto, tijera de piernas estiradas (visible DE PERFIL) y toque mano-pie; si
# falla alguna, no cuenta y se dice por qué (ver el bloque SWITCHBLADE_*). Umbrales PENDIENTES de afinar con vídeo real.
#
# Tren inferior (pliométrico), nivel "advanced" (pide base de salto y movilidad de cadera/isquios, como los tuck jumps),
# MET 8.0 como jump-squat. order 67. En views.COUNTERS, calories.SECONDS_PER_REP, workout.js (web y app), workout-view.js
# y task_workout.html se da de alta aparte. get_or_create idempotente, mismo patrón que 0115-0120.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="switchblade-jump", name="Switchblade jumps", mode="pose", counter_key="switchblade",
         body_area="lower_body", level="advanced", met=8.0, order=67),
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
        ("tasks", "0120_add_hollow_body_hold"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
