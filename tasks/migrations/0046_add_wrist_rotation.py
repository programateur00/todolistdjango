# Añade "Rotación de muñecas" al catálogo -- duodécimo de la familia de
# calentamientos/estiramientos con cámara en "Deporte -> Estiramientos y
# calentamientos" (ver 0031/.../0045 para el resto de la familia y el
# body_area="warmup" ya dejado listo en 0029).
#
# Pedido por el usuario con un vídeo de referencia (WhatsApp, grabado
# 2026-09-04, subido 2026-09-08): de pie, de frente a la cámara -- manos
# juntas con los dedos entrelazados (como al rezar), delante del pecho/
# barbilla, girando juntas en círculo. El usuario pidió explícitamente
# tener en cuenta que el movimiento es un GIRO (dar vueltas) y no un
# vaivén de lado a lado.
#
# Se cuenta por repeticiones (una vuelta completa de 360° de las manos
# juntas, en cualquier sentido, cuenta como una repetición -- mismo
# mecanismo que círculos de cuello/brazos/rotación de brazo con el codo
# sujeto: ángulo acumulado del vector punto-medio-de-hombros->punto-
# medio-de-muñecas, wrapAngleDelta por fotograma, una repetición cada
# ±2π; esto ya distingue por construcción "dar vueltas" de "ir de un
# lado a otro", sin lógica aparte -- ver el comentario del bloque
# WRISTROTATION_* en workout.js para el razonamiento completo, incluido
# por qué esta primera versión usa landmarks de imagen en 2D en vez de
# los world landmarks 3D que también expone PoseLandmarker), así que va
# con mode="pose" (cámara cuenta reps) y counter_key en COUNTERS
# (tasks/views.py), no en POSTURE_COUNTERS. El contador de cámara
# ("wristrotation") vive en workout.js (processWristRotation) y se ha
# añadido también a COUNTERS en tasks/views.py, GROUND_STYLE_COUNTERS y
# NO_REST_COUNTERS en workout.js, a la vez que esta migración (no hay
# forma de que una migración de datos toque JS). circuit.js no necesita
# ningún cambio: mode="pose" ya se enruta solo a runCamera(), igual que
# el resto de ejercicios contados por repeticiones.
#
# Primera versión de este ejercicio, umbrales sin probar en cámara real
# todavía -- pendiente de calibrar con un test real, mismo patrón que el
# resto de la familia.
#
# Mismo patrón que 0031/.../0045 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="wrist-rotation-interlaced", name="Rotación de muñecas", mode="pose", counter_key="wristrotation", order=1),
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
        ("tasks", "0045_add_forearm_rotation"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
