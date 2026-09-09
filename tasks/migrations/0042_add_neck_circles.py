# Añade "Círculos de cuello" al catálogo -- décimo de la familia de
# calentamientos/estiramientos con cámara en "Deporte -> Estiramientos y
# calentamientos" (ver 0031/.../0041 para el resto de la familia y el
# body_area="warmup" ya dejado listo en 0029).
#
# Se cuenta por repeticiones (de pie o sentada/o, de frente a la cámara,
# la cabeza da una vuelta completa alrededor del cuello: de frente,
# hacia un lado, barbilla al pecho, hacia el otro lado, y hacia
# atrás/arriba de vuelta al frente), así que va con mode="pose" (cámara
# cuenta reps) y counter_key en COUNTERS (tasks/views.py), no en
# POSTURE_COUNTERS. El contador de cámara ("neckcircles") vive en
# workout.js (processNeckCircles) y se ha añadido también a COUNTERS en
# tasks/views.py, GROUND_STYLE_COUNTERS y NO_REST_COUNTERS en
# workout.js, a la vez que esta migración (no hay forma de que una
# migración de datos toque JS). circuit.js no necesita ningún cambio:
# mode="pose" ya se enruta solo a runCamera(), igual que el resto de
# ejercicios contados por repeticiones.
#
# Pedido por el usuario con dos vídeos de referencia (WhatsApp,
# 2026-09-04): uno da la vuelta completa (este ejercicio), el otro para
# a la mitad sin llegar a inclinar la cabeza hacia atrás (ver la
# siguiente migración, 0043, "Media vuelta de cuello"). A diferencia de
# círculos de brazos (que exige completar antes un sentido para poder
# cambiar al otro), aquí CUALQUIER sentido (horario o antihorario)
# cuenta siempre, sin bloqueo -- pedido explícitamente por el usuario
# ("que también cuenten si los hago en sentido contrario").
#
# Mismo patrón que 0031/.../0041 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="neck-circles", name="Círculos de cuello", mode="pose", counter_key="neckcircles", order=1),
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
        ("tasks", "0041_add_hip_lateral_mobility"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
