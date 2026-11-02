# Borra por completo "Elevación de pierna alta" (Alex, 2026-10-22): no tenía sentido
# tenerla. Antes solo se había quitado del circuito de calentamiento (0098); ahora se
# elimina el ejercicio entero.
#
# - Exercise "high-leg-raise": se borra del catálogo. Por CASCADE se van también sus
#   RoutineItem (circuitos) y PlanItem (objetivos de planes).
# - WorkoutSession con exercise="high-leg-raise": el historial guarda el slug como texto
#   (no hay FK), así que se borra aparte; si no, saldría en crudo en el historial.
#
# El contador de cámara ("highlegraise") ya no existe en workout.js (web y app móvil),
# ni en views.COUNTERS, ni en calories.py. Idempotente. No reversible (los datos
# borrados no se pueden recuperar).

from django.db import migrations

SLUG = "high-leg-raise"


def remove_exercise(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    WorkoutSession = apps.get_model("tasks", "WorkoutSession")
    WorkoutSession.objects.filter(exercise=SLUG).delete()
    Exercise.objects.filter(slug=SLUG).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0126_add_butterfly_stretch"),
    ]

    operations = [
        migrations.RunPython(remove_exercise, migrations.RunPython.noop),
    ]
