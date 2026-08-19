# Pone al día el catálogo de ejercicios para instalaciones que ya habían
# corrido 0002_seed_exercise_catalog con el estado antiguo (PythonAnywhere
# en producción, por ejemplo) — 0002 ya no vuelve a ejecutarse una vez
# aplicada, así que su edición sola no le llega a una base de datos real.
#
# Tres cambios, decisión del usuario:
#   1. "Superman" y "Circuito de abdominales" se borran del catálogo del
#      todo (no se desactivan). ab-circuit era un placeholder de sesión
#      combinada, deprecado desde routine_save (ver su docstring); ya
#      estaba excluido del constructor de circuitos. OJO: Exercise tiene
#      FK CASCADE desde PlanItem — si algún plan (pasado o activo)
#      apuntaba a alguno de los dos, ese objetivo del plan desaparece
#      con él. RoutineItem también cae en cascada.
#   2. Crunch y elevación de piernas pasan de "timed" (solo cronómetro,
#      dentro de un circuito) a "pose" (cámara, como sentadillas o
#      abdominales) — ya tienen contador propio en workout.js.
#   3. Plancha y plancha lateral se quedan "timed" (se aguantan, no se
#      cuentan en repeticiones) pero con counter_key puesto: el
#      reproductor de circuitos las juega con la cámara encendida para
#      comprobar la postura y pausar la cuenta atrás si se rompe.

from django.db import migrations

DELETE_SLUGS = ["ab-circuit", "superman"]

# (slug, mode nuevo, counter_key nuevo)
UPDATE_MODE = [
    ("crunch", "pose", "crunch"),
    ("leg-raise", "pose", "legraise"),
]
UPDATE_COUNTER_ONLY = [
    ("plank", "plank"),
    ("side-plank", "sideplank"),
]


def apply_updates(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=DELETE_SLUGS).delete()
    for slug, mode, counter_key in UPDATE_MODE:
        Exercise.objects.filter(slug=slug).update(mode=mode, counter_key=counter_key)
    for slug, counter_key in UPDATE_COUNTER_ONLY:
        Exercise.objects.filter(slug=slug).update(counter_key=counter_key)


def revert_updates(apps, schema_editor):
    # Best-effort: vuelve a dejar crunch/leg-raise/plank/side-plank como
    # estaban y recrea Superman y Circuito de abdominales si hiciera
    # falta rehacer la migración hacia atrás. No recupera RoutineItem ni
    # PlanItem que se hubieran borrado en cascada al aplicar esta
    # migración hacia delante — eso ya se ha ido de verdad.
    Exercise = apps.get_model("tasks", "Exercise")
    for slug, _mode, _counter_key in UPDATE_MODE:
        Exercise.objects.filter(slug=slug).update(mode="timed", counter_key="")
    for slug, _counter_key in UPDATE_COUNTER_ONLY:
        Exercise.objects.filter(slug=slug).update(counter_key="")
    Exercise.objects.get_or_create(slug="superman", defaults=dict(
        name="Superman", mode="timed", counter_key="",
        body_area="lower_body", config={}, is_active=True, order=13,
    ))
    Exercise.objects.get_or_create(slug="ab-circuit", defaults=dict(
        name="Circuito de abdominales", mode="timed", counter_key="",
        body_area="lower_body", config={}, is_active=True, order=14,
    ))


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0010_courseplaylist_level_range"),
    ]

    operations = [
        migrations.RunPython(apply_updates, revert_updates),
    ]
