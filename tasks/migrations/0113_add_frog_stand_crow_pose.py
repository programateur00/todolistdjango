# Añade "Frog Stand" y "Crow Pose" al catálogo, a petición de Alex (2026-10-11).
#
# Son dos equilibrios sobre las manos MUY parecidos (rodillas apoyadas en los
# brazos, pies en el aire): frog stand = rodillas sobre los codos/tríceps con
# los brazos flexionados; crow = rodillas más arriba, brazos más estirados. La
# cámara no los distingue, así que COMPARTEN contador ("frogstand",
# checkFrogStandPosture en workout.js), igual que diamante/anchas con su base.
# Se aguantan, no se cuentan reps: mode="timed". Contador de cámara en
# POSTURE_COUNTERS (views.py, workout.js, session-runner.js, workout-view.js,
# circuit.js, plan-session.js). Umbrales PENDIENTES de afinar con vídeo real.
#
# Mismo patrón que 0092/0106/0111/0112: get_or_create idempotente; si ya
# existía sin nivel, se le pone.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="frog-stand", name="Frog Stand", mode="timed", counter_key="frogstand",
         body_area="upper_body", level="intermediate", order=59),
    dict(slug="crow-pose", name="Crow Pose", mode="timed", counter_key="frogstand",
         body_area="upper_body", level="intermediate", order=60),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for e in NEW_EXERCISES:
        obj, created = Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode=e["mode"], counter_key=e["counter_key"],
            body_area=e["body_area"], level=e["level"], config={}, is_active=True, order=e["order"],
        ))
        if not created and not obj.level:
            obj.level = e["level"]
            obj.save(update_fields=["level"])


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0112_add_heel_raise"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
