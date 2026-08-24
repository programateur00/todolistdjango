# Quita "Dead Hang" del catálogo y lo sustituye por "Handstand" (el
# pino), a petición del usuario.
#
# Por qué se quita Dead Hang: comprobado en la base de datos real antes
# de escribir esta migración — cero WorkoutSession, cero RoutineItem y
# cero PlanItem lo referencian, así que se puede borrar sin ningún riesgo
# de pérdida de datos (RoutineItem.exercise y PlanItem.exercise SÍ son
# ForeignKey a Exercise con on_delete=CASCADE, así que si hubiera algo
# referenciándolo, borrarlo se lo llevaría por delante — no es el caso).
#
# Por qué se añade Handstand: mismo tipo de ejercicio isométrico que
# plancha/kneehold en barra/silla en pared — mode="timed" con
# counter_key puesto. A diferencia de Dead Hang (que necesitó varios
# intentos fallidos, con suavizado y referencia personal, porque
# "colgarte" y "estar de pie estirando los brazos" se ven casi iguales
# para MediaPipe — ver el historial de comentarios en 0018_add_dead_hang),
# un pino no tiene ese problema de raíz: el cuerpo entero queda
# invertido, con la cadera por encima de los hombros en la imagen, algo
# que ninguna postura normal puede producir. Solo dos condiciones, tal y
# como se pidió: cadera por encima de hombros (cuerpo invertido) y
# codos/muñecas por debajo de la cadera (brazos aguantando el peso cerca
# del suelo). Vale igual con o sin apoyo en la pared — la cámara no ve la
# pared, así que no hace falta distinguir un caso del otro.
#
# El contador de cámara ("handstand") vive en workout.js
# (checkHandstandPosture, sin paso 1 de confirmación — mismo criterio
# que silla en pared) y se comparte con circuit.js/plan-session.js para
# poder jugarlo también dentro de un circuito o un plan — ver
# POSTURE_COUNTERS en views.py y en esos archivos JS (más
# session-runner.js/workout-view.js en la app móvil, y el propio
# workout.js/circuit.js duplicados ahí), que también hay que actualizar
# a la vez que esta migración (no hay forma de que una migración de
# datos toque JS).
#
# body_area="upper_body", igual que Dead Hang y Kneehold Bar — un pino
# se aguanta con hombros/brazos/muñecas, aunque también exige mucho
# abdomen; se deja en tren superior por coherencia con el resto de
# ejercicios de "colgarse/aguantar" ya existentes.

from django.db import migrations

REMOVED_EXERCISES = [
    dict(slug="dead-hang", name="Dead Hang", mode="timed", counter_key="deadhang", order=20),
]

NEW_EXERCISES = [
    dict(slug="handstand", name="Handstand", mode="timed", counter_key="handstand", order=23),
]


def apply_replacement(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in REMOVED_EXERCISES]).delete()
    for e in NEW_EXERCISES:
        Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode=e["mode"], counter_key=e["counter_key"],
            body_area="upper_body", config={}, is_active=True, order=e["order"],
        ))


def revert_replacement(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()
    for e in REMOVED_EXERCISES:
        Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode=e["mode"], counter_key=e["counter_key"],
            body_area="upper_body", config={}, is_active=True, order=e["order"],
        ))


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0021_study_playlist_progress"),
    ]

    operations = [
        migrations.RunPython(apply_replacement, revert_replacement),
    ]
