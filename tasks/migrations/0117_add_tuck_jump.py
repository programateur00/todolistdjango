# Ejercicio nuevo "Tuck jumps" (slug "tuck-jump"), pedido por Alex (2026-10-12): de pie, salto vertical subiendo las dos
# rodillas a la vez hacia el pecho (muslos al menos paralelos al suelo), tronco erguido y aterrizaje amortiguado.
# Técnica según NASM (tuck jump), CoachWeb y el test de tuck jump de World Rugby (Myer et al.).
#
# PROPIO counter_key "tuckjump" -> processTuckJump en workout.js (web y app): una repetición cuenta solo si el salto
# sube lo bastante, las DOS rodillas llegan arriba y el tronco no se inclina; si falla alguna, no cuenta y se dice por
# qué (ver el bloque TUCKJUMP_*). Un aterrizaje rígido solo avisa. Vale de frente y de perfil. Umbrales PENDIENTES de
# afinar con vídeo real de cámara.
#
# Tren inferior (pliométrico), nivel "advanced" (igual que las sentadillas con salto, 0104; NASM pide una base de fuerza
# previa), MET 8.0 como jump-squat. order 63. En views.COUNTERS, calories.SECONDS_PER_REP, workout.js (web y app),
# workout-view.js y task_workout.html se da de alta aparte. get_or_create idempotente, mismo patrón que 0115/0116.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="tuck-jump", name="Tuck jumps", mode="pose", counter_key="tuckjump",
         body_area="lower_body", level="advanced", met=8.0, order=63),
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
        ("tasks", "0116_add_step_up"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
