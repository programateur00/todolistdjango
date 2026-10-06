# Añade "Pistol squat" (sentadilla a una pierna) al catálogo de tren inferior,
# a petición de Alex, que mandó un vídeo de referencia real
# (WIN_20261006_15_54_57_Pro.mp4, 1280x720 ~15fps, ~67s, 2026-10-06): de pie
# DE FRENTE a la cámara, una repetición con la pierna izquierda y luego otra
# con la derecha.
#
# mode="pose" con counter_key="pistolsquat" (cámara cuenta reps, igual criterio
# que "squat"/"splitsquat"). Nivel "advanced": unilateral + equilibrio + fuerza,
# más exigente que la sentadilla a dos piernas (intermedia) -- Exercise.level
# existe desde 0084/0085, así que se fija aquí directamente en vez de tocar
# tasks/ai.py (que ya lo lee del campo).
#
# El contador ("pistolsquat") vive en workout.js (processPistolSquat, junto a
# processSplitSquat). Diseñado sobre el vídeo real, SIN ángulo de rodilla (de
# frente no es fiable): se mide cuánto se ACORTA cada pierna (cadera->tobillo
# respecto a su largo de pie), exigiendo además asimetría entre las dos piernas
# y bajada de cadera para no confundirlo con una sentadilla normal ni con
# levantar un pie. Verificado ejecutando el JS real sobre la pose de TODO el
# vídeo (PoseLandmarker VIDEO, pose_landmarker_full.task vendorizado,
# mediapipe 0.10.32 tasks API) a fps completo y submuestreado a 10 y 6.7 fps:
# exactamente 2 repeticiones (izquierda t=36.5-40.6s, derecha t=55.2-57.3s) y
# cero falsos positivos durante ~30s de pie hablando y gesticulando. La serie
# se cierra a los 8s sin repetir (pedido por Alex), solo si ya hay reps.
#
# También dado de alta en COUNTERS (tasks/views.py) y en el COUNTERS de
# workout-view.js (app móvil, con tip 📐 propio), y en LABELS de
# exercise-icons.js (sin alias: ninguna silueta de Everkinetic enseña una
# sentadilla a una pierna, cae al respaldo genérico de solo texto).
#
# Mismo patrón que 0036/0081/0083 (siembra el catálogo, get_or_create
# idempotente para quien ya la haya aplicado).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="pistol-squat", name="Pistol squat", mode="pose", counter_key="pistolsquat",
         body_area="lower_body", level="advanced", order=24),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for e in NEW_EXERCISES:
        obj, created = Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode=e["mode"], counter_key=e["counter_key"],
            body_area=e["body_area"], level=e["level"], config={}, is_active=True, order=e["order"],
        ))
        if not created and not obj.level:
            obj.level = e["level"]
            obj.save(update_fields=["level"])


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0091_refresh_upper_body_warmup_routine"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
