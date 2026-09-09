# Añade "Cadera adelante y atrás" al catálogo -- decimotercero de la
# familia de calentamientos/estiramientos con cámara en "Deporte ->
# Estiramientos y calentamientos" (ver 0031/.../0047 para el resto de la
# familia y el body_area="warmup" ya dejado listo en 0029).
#
# Pedido por el usuario con un vídeo de referencia (WhatsApp, grabado
# 2026-09-04, subido 2026-09-08): de pie, DE PERFIL a la cámara (a
# diferencia de movilidad lateral de cadera, 0041, que pide de frente),
# con los pies quietos en el suelo -- la cadera se lleva hacia delante
# y hacia atrás, volviendo cada vez al centro.
#
# Se cuenta por repeticiones (un vaivén completo, cadera hasta delante
# O hasta atrás y vuelta al centro, cuenta como una repetición -- mismo
# mecanismo de vaivén con histéresis que movilidad lateral de cadera:
# desplazamiento de la cadera respecto a un tobillo fijo, con un umbral
# de entrada y otro más corto de salida, sin exigir alternar delante/
# atrás), así que va con mode="pose" (cámara cuenta reps) y counter_key
# en COUNTERS (tasks/views.py), no en POSTURE_COUNTERS. El contador de
# cámara ("hipforwardback") vive en workout.js (processHipForwardBack)
# y se ha añadido también a COUNTERS en tasks/views.py,
# GROUND_STYLE_COUNTERS y NO_REST_COUNTERS en workout.js, a la vez que
# esta migración (no hay forma de que una migración de datos toque JS).
# circuit.js no necesita ningún cambio: mode="pose" ya se enruta solo a
# runCamera(), igual que el resto de ejercicios contados por
# repeticiones.
#
# Diferencia clave con movilidad lateral de cadera (0041): aquella mide
# el desplazamiento de la cadera EN HORIZONTAL DE FRENTE a la cámara, y
# explícitamente rechaza el movimiento hacia delante/atrás porque, de
# frente, ese movimiento corre principalmente por el eje de profundidad
# de MediaPipe (z), demasiado ruidoso para fiarse (ver el comentario
# junto a HIPLATERAL_MAX_DEPTH_FACTOR en workout.js: "mover la cadera
# hacia delante y hacia atrás se contaba como repetición válida" fue
# justo el fallo que llevó a excluirlo ahí). Puesto DE PERFIL en vez de
# de frente, ese mismo movimiento (delante/atrás) pasa a correr por el
# eje horizontal de la imagen -- el eje bueno, el mismo que usa
# movilidad lateral de cadera -- así que aquí se puede medir limpio sin
# tocar la coordenada z para nada. Por la misma razón que talones al
# glúteo (0039) normaliza por la LONGITUD DE LA PIERNA en vez del ancho
# de cadera al ir de perfil (los dos tobillos casi se solapan en la
# imagen), aquí también: el desplazamiento cadera-tobillo se normaliza
# por la propia longitud cadera-tobillo (ver processHipForwardBack), no
# por una anchura de base que de perfil sería casi cero.
#
# Al no poder ver las dos caderas/tobillos por separado de perfil (se
# solapan), se selecciona un único lado (cadera+tobillo) a vigilar,
# elegido UNA vez al armar según cuál se vea mejor, sin cambiar a media
# serie -- mismo criterio que talones al glúteo v10 (ver ese comentario
# en workout.js para el porqué de fijarlo así). Para poder anunciar
# "cadera adelante"/"cadera atrás" con sentido anatómico real (y no solo
# como izquierda/derecha de pantalla), se fija también, al armar, hacia
# qué lado de la pantalla mira la persona (nariz respecto al punto medio
# de hombros) -- heurística de primera versión, sin contrastar todavía
# en cámara real.
#
# Umbrales de partida, sin probar en cámara real todavía (mismo caso que
# tuvo el resto de la familia al añadirse) -- pendientes de ajustar según
# lo que se reporte probándolos de verdad delante de la cámara.
#
# Mismo patrón que 0031/.../0047 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="hip-forward-back", name="Cadera adelante y atrás", mode="pose", counter_key="hipforwardback", order=1),
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
        ("tasks", "0047_add_standing_quad_stretch"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
