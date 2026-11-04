# Borra por completo "Dominadas escapulares" (Alex, 2026-11-04): fuera del catálogo, del
# calentamiento y de cualquier otro sitio.
#
# - Exercise "scapular-pull": se borra del catálogo. Por CASCADE se van también sus
#   RoutineItem (circuitos, p. ej. el calentamiento de tren superior) y PlanItem
#   (objetivos de planes).
# - WorkoutSession con exercise="scapular-pull": el historial guarda el slug como texto
#   (no hay FK), así que se borra aparte; si no, saldría en crudo en el historial.
#
# El contador de cámara ("scapularpull") ya no existe en workout.js (web y app móvil),
# ni en views.COUNTERS, ni en calories.py, ni en seed_warmup_routines. Idempotente.
# No reversible (los datos borrados no se pueden recuperar). Mismo patrón que 0127.

from django.db import migrations

SLUG = "scapular-pull"


def remove_exercise(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    WorkoutSession = apps.get_model("tasks", "WorkoutSession")
    WorkoutSession.objects.filter(exercise=SLUG).delete()
    Exercise.objects.filter(slug=SLUG).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0128_tiempo_en_una_web"),
    ]

    operations = [
        migrations.RunPython(remove_exercise, migrations.RunPython.noop),
    ]
