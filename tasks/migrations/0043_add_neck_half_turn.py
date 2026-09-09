# Añade "Media vuelta de cuello" al catálogo -- undécimo de la familia de
# calentamientos/estiramientos con cámara en "Deporte -> Estiramientos y
# calentamientos" (ver 0031/.../0042 para el resto de la familia y el
# body_area="warmup" ya dejado listo en 0029).
#
# Se cuenta por repeticiones (de pie o sentada/o, de frente a la cámara,
# la cabeza va de un lado al otro pasando por el centro con la barbilla
# hacia el pecho, SIN llegar a completar el círculo entero -- sin
# inclinar la cabeza hacia atrás), así que va con mode="pose" (cámara
# cuenta reps) y counter_key en COUNTERS (tasks/views.py), no en
# POSTURE_COUNTERS. El contador de cámara ("neckhalfturn") vive en
# workout.js (processNeckHalfTurn) y se ha añadido también a COUNTERS en
# tasks/views.py, GROUND_STYLE_COUNTERS y NO_REST_COUNTERS en
# workout.js, a la vez que esta migración (no hay forma de que una
# migración de datos toque JS). circuit.js no necesita ningún cambio:
# mode="pose" ya se enruta solo a runCamera(), igual que el resto de
# ejercicios contados por repeticiones.
#
# Pedido por el usuario con un segundo vídeo de referencia (WhatsApp,
# 2026-09-04) para diferenciarlo del círculo completo de la migración
# anterior (0042, "Círculos de cuello"): "que pare a la mitad". Se
# implementa con el mismo ángulo acumulado que círculos de cuello, pero
# contando una repetición cada MEDIO círculo (π) en vez de uno entero
# (2π) -- así que ir de un lado a otro Y VOLVER (el otro medio círculo,
# en sentido contrario) cuenta como DOS repeticiones, tal y como se
# pidió ("que también cuenten si los hago en sentido contrario").
# Tampoco hay bloqueo de sentido.
#
# Mismo patrón que 0031/.../0042 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="neck-half-turn", name="Media vuelta de cuello", mode="pose", counter_key="neckhalfturn", order=1),
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
        ("tasks", "0042_add_neck_circles"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
