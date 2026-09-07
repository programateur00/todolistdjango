# Añade "Rodillas altas" al catálogo -- séptimo de la familia de
# calentamientos/estiramientos con cámara en "Deporte -> Estiramientos y
# calentamientos" (ver 0031/0032/0033/0034/0035/0037 para el resto de la
# familia y el body_area="warmup" ya dejado listo en 0029).
#
# Se cuenta por repeticiones (de pie, de perfil a la cámara, marchando
# en el sitio -- se alterna levantar una rodilla y volver a apoyar el
# pie, sin pausa entre piernas), así que va con mode="pose" (cámara
# cuenta reps) y counter_key en COUNTERS (tasks/views.py), no en
# POSTURE_COUNTERS. El contador de cámara ("kneeraises") vive en
# workout.js (processKneeRaises) y se ha añadido también a COUNTERS en
# tasks/views.py, GROUND_STYLE_COUNTERS y NO_REST_COUNTERS en
# workout.js, a la vez que esta migración (no hay forma de que una
# migración de datos toque JS). circuit.js no necesita ningún cambio:
# mode="pose" ya se enruta solo a runCamera(), igual que el resto de
# ejercicios contados por repeticiones.
#
# Pedido por el usuario con un vídeo de referencia (WhatsApp,
# 2026-09-07): de perfil a la cámara (no de frente, a diferencia de
# rotación de piernas), con la cadera, la rodilla y el tobillo bien
# visibles; mensajes al mínimo (un solo aviso hablado al empezar, no
# dos); umbral de ángulo relajado por si no se llega muy alto con la
# rodilla; y que el contador aguante el ritmo real (marcha rápida,
# alternando piernas casi sin pausa) sin saltarse ninguna repetición.
#
# Mismo patrón que 0031/.../0037 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="knee-raises", name="Rodillas altas", mode="pose", counter_key="kneeraises", order=1),
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
        ("tasks", "0037_add_leg_rotation"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
