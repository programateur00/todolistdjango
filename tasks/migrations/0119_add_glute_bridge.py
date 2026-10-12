# Ejercicio nuevo "Puente de glúteo" (slug "glute-bridge"), pedido por Alex (2026-10-12): tumbado boca arriba, rodillas
# dobladas y pies planos en el suelo, se sube la cadera empujando con los talones hasta que hombros, cadera y rodillas
# quedan en línea recta, y se baja de vuelta al suelo (técnica habitual de las guías de fitness: Mayo Clinic, NHS, ACE).
#
# PROPIO counter_key "glutebridge" -> processGluteBridge en workout.js (web y app), código original. Una repetición solo
# cuenta si la cámara ve las TRES cosas: partir de la posición inicial real (boca arriba, rodillas dobladas, cadera abajo),
# subir la cadera de verdad con la cadera extendida (hombro-cadera-rodilla casi recto), y volver abajo (ver el bloque
# GLUTEBRIDGE_*). No vale "crunch" (ahí sube el hombro) ni "legraise" (ahí se mueve la pierna).
#
# Tren inferior, nivel "beginner" (peso corporal), MET 3.5 (calistenia ligera-moderada, Compendio de Actividades Físicas
# 2011). order 65. get_or_create idempotente, mismo patrón que 0116-0118.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="glute-bridge", name="Puente de glúteo", mode="pose", counter_key="glutebridge",
         body_area="lower_body", level="beginner", met=3.5, order=65),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for ex in NEW_EXERCISES:
        Exercise.objects.get_or_create(slug=ex["slug"], defaults=dict(
            name=ex["name"], mode=ex["mode"], counter_key=ex["counter_key"],
            body_area=ex["body_area"], level=ex["level"], met=ex["met"],
            config={}, is_active=True, order=ex["order"],
        ))


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0118_add_jump_rope"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
