# Añade "Cossack squat" (sentadilla cosaca / lateral profunda) al catálogo de tren inferior,
# a petición de Alex (2026-10-11): DE FRENTE a la cámara.
#
# Forma (strengthlog, Box Life, Garage Gym Reviews): pies muy separados, se baja sobre UNA pierna (rodilla
# doblada a fondo, pie entero en el suelo) mientras la otra queda estirada hacia el lado con el pie girado sobre
# el talón (puntas hacia arriba), tronco erguido; se vuelve al centro y se baja al otro lado.
#
# mode="pose" con counter_key="cossacksquat": contador propio en workout.js (processCossackSquat, junto a
# processPistolSquat), mismo método que el pistol squat -- solo caderas y tobillos, sin ángulo de rodilla
# (de frente no es fiable): la cadera baja y se desplaza hacia el pie que se dobla, esa pierna se acorta en
# pantalla y la estirada se queda a su largo. Cada lado cuenta 1 repetición. Nivel "intermediate":
# exige movilidad de cadera/aductores, pero menos fuerza unilateral que el pistol (advanced).
# Sentadilla sumo y pistol squat NO pasan sus filtros (ver el bloque COSSACKSQUAT_*).
#
# Mismo patrón que 0092/0106: get_or_create idempotente; si ya existía sin nivel, se le pone.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="cossack-squat", name="Cossack squat", mode="pose", counter_key="cossacksquat",
         body_area="lower_body", level="intermediate", order=57),
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
        ("tasks", "0110_plank_variants_rep_counters"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
