# Añade "Elevación de talones" (heel raise / calf raise) al catálogo de tren inferior,
# a petición de Alex (2026-10-11).
#
# De pie, se sube sobre la punta de los pies (los talones se despegan del suelo) y se baja. mode="pose" con
# counter_key="heelraise": contador propio en workout.js (processHeelRaise, junto a processCossackSquat); se mide
# cuánto sube el talón/tobillo respecto a la punta del pie, relativo a una base guardada al armar y normalizado por el
# largo de pierna (ver el bloque HEELRAISE_*). Vale de frente o de perfil. Nivel "beginner": sin material ni
# movilidad especial. Umbrales PENDIENTES de afinar con un vídeo real de cámara.
#
# Mismo patrón que 0092/0106/0111: get_or_create idempotente; si ya existía sin nivel, se le pone.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="heel-raise", name="Elevación de talones", mode="pose", counter_key="heelraise",
         body_area="lower_body", level="beginner", order=58),
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
        ("tasks", "0111_add_cossack_squat"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
