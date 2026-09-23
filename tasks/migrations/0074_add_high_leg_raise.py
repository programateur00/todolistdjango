# Añade "Elevación de pierna alta" al catálogo -- estiramiento dinámico
# con cámara para la familia de calentamientos/estiramientos de tren
# inferior en "Deporte -> Estiramientos y calentamientos" (ver
# 0031/.../0048 para el resto de la familia y el body_area="warmup" ya
# dejado listo en 0029).
#
# Se cuenta por repeticiones (tumbado boca arriba, de perfil a la
# cámara, subiendo una pierna estirada hacia el pecho o la cabeza --
# ayudándose con las manos si se quiere -- y volviendo a bajarla), así
# que va con mode="pose" (cámara cuenta reps) y counter_key en COUNTERS
# (tasks/views.py) y en el COUNTERS de mobile-app/www/js/workout-view.js
# (para poder abrirlo suelto, no solo dentro de un circuito -- ver el
# comentario junto a ese Set), no en POSTURE_COUNTERS. El contador de
# cámara ("highlegraise") vive en workout.js (processHighLegRaise), en
# la copia web y en la de la app móvil, con umbrales deliberadamente MÁS
# LAXOS que "Elevación de piernas" (legraise): sin exigir la pierna
# estirada (ni para armar ni para contar), ángulo de "arriba" más
# permisivo (120° en vez de 100°) y mucho más margen antes de dar la
# serie por terminada al inclinarse el torso (2000ms en vez de 900ms) --
# ver el bloque de comentarios HIGHLEGRAISE_* en workout.js para el
# detalle completo, validado frame a frame contra la salida real de
# MediaPipe sobre el vídeo de referencia (subido 2026-09-22).
#
# Pedido por Alex con un vídeo de referencia (subido 2026-09-22): quería
# el nombre de forma libre (no "estiramiento muay thai"), que aguantara
# bien en móvil y que relajara umbrales si hacía falta para que contara
# de forma fiable -- de ahí que este ejercicio, a diferencia de
# elevación de piernas, no exija piernas rectas en ningún momento.
#
# Se añade también a la rutina "Calentamiento y estiramiento — tren
# inferior" (seed_warmup_routines.py), junto al resto de movimientos
# dinámicos de pierna/cadera de esa familia -- hay que relanzar
# `python3 manage.py seed_warmup_routines` para que el circuito ya
# existente recoja el ejercicio nuevo (no lo hace esta migración de
# datos: RoutineItem no se toca aquí, igual que el resto de la familia).
#
# Mismo patrón que 0031/.../0048 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="high-leg-raise", name="Elevación de pierna alta", mode="pose", counter_key="highlegraise", order=1),
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
        ("tasks", "0073_remove_neck_circles_half_turn"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
