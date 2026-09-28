# Añade "Flexiones en pino" (handstand push-ups) al catálogo de tren
# superior, a petición de Alex, que mandó un vídeo de referencia real
# (handstand_pushups.mp4, ~34s con audio, 2026-09-27) explicando el
# ejercicio: "estos son flexiones haciendo el pino" (transcripción vosk,
# confianza 0.81-1.00 en ese tramo).
#
# Ejercicio DISTINTO de "handstand" (slug "handstand", counter_key
# "handstand", mode="timed", añadido en 0022) -- aquel es un AGUANTE (el
# pino quieto, isométrico); este es de REPETICIONES: partiendo del mismo
# pino (invertida/o, cadera por encima de hombros, brazos aguantando el
# peso cerca del suelo), doblar los codos para bajar la cabeza hacia el
# suelo y volver a subir cuenta como una repetición. mode="pose" con
# counter_key, igual criterio que "pullup"/"pushup"/"scapularpull", NO
# "timed" como el pino aguantado.
#
# El contador de cámara ("handstandpushup") vive en workout.js
# (processHandstandPushup, junto a processPikePushup, que es la plantilla
# más parecida: mismo patrón de ángulo de codo hombro-codo-muñeca con
# umbrales abajo/arriba, gate de brazos estirados para armar y cierre de
# serie al salir de la postura sostenido un rato) -- analizado con el
# vídeo de referencia real (transcripción vosk-model-small-es-0.42,
# mirror GitHub kercre123, + contact sheets fotograma a fotograma +
# simulación con pose real PoseLandmarker VIDEO, modelo vendorizado
# pose_landmarker_full.task, mediapipe 0.10.32 tasks API, sobre TODO el
# vídeo a ~10fps, portando la lógica candidata a Python antes de tocar
# JS). HALLAZGOS clave: (1) el gate de postura reutiliza la misma
# fórmula que checkHandstandPosture (cadera por encima de hombros +
# codos/muñecas por debajo de cadera, con el mismo margen
# HANDSTAND_MARGIN_FACTOR=0.08 y umbral de visibilidad
# HANDSTAND_MIN_VISIBILITY=0.35 ya usados ahí) -- se mantiene invertido
# de forma continua y limpia durante todo el pino real del vídeo
# (t=11.4-27.6s), sin falsos positivos antes de kickup ni falsos
# negativos durante el aguante. (2) Las DOS repeticiones reales del
# vídeo (bajada-subida t~20.4-22.7s y t~22.9-26.7s) NO siempre
# recuperan el bloqueo completo de brazos entre una y otra -- la primera
# subida solo llega a ~143° antes de que empiece la siguiente bajada (la
# segunda sí llega a bloqueo completo, ~150-177°) -- por eso el umbral de
# "arriba" que cuenta la repetición (125°) es más permisivo que el de
# referencia para armar el contador (140°), mismo criterio de histéresis
# que ya usan processPushup/processPikePushup para no perder repeticiones
# rápidas o sin bloqueo total. Verificado contra los datos reales de pose:
# exactamente 2 repeticiones contadas con estos umbrales, cero falsos
# positivos durante el resto del vídeo (de pie, colocándose, bajando del
# pino al final).
#
# A diferencia de las flexiones normales o pike push-ups, aquí NO se
# comprueba el gesto de la mano (checkWaveGesture) para cerrar la serie a
# voluntad -- con las dos manos aguantando el peso del cuerpo entero
# invertido no es seguro soltar una para saludar; el cierre de serie es
# solo por salir de la postura de pino (igual criterio que los ejercicios
# de barra: archerpullup/kneeholdbar/tucklever/deadhang, que tampoco usan
# checkWaveGesture).
#
# También dado de alta en COUNTERS (tasks/views.py) para que
# task_workout lo trate como soportado por cámara, y en el COUNTERS de
# workout-view.js (app móvil) para que abra suelto desde "¿Qué toca hoy?"
# -- con tip 📐 propio (mismo criterio que handstand/kneehold-bar/
# deadhang, que también tienen su propio texto en vez de caer en el
# genérico "de lado"). exercise-icons.js: sin alias, igual que
# "handstand" (ninguna silueta de Everkinetic sirve para un cuerpo
# invertido) -- cae al respaldo genérico de solo texto, con su propia
# entrada en LABELS.
#
# Mismo patrón que 0019/0080/0081 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="handstand-push-up", name="Flexiones en pino", mode="pose", counter_key="handstandpushup", order=38),
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
        ("tasks", "0082_readd_dead_hang"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
