# Añade "Silla en pared" (wall sit) al catálogo de tren inferior, a
# petición del usuario.
#
# Es un ejercicio ISOMÉTRICO (se aguanta, no se cuenta en repeticiones)
# — igual que plancha y plancha lateral, así que sigue exactamente el
# mismo patrón que esos dos: mode="timed" con counter_key puesto, no
# mode="pose". El contador de cámara ("wallsit") vive en workout.js
# (checkWallSitPosture) y se comparte con circuit.js para poder jugarlo
# también dentro de un circuito — ver POSTURE_COUNTERS en views.py y en
# esos dos archivos JS, que también hay que actualizar a la vez que esta
# migración (no hay forma de que una migración de datos toque JS).
#
# La cámara se coloca A UN LADO (de perfil) y algo alejada, para ver el
# cuerpo entero: igual que en sentadillas, el ángulo de la rodilla solo
# se puede medir bien de perfil. La postura correcta se detecta por dos
# ángulos (rodilla cadera-rodilla-tobillo y cadera hombro-cadera-rodilla,
# los dos cerca de 90°) más una comprobación de que la espalda se
# mantiene recta y vertical, apoyada en la pared.
#
# Mismo patrón que 0012 (siembra el catálogo para instalaciones nuevas,
# get_or_create idempotente para quien ya la haya aplicado): este
# ejercicio no existía antes, así que no hace falta ningún "pasa de
# estado viejo a nuevo" como en 0011, solo crearlo si falta.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="wall-sit", name="Silla en pared", mode="timed", counter_key="wallsit", order=17),
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
        ("tasks", "0013_rename_scissor_kick"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
