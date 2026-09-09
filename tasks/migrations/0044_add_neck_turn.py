# Añade "Giro de cabeza a los lados" al catálogo -- décimo de la familia
# de calentamientos/estiramientos con cámara en "Deporte -> Estiramientos
# y calentamientos" (ver 0031/.../0043 para el resto de la familia y el
# body_area="warmup" ya dejado listo en 0029).
#
# IMPORTANTE: esto NO es lo mismo que "Movilidad lateral de cuello"
# (0034, counter_key necklateral) -- ese ejercicio es una INCLINACIÓN
# (oreja hacia el hombro); este es un GIRO puro sobre el eje vertical
# del cuello (como decir "no" con la cabeza), mirando hacia un lado y
# volviendo al centro, sin acercar la oreja al hombro ni completar
# ninguna circunferencia (a diferencia de círculos de cuello/media
# vuelta de cuello, 0042/0043). El usuario pidió explícitamente que
# fuera un ejercicio nuevo y separado, aunque la geometría de base
# (desplazamiento horizontal de la nariz respecto al punto medio de los
# hombros) sea la misma que necklateral.
#
# Se cuenta por repeticiones (un vaivén completo centro -> lado -> centro
# cuenta como una repetición), así que va con mode="pose" (cámara cuenta
# reps) y counter_key en COUNTERS (tasks/views.py), no en
# POSTURE_COUNTERS. El contador de cámara ("neckturn") vive en
# workout.js (processNeckTurn) y se ha añadido también a COUNTERS en
# tasks/views.py, GROUND_STYLE_COUNTERS y NO_REST_COUNTERS en workout.js,
# a la vez que esta migración (no hay forma de que una migración de
# datos toque JS). circuit.js no necesita ningún cambio: mode="pose" ya
# se enruta solo a runCamera(), igual que el resto de ejercicios
# contados por repeticiones.
#
# Pedido por el usuario con un vídeo de referencia (WhatsApp, grabado
# 2026-09-04, subido 2026-09-08): de pie, de frente a la cámara, con las
# manos en la cadera, mirando al frente -- gira la cabeza para mirar
# hacia un lado y vuelve a mirar al frente. Reutiliza tal cual los
# umbrales ya calibrados de necklateral (misma geometría, mismo punto de
# partida razonable) bajo constantes NECKTURN_* propias e independientes
# -- primera versión de ESTE ejercicio, pendiente de confirmar en una
# prueba real que esos umbrales también valen para un giro (que suele
# desplazar la nariz más que una inclinación) y no solo para inclinar.
#
# Mismo patrón que 0031/.../0043 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="neck-turn-side", name="Giro de cabeza a los lados", mode="pose", counter_key="neckturn", order=1),
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
        ("tasks", "0043_add_neck_half_turn"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
