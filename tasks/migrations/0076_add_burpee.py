# Añade "Burpees" con cámara (2026-09-23).
#
#   - "burpee" (mode="pose", counter_key="burpee"): repeticiones. De perfil a la cámara, de pie para
#     empezar; cada rep encadena agacharse (manos al suelo), tirar las piernas atrás hasta la plancha,
#     opcionalmente una flexión (bajar y subir el pecho), volver a traer las piernas y ponerse de pie.
#     Basado en un vídeo de referencia real de Alex (burpees.mp4, con audio y demo lenta/rápida) -- ver
#     el bloque BURPEE_* en workout.js para el detalle de cada fase y sus umbrales.
#
# El contador vive en workout.js (processBurpee, bloque BURPEE_*), en la copia web y en la de la app
# móvil (mismo parche exacto en las dos, verificado con node --check). body_area="lower_body": aunque
# incluye una flexión, el patrón cíclico (agachar/plancha/levantarse) es el mismo criterio que ya se usó
# para Superman y (en su momento) Mountain climbers -- a falta de una subcategoría "cuerpo entero" en el
# catálogo, y a diferencia de las flexiones sueltas (upper_body). Revisar si Alex prefiere otra.
#
# PRIMERA VERSIÓN: el contador es, con diferencia, el que más fases encadena de todo el catálogo --
# mountain-climber (una sola fase) se acabó retirando (0072) por poco fiable a fps bajo real. Sin probar
# en cámara real todavía -- pedir 📋 en cuanto se pruebe.
#
# Mismo patrón que 0069/0070/0071 (get_or_create idempotente; no toca filas ya existentes con ese slug).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="burpee", name="Burpees", mode="pose", counter_key="burpee", order=34),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for e in NEW_EXERCISES:
        Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode=e["mode"], counter_key=e["counter_key"],
            body_area="lower_body", config={}, is_active=True, order=e["order"],
        ))


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0075_add_elephant_steps"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
