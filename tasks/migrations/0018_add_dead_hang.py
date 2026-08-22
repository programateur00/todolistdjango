# Añade "Dead Hang" (colgarse de la barra con los brazos estirados y
# aguantar) al catálogo de tren superior, a petición del usuario — mismo
# tipo de ejercicio isométrico que Kneehold Bar (ver 0015), pero sin
# subir las rodillas: aquí lo único que se trabaja es el agarre, el
# antebrazo y los hombros, colgado sin más.
#
# Es un ejercicio ISOMÉTRICO (se aguanta, no se cuenta en repeticiones) —
# mismo patrón que plancha/plancha lateral/silla en pared/kneehold en
# barra: mode="timed" con counter_key puesto, no mode="pose". El nombre
# se deja en inglés a propósito, igual que "Kneehold Bar" y "Scissor
# Kicks" (ver 0013_rename_scissor_kick): así es como lo pidió quien lo
# encargó.
#
# El contador de cámara ("deadhang") vive en workout.js
# (checkDeadHangPosture, más su paso 1 checkDeadHangHanging) y se
# comparte con circuit.js para poder jugarlo también dentro de un
# circuito — ver POSTURE_COUNTERS en views.py y en esos dos archivos JS
# (más session-runner.js/workout-view.js en la app móvil, y el propio
# workout.js/circuit.js duplicados ahí — ver notas en esos ficheros), que
# también hay que actualizar a la vez que esta migración (no hay forma de
# que una migración de datos toque JS).
#
# body_area="upper_body" desde el principio (a diferencia de Kneehold
# Bar, que hubo que corregir en 0016 después de crearlo mal): aquí no hay
# ambigüedad de "qué se trabaja al subir las rodillas" porque no hay
# rodillas que subir — es un colgado sin más, así que tren superior desde
# el primer momento.
#
# Un dead hang de verdad (agarre, brazos estirados, piernas colgando
# rectas) es indistinguible para MediaPipe de estar de pie estirando los
# brazos hacia la barra sin haber saltado todavía — la relación
# hombro-muñeca es la misma con o sin pies en el suelo. Por eso se pide
# doblar las rodillas hacia atrás (como un curl de isquios): de pie, con
# las dos piernas así dobladas, no hay forma de mantener el equilibrio,
# así que esa postura es una prueba bastante sólida de que de verdad
# estás en el aire. Se pide mantenerlo todo el aguante, no solo como
# gesto inicial.
#
# La comprobación de "rodillas dobladas hacia atrás" NO se basa en que el
# tobillo deje de verse (primer intento, descartado tras feedback real:
# MediaPipe sigue estimando su posición con bastante confianza aunque
# esté oculto detrás del cuerpo, así que nunca llegaba a contar por mucho
# que se doblara la rodilla), sino en que el largo proyectado de la
# espinilla (rodilla-tobillo) se acorta mucho al doblar la rodilla hacia
# atrás — un giro sobre todo en profundidad respecto a una cámara de
# frente — normalizado por el ancho de hombros (no por el muslo: un
# intento anterior con el muslo como referencia no discriminaba bien,
# ver el historial de comentarios en workout.js). Ese valor, encima, se
# suaviza con la mediana de los últimos fotogramas antes de compararlo
# con el umbral, para que un fallo puntual de seguimiento de MediaPipe
# (un pico de ruido aislado) no impida que una postura mantenida de
# verdad llegue a confirmarse. Ver el comentario junto a
# checkDeadHangPosture en workout.js para el razonamiento completo.
#
# Mismo patrón que 0014/0015/0017 (siembra el catálogo para instalaciones
# nuevas, get_or_create idempotente para quien ya la haya aplicado): este
# ejercicio no existía antes, así que no hace falta ningún "pasa de
# estado viejo a nuevo" como en 0011.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="dead-hang", name="Dead Hang", mode="timed", counter_key="deadhang", order=20),
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
        ("tasks", "0017_add_push_up"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
