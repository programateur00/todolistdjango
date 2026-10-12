# Ejercicio nuevo "Flexiones pseudo planche" (slug "pseudo-planche-push-up"),
# pedido por Alex (2026-10-11): flexión con las manos junto a la cintura (dedos
# hacia atrás) y el cuerpo inclinado hacia delante, hombros por delante de las
# manos. PROPIO counter_key "pseudoplanchepushup" -> processPseudoPlanchePushup
# en workout.js (mismo conteo de codo que processPushup, pero de perfil exige el
# hombro por delante de la muñeca: lo único que la distingue de una flexión
# normal; ver el bloque PSEUDOPLANCHE_PUSHUP_*).
#
# Nivel "advanced" (ajustable en el admin), MET 7.0, order 48. Dado de alta
# también en views.COUNTERS, ai._LOW_REP_STRENGTH_SLUGS (empieza con pocas reps)
# y calories.SECONDS_PER_REP. get_or_create idempotente.

from django.db import migrations

NEW_EXERCISE = dict(
    slug="pseudo-planche-push-up", name="Flexiones pseudo planche",
    mode="pose", counter_key="pseudoplanchepushup", body_area="upper_body",
    level="advanced", met=7.0, order=48,
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
        ("tasks", "0102_add_archer_onearm_clap_push_ups"),
    ]

    operations = [
        migrations.RunPython(add_exercise, remove_exercise),
    ]
