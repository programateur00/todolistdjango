# Ejercicio nuevo "Comba" (slug "jump-rope"), pedido por Alex (2026-10-12): saltar a la cuerda, con cuerda o sin ella.
# Técnica según guías de salto básico (p. ej. Elevate Rope "jump rope basics"): saltitos de 2-4 cm con las puntas de los pies,
# tronco erguido, codos pegados al cuerpo, muñecas girando la cuerda a la altura de la cadera.
#
# PROPIO counter_key "jumprope" -> processJumpRope en workout.js (web y app). Un salto = una repetición. Se cuenta el REBOTE
# vertical del cuerpo (hombros + caderas + tobillos, normalizado con el tronco): picos con ritmo y periodicidad, no un salto
# grande como en tuck jumps / sentadillas con salto. Descarta brazos arriba (jumping jacks), rodillas subidas (correr en el
# sitio) y saltos grandes. Vale de frente y de perfil. Umbrales PENDIENTES de afinar con vídeo real de cámara (probados solo
# con una simulación sintética de landmarks).
#
# Tren inferior (cardio con impacto), nivel "beginner" (el salto básico es de principiante), MET 11.8 (Compendio de
# Actividades Físicas 2011, 15551: comba, ritmo moderado 100-120 saltos/min, salto básico a dos pies). order 64.
# En views.COUNTERS, calories.SECONDS_PER_REP, workout.js (web y app), workout-view.js y task_workout.html se da de alta
# aparte. get_or_create idempotente, mismo patrón que 0115/0116/0117.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="jump-rope", name="Comba (saltar a la cuerda)", mode="pose", counter_key="jumprope",
         body_area="lower_body", level="beginner", met=11.8, order=64),
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
        ("tasks", "0117_add_tuck_jump"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
