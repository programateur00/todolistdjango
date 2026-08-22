# Añade "Flexiones" (push-ups) al catálogo de tren superior, a petición
# del usuario.
#
# Se cuenta por REPETICIONES (mode="pose", como dominadas, fondos o
# sentadillas), no cronometrado — cada bajada y subida completa cuenta
# una flexión. El contador de cámara ("pushup") vive en workout.js
# (processPushup), indexado por counter_key — ver COUNTERS en views.py
# (y su equivalente en la app móvil, workout-view.js), que hay que
# actualizar a la vez que esta migración (no hay forma de que una
# migración de datos toque JS).
#
# El slug "push-up" ya tenía ilustración propia en exercise_icons.py
# (AVAILABLE) y en el equivalente JS de la app (exercise-icons.js) desde
# antes de este ejercicio existir de verdad en el catálogo — así que no
# hace falta tocar ninguno de los dos.
#
# La cámara se coloca A UN LADO (de perfil), igual que en sentadillas: el
# ángulo del codo (hombro-codo-muñeca) que se usa para contar solo se
# mide bien de perfil. A diferencia de los fondos (que evitan a propósito
# ese ángulo porque el movimiento se ve igual de frente), aquí el
# movimiento YA es de perfil por definición — una flexión es horizontal,
# boca abajo — así que si el usuario mantiene los codos hacia atrás
# (pegados al cuerpo, no abiertos hacia los lados) el ángulo se ve
# perfectamente bien desde el lado.
#
# Mismo patrón que 0012/0014/0015 (siembra el catálogo para instalaciones
# nuevas, get_or_create idempotente para quien ya la haya aplicado): este
# ejercicio no existía antes en el catálogo, así que no hace falta ningún
# "pasa de estado viejo a nuevo" como en 0011.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="push-up", name="Flexiones", mode="pose", counter_key="pushup", order=19),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for e in NEW_EXERCISES:
        Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode=e["mode"], counter_key=e["counter_key"],
            body_area="upper_body", config={}, is_active=True, order=e["order"],
        ))


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0016_kneehold_bar_lower_body"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
