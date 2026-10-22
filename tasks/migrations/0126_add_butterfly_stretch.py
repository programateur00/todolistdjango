# Ejercicio nuevo "Mariposa" (slug "butterfly-stretch"), pedido por Alex (2026-10-19): estiramiento de aductores/ingle sentado en
# el suelo con las plantas de los pies juntas y las rodillas abiertas hacia los lados (butterfly stretch / baddha konasana), espalda
# recta, aguantando 15-30 s (técnica según ACE Fitness, Sportskeeda y Liforme).
#
# mode="timed", counter_key="butterflystretch" (aguante, como Pasos de elefante (aguante) 0077 y el resto de estiramientos con
# cronómetro). body_area="warmup" (mismo grupo que los demás estiramientos), sin nivel (los de calentamiento/estiramiento quedan
# fuera del sistema de niveles, ver 0085). MET 2.3, el mismo que el resto de estiramientos (0096). order 36.
#
# SIMÉTRICO (las dos piernas a la vez) y DE FRENTE a la cámara: una sola pantalla, sin "lado 1 / lado 2" ni paso 1 de standby. El
# detector vive en workout.js (checkButterflyStretch / createButterflyStretchChecker, web y app); también se da de alta en
# views.POSTURE_COUNTERS, circuit.js, session-runner.js y workout-view.js. NO se añade a ninguna rutina de calentamiento
# (seed_warmup_routines.py): se elige a mano o desde un plan/tarea de Estiramientos.
#
# Mismo patrón que 0077 (get_or_create idempotente para quien ya lo tenga). Depende de la 0125 (Russian twists) para que el
# grafo de migraciones siga en una sola línea.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="butterfly-stretch", name="Mariposa", mode="timed", counter_key="butterflystretch",
         body_area="warmup", met=2.3, order=36),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for ex in NEW_EXERCISES:
        Exercise.objects.get_or_create(slug=ex["slug"], defaults=dict(
            name=ex["name"], mode=ex["mode"], counter_key=ex["counter_key"],
            body_area=ex["body_area"], met=ex["met"],
            config={}, is_active=True, order=ex["order"],
        ))


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0125_add_russian_twist"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
