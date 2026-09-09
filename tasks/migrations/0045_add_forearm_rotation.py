# Añade "Rotación de brazo sujetando el codo" al catálogo -- undécimo de
# la familia de calentamientos/estiramientos con cámara en "Deporte ->
# Estiramientos y calentamientos" (ver 0031/.../0044 para el resto de la
# familia y el body_area="warmup" ya dejado listo en 0029).
#
# Pedido por el usuario con dos vídeos de referencia (WhatsApp, grabados
# 2026-09-04): de pie, de frente a la cámara -- una mano agarra el codo
# del otro brazo (por delante, cerca del cuerpo) y ese otro brazo gira en
# círculos alrededor del codo. Los dos vídeos muestran el mismo ejercicio
# en espejo (uno con cada brazo), así que un solo counter_key sirve para
# los dos lados sin duplicar nada -- pedido explícitamente: "que sirva
# para las dos manos así nos ahorramos hacer 2 ejercicios". "Es muy
# fácil" (palabras del usuario): sin postura de reposo previa ni ángulo
# de codo que exigir, solo el agarre.
#
# Se cuenta por repeticiones (una vuelta completa de 360° del antebrazo
# alrededor del codo, en cualquier sentido, cuenta como una repetición),
# así que va con mode="pose" (cámara cuenta reps) y counter_key en
# COUNTERS (tasks/views.py), no en POSTURE_COUNTERS. El contador de
# cámara ("forearmrotation") vive en workout.js (processForearmRotation)
# y se ha añadido también a COUNTERS en tasks/views.py,
# GROUND_STYLE_COUNTERS y NO_REST_COUNTERS en workout.js, a la vez que
# esta migración (no hay forma de que una migración de datos toque JS).
# circuit.js no necesita ningún cambio: mode="pose" ya se enruta solo a
# runCamera(), igual que el resto de ejercicios contados por
# repeticiones.
#
# Primera versión de este ejercicio, umbrales sin probar en cámara real
# todavía -- pendiente de calibrar con un test real, mismo patrón que el
# resto de la familia.
#
# Mismo patrón que 0031/.../0044 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="forearm-rotation-elbow-hold", name="Rotación de brazo sujetando el codo", mode="pose", counter_key="forearmrotation", order=1),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for e in NEW_EXERCISES:
        Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode=e["mode"], counter_key=e["counter_key"],
            body_area="warmup", config={}, is_active=True, order=e["order"],
        ))


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0044_add_neck_turn"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
