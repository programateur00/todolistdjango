# Añade "Sentadillas con peso" al catálogo de tren inferior, a petición
# del usuario: es EL MISMO ejercicio que "Sentadillas" (mismo movimiento,
# mismo contador de cámara), solo que con lastre añadido y progresión de
# peso — mismo patrón que "Dominadas con peso"/"Fondos con peso" (ver
# 0002_seed_exercise_catalog: weighted-pullup reutiliza counter_key
# "pullup", weighted-dips reutiliza "dip"), así que aquí
# counter_key="squat", el mismo contador que ya usa "Sentadillas" a
# secas — MediaPipe no necesita saber que hay peso de más, solo cuenta
# el movimiento.
#
# body_area="lower_body" (tren inferior — igual que "Sentadillas").
# Nivel intermedio (ver ai._EXERCISE_DIFFICULTY en tasks/ai.py, que hay
# que actualizar a la vez que esta migración — no hay forma de que una
# migración de datos toque ai.py): a diferencia de dominadas/fondos con
# peso (que se etiquetan avanzado, porque ya cuesta hacer la versión sin
# peso a pulso), sentadillas con peso es razonable para alguien que ya
# domina la sentadilla de peso corporal sin llegar todavía a nivel
# avanzado.
#
# Mismo patrón que 0012/0014/0015/0017/0018/0019 (siembra el catálogo
# para instalaciones nuevas, get_or_create idempotente) — este ejercicio
# no existía antes, así que no hace falta migrar nada de estado viejo,
# solo crearlo si falta.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="weighted-squat", name="Sentadillas con peso", mode="pose", counter_key="squat", order=22),
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
        ("tasks", "0019_add_archer_pullup"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
