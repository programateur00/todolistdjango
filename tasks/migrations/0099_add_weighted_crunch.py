# Ejercicio nuevo "Weighted crunch" (slug "weighted-crunch"), pedido por Alex
# (2026-10-08): idéntico al crunch pero con los brazos estirados hacia arriba
# (hacia el techo) agarrando una pesa -- el usuario tira hacia arriba con ella
# al subir los hombros.
#
# Mismo contador de cámara que "Crunch" (counter_key="crunch" ->
# processCrunch en workout.js), sin tocar workout.js: el contador solo mide
# cuánto sube el hombro sobre la cadera, y con los brazos arriba la muñeca
# queda POR ENCIMA del hombro, que checkOnBack nunca penaliza (solo bloquea
# muñecas MUY por debajo del hombro = a cuatro patas). Mismo criterio que
# "wide-weighted-pullup" (0085), que comparte contador con "wide-pullup".
#
# Dado de alta también en Exercise.WEIGHTED_SLUGS/WEIGHTED_BASE (models.py),
# _WEIGHTED_CATEGORY_BY_SLUG (ai.py) y SECONDS_PER_REP (calories.py).
# Nivel "intermediate" (crunch sin peso es "beginner"). get_or_create
# idempotente, mismo patrón que 0085.

from django.db import migrations

NEW_EXERCISE = dict(
    slug="weighted-crunch", name="Weighted crunch",
    mode="pose", counter_key="crunch", body_area="lower_body",
    level="intermediate", met=4.2, order=40,
)


def add_exercise(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.get_or_create(slug=NEW_EXERCISE["slug"], defaults=dict(
        name=NEW_EXERCISE["name"], mode=NEW_EXERCISE["mode"],
        counter_key=NEW_EXERCISE["counter_key"], body_area=NEW_EXERCISE["body_area"],
        level=NEW_EXERCISE["level"], met=NEW_EXERCISE["met"],
        config={}, is_active=True, order=NEW_EXERCISE["order"],
    ))


def remove_exercise(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug=NEW_EXERCISE["slug"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0098_remove_high_leg_raise_from_lower_warmup"),
    ]

    operations = [
        migrations.RunPython(add_exercise, remove_exercise),
    ]
