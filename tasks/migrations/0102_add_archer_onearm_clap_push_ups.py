# Ejercicios nuevos "Flexiones arquero" (slug "archer-push-up"), "Flexiones a una
# mano" (slug "one-arm-push-up") y "Flexiones con palmada" (slug
# "clap-push-up"), pedidos por Alex (2026-10-11), cada uno con su PROPIO
# counter_key ("archerpushup" / "onearmpushup" / "clappushup" ->
# processArcherPushup / processOneArmPushup / processClapPushup en workout.js,
# ver el bloque ARCHER_PUSHUP_*/ONEARM_PUSHUP_*/CLAP_PUSHUP_* para el porqué:
# arquero se mide DE FRENTE con los dos codos; a una mano exige la mano libre
# en alto; con palmada exige que las manos despeguen del suelo).
#
# Niveles: arquero y a una mano "advanced"; con palmada "intermediate" (ajustable
# en el admin). MET alto (empuje exigente / pliométrico). order 45-47. Dados de
# alta también en views.COUNTERS, ai._LOW_REP_STRENGTH_SLUGS (empiezan con pocas
# reps, no con 8-15) y calories.SECONDS_PER_REP. get_or_create idempotente.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="archer-push-up", name="Flexiones arquero",
         mode="pose", counter_key="archerpushup", body_area="upper_body",
         level="advanced", met=7.0, order=45),
    dict(slug="one-arm-push-up", name="Flexiones a una mano",
         mode="pose", counter_key="onearmpushup", body_area="upper_body",
         level="advanced", met=8.0, order=46),
    dict(slug="clap-push-up", name="Flexiones con palmada",
         mode="pose", counter_key="clappushup", body_area="upper_body",
         level="intermediate", met=8.0, order=47),
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
        ("tasks", "0101_add_knee_push_ups"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
