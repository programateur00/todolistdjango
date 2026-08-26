# Añade "Curl con mancuernas" al catálogo de tren superior, a petición
# del usuario (Alex): quiere contar curls con mancuernas por cámara,
# igual que ya se cuentan flexiones/fondos por el ángulo del codo.
#
# mode="pose", counter_key="dumbbellcurl" — contador propio
# (processDumbbellCurl, workout.js), también dado de alta en COUNTERS
# (tasks/views.py) para que task_workout lo trate como soportado por
# cámara. Se mide DE PERFIL, igual que flexiones/fondos/sentadillas —
# una primera versión de frente (para ver los dos brazos/mancuernas a la
# vez, como dominadas) no contaba ninguna repetición en cámara real: el
# curl dobla el antebrazo en el plano sagital del cuerpo, que de frente
# queda casi de canto respecto a la cámara y apenas se ve en las
# coordenadas 2D de MediaPipe. Ver el bloque CURL_* al principio de
# workout.js para el detalle completo, incluida la limitación conocida
# (MediaPipe Pose no puede "ver" si hay algo agarrado en la mano; se
# aproxima por la forma del movimiento: codo pegado al costado y muñeca
# por debajo de la cara, para no confundir un curl real con levantar las
# manos sin querer o mirar el móvil).
#
# body_area="upper_body" (tren superior). Nivel principiante — mismo
# criterio que el resto de ejercicios básicos de tren superior
# (push-up), no hace falta fuerza de agarre ni equilibrio invertido.
#
# El slug no tiene ilustración propia (ver exercise_icons.py, actualizado
# a la vez): no hay ninguna silueta de Everkinetic con mancuernas en el
# set disponible, así que cae al hueco discreto de solo texto — igual
# que handstand, que tampoco reutiliza ninguna otra.
#
# Mismo patrón que 0012/.../0023 (siembra el catálogo para instalaciones
# nuevas, get_or_create idempotente para quien ya la haya aplicado): este
# ejercicio no existía antes en el catálogo, así que no hace falta
# ningún "pasa de estado viejo a nuevo".

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="dumbbell-curl", name="Curl con mancuernas", mode="pose", counter_key="dumbbellcurl", order=25),
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
        ("tasks", "0023_add_incline_push_up"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
