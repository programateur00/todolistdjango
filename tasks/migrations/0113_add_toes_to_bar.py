# Añade "Toes to bar" (llevar los pies a la barra colgado) al catálogo de tren inferior / core,
# a petición de Alex (2026-10-11).
#
# Colgado de la barra con los brazos estirados, las piernas suben (casi rectas) hasta que los pies tocan la
# barra y bajan con control. mode="pose" con counter_key="toestobar": contador propio en workout.js
# (processToesToBar, junto a processScapularPull; mismo agarre/calibrado/cierre al soltar la barra). Se mide la
# altura de los pies frente a las muñecas (la barra) y la cadera, en unidades de torso, así que vale de frente
# o de perfil. Elevaciones de rodilla o de piernas que no llegan a la barra NO cuentan. Nivel "advanced".
# Necesita barra (ver ai._NEEDS_BAR_EQUIPMENT y NEEDS_BAR_SLUGS en plan-view.js).
#
# Mismo patrón que 0111/0112: get_or_create idempotente; si ya existía sin nivel, se le pone.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="toes-to-bar", name="Toes to bar", mode="pose", counter_key="toestobar",
         body_area="lower_body", level="advanced", order=59),
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
