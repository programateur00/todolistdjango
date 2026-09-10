# Añade "Jumping Jacks" al catálogo -- existía como fila suelta en
# algunos entornos (creada a mano en algún momento, nunca vía
# migración) pero no en otros: seed_warmup_routines la daba por
# encontrada en local y por "no encontrada en el catálogo" en
# producción/otro clon, porque nunca hubo una migración de verdad que
# la sembrara -- solo 0050_set_voice_step_fast_exercises la referencia
# de pasada (por si ya existía) para ponerle voice_step=5, sin crearla.
#
# Se cuenta por repeticiones (cámara), así que mode="pose", igual que
# el resto de calentamientos con contador -- ver counter_key
# "jumpingjack" en workout.js/COUNTERS (tasks/views.py), ya presente
# desde antes de esta migración. body_area="warmup" (el mismo grupo
# que el resto de "Estiramientos y calentamientos"). config con
# voice_step=5 puesto directamente aquí (en vez de depender de que
# 0050 la vuelva a tocar, que no lo hará -- las migraciones no se
# re-ejecutan) para que el resultado final sea el mismo en cualquier
# entorno donde se aplique esta migración desde cero.
#
# Mismo patrón que 0031/.../0038/etc. (siembra el catálogo,
# get_or_create idempotente para quien ya la tuviera creada a mano).

from django.db import migrations

NEW_EXERCISES = [
    dict(
        slug="jumping-jack", name="Jumping Jacks", mode="pose",
        counter_key="jumpingjack", order=0, config={"voice_step": 5},
    ),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for e in NEW_EXERCISES:
        Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode=e["mode"], counter_key=e["counter_key"],
            body_area="warmup", config=e["config"], is_active=True, order=e["order"],
        ))


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0051_add_routine_warmup_bookend"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
