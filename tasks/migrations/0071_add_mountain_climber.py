# Añade "Mountain climbers" con cámara (2026-09-20).
#
#   - "mountain-climber" (mode="pose", counter_key="mountainclimber"): repeticiones. De perfil a la cámara, en
#     plancha (antebrazos o brazos estirados); cada rodilla llevada al pecho, alternando piernas, cuenta 1 rep.
#     La serie se cierra al romper la plancha (tirarse al suelo, levantarse...).
#
# El contador vive en workout.js (processMountainClimber, bloque MC_*), en la copia web y en la de la app móvil.
# body_area="lower_body" (igual que Superman: es la subcategoría de core/piernas).
#
# Mismo patrón que 0069/0070 (get_or_create idempotente; no toca filas ya existentes con ese slug).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="mountain-climber", name="Mountain climbers", mode="pose", counter_key="mountainclimber", order=31),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for e in NEW_EXERCISES:
        Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode=e["mode"], counter_key=e["counter_key"],
            body_area="lower_body", config={}, is_active=True, order=e["order"],
        ))


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0070_add_pike_push_up"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
