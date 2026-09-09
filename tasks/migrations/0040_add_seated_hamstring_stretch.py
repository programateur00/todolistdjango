# Añade "Estiramiento de isquiotibiales sentado" al catálogo — tercero
# de la familia de estiramientos ISOMÉTRICOS con cámara (mode="timed",
# ver 0031/0032 para el primero/segundo de esta subfamilia: cruzado de
# brazo y tríceps por encima de la cabeza). counter_key=
# "seatedhamstringstretch", body_area="warmup" (ver 0029).
#
# A diferencia de los dos anteriores (de pie, de frente), aquí el
# estiramiento se hace SENTADO EN EL SUELO: una pierna estirada del
# todo, la otra doblada, el cuerpo inclinado hacia delante para
# agarrarse el pie/tobillo de la pierna estirada con la mano,
# aguantando. Pedido por el usuario con un vídeo de referencia propio
# (subido 2026-09-07).
#
# Reutiliza el mismo patrón de dos pasos que el resto de
# STRETCH_HOLD_COUNTERS (workout.js): paso 1 standby de pie
# (checkStandbyPosture, sin cambios — el mismo de cruzado de brazo y
# tríceps), paso 2 la postura sentada en sí (checkSeatedHamstringStretch,
# nueva). Como en los dos anteriores, se comprueban las dos piernas
# posibles (izquierda estirada/derecha estirada) sin exigir un lado
# concreto, para poder alternar sin lógica aparte — cada aguante cuenta
# como una serie aparte.
#
# A DIFERENCIA de cruzado de brazo/tríceps (de frente, para ver los dos
# brazos), aquí se pide DE PERFIL: la comprobación mide el ángulo
# cadera-rodilla-tobillo de la pierna estirada (ver angle() en
# workout.js, pensada para verse "de perfil" — de frente, una pierna
# apuntando a la cámara se ve escorzada y el ángulo sale con mucho
# ruido), igual que sentadillas/silla en pared/rodillas altas/talones
# al glúteo.
#
# El contador de cámara vive en workout.js (checkSeatedHamstringStretch)
# y se ha añadido también a CAMERA_POSTURE_COUNTERS, NO_REST_COUNTERS,
# PROFILE_POSTURE_COUNTERS y STRETCH_HOLD_COUNTERS ahí, a
# POSTURE_COUNTERS en tasks/views.py, y al import + POSTURE_COUNTERS +
# el dispatch de runTimerWithPosture en circuit.js, a la vez que esta
# migración (no hay forma de que una migración de datos toque JS).
#
# Umbrales de partida, sin probar en cámara real todavía (mismo caso
# que tuvo cruzado de brazo/tríceps al añadirse) — pendientes de
# ajustar según lo que se reporte probándolos de verdad delante de la
# cámara.
#
# Mismo patrón que 0031/.../0039 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="seated-hamstring-stretch", name="Estiramiento de isquiotibiales sentado", mode="timed", counter_key="seatedhamstringstretch", order=1),
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
        ("tasks", "0039_add_heel_kicks"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
