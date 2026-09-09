# Añade "Cuádriceps de pie" al catálogo — cuarto de la familia de
# estiramientos ISOMÉTRICOS con cámara (mode="timed", ver 0031/0032/0040
# para el primero/segundo/tercero de esta subfamilia: cruzado de brazo,
# tríceps por encima de la cabeza e isquiotibiales sentado).
# counter_key="standingquadstretch", body_area="warmup" (ver 0029).
#
# De pie, DE FRENTE a la cámara (a diferencia del isquiotibiales sentado,
# que pide perfil): una pierna se dobla hacia atrás llevando el talón
# hacia el glúteo, agarrada por detrás de la espalda con la mano del
# mismo lado o del contrario (no se exige cuál), aguantando el equilibrio
# con la pierna contraria. Pedido por el usuario con un vídeo de
# referencia propio (subido 2026-09-08).
#
# A diferencia del resto de la familia, aquí NO se mide ningún ángulo de
# la pierna que se dobla ni del brazo que agarra: de frente, tanto el
# tramo rodilla-tobillo de esa pierna como el antebrazo que la sujeta por
# detrás de la espalda quedan ocultos por el propio cuerpo, así que
# MediaPipe no les puede dar una posición fiable. La comprobación usa la
# propia caída de confianza (landmark.visibility) como señal: rodilla
# todavía visible + tobillo "desaparecido" + alguna muñeca "desaparecida"
# = en el estiramiento (ver checkStandingQuadStretch en workout.js).
#
# Reutiliza el mismo patrón de dos pasos que el resto de
# STRETCH_HOLD_COUNTERS (workout.js): paso 1 standby de pie
# (checkStandbyPosture, sin cambios), paso 2 la postura del estiramiento
# en sí (checkStandingQuadStretch, nueva). Como en el resto, se
# comprueban las dos piernas posibles sin exigir un lado concreto, para
# poder alternar sin lógica aparte — cada aguante cuenta como una serie
# aparte.
#
# El contador de cámara vive en workout.js (checkStandingQuadStretch) y
# se ha añadido también a CAMERA_POSTURE_COUNTERS, NO_REST_COUNTERS y
# STRETCH_HOLD_COUNTERS ahí (NO a PROFILE_POSTURE_COUNTERS: este va de
# frente), a POSTURE_COUNTERS en tasks/views.py, y al import +
# POSTURE_COUNTERS + el dispatch de runTimerWithPosture en circuit.js, a
# la vez que esta migración (no hay forma de que una migración de datos
# toque JS).
#
# Umbrales de partida, sin probar en cámara real todavía (mismo caso que
# tuvo el resto de la familia al añadirse) — pendientes de ajustar según
# lo que se reporte probándolos de verdad delante de la cámara.
#
# Mismo patrón que 0031/.../0046 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="standing-quad-stretch", name="Cuádriceps de pie", mode="timed", counter_key="standingquadstretch", order=1),
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
        ("tasks", "0046_add_wrist_rotation"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
