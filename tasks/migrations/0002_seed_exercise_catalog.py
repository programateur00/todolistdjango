# Siembra el catálogo de ejercicios y la rutina por defecto.
#
# Reconstruida a partir de seis migraciones de datos antiguas
# (0008, 0009, 0011, 0018, 0026, 0031 del historial previo al reseteo
# de migraciones) en una sola, reflejando el estado FINAL — con
# "Plancha lateral" en vez de "Mountain climbers" en el circuito, que
# fue sustituido a mitad de proyecto por no tener ilustración en
# Everkinetic y aportar menos al abdomen.
#
# config={} en todos: no hay ajustes de MediaPipe que perder aquí — el
# conteo por cámara vive en el JS, indexado por counter_key, no en
# este campo.

from django.db import migrations

UPPER_BODY = [
    dict(slug="pullup", name="Dominadas", mode="pose", counter_key="pullup", order=0),
    dict(slug="wide-pullup", name="Dominadas anchas", mode="pose", counter_key="pullup", order=1),
    dict(slug="chinup", name="Chin ups", mode="pose", counter_key="pullup", order=2),
    dict(slug="weighted-pullup", name="Dominadas con peso", mode="pose", counter_key="pullup", order=3),
    dict(slug="jumping-pullup", name="Dominadas con salto", mode="pose", counter_key="pullup", order=4),
    dict(slug="dips", name="Fondos", mode="pose", counter_key="dip", order=15),
    dict(slug="weighted-dips", name="Fondos con peso", mode="pose", counter_key="dip", order=16),
]

LOWER_BODY = [
    dict(slug="situp", name="Abdominales", mode="pose", counter_key="situp", order=5),
    dict(slug="squat", name="Sentadillas", mode="pose", counter_key="squat", order=6),
    dict(slug="plank", name="Plancha", mode="timed", counter_key="", order=8),
    dict(slug="crunch", name="Crunch", mode="timed", counter_key="", order=9),
    dict(slug="leg-raise", name="Elevación de piernas", mode="timed", counter_key="", order=10),
    dict(slug="bicycle-crunch", name="Bicicleta", mode="timed", counter_key="", order=11),
    dict(slug="side-plank", name="Plancha lateral", mode="timed", counter_key="", order=12),
    dict(slug="superman", name="Superman", mode="timed", counter_key="", order=13),
    dict(slug="ab-circuit", name="Circuito de abdominales", mode="timed", counter_key="", order=14),
]

RUNNING = [
    dict(slug="running", name="Correr", mode="distance", counter_key="", order=7),
]

DEFAULT_ROUTINE_NAME = "Abdominales completo"
DEFAULT_ROUTINE_ORDER = ["plank", "crunch", "leg-raise", "bicycle-crunch", "side-plank", "superman"]


def seed(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Routine = apps.get_model("tasks", "Routine")
    RoutineItem = apps.get_model("tasks", "RoutineItem")
    User = apps.get_model("auth", "User")

    for e in UPPER_BODY:
        Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode=e["mode"], counter_key=e["counter_key"],
            body_area="upper_body", config={}, is_active=True, order=e["order"],
        ))
    for e in LOWER_BODY:
        Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode=e["mode"], counter_key=e["counter_key"],
            body_area="lower_body", config={}, is_active=True, order=e["order"],
        ))
    for e in RUNNING:
        Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode=e["mode"], counter_key=e["counter_key"],
            body_area="running", config={}, is_active=True, order=e["order"],
        ))

    # Mismo usuario "default" que usa get_current_user() en todo el resto
    # de la app — la app entera va sin login real, protegida por
    # contraseña única (ver tasks/utils.py).
    user, _ = User.objects.get_or_create(username="default", defaults={"is_active": True})

    routine, created = Routine.objects.get_or_create(
        name=DEFAULT_ROUTINE_NAME, user=user,
        defaults=dict(subcategory="lower_body", default_work_seconds=40, default_rest_seconds=20),
    )
    if created:
        for i, slug in enumerate(DEFAULT_ROUTINE_ORDER):
            ex = Exercise.objects.get(slug=slug)
            RoutineItem.objects.create(routine=routine, exercise=ex, order=i)


def unseed(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Routine = apps.get_model("tasks", "Routine")
    Routine.objects.filter(name=DEFAULT_ROUTINE_NAME).delete()
    slugs = [e["slug"] for e in UPPER_BODY + LOWER_BODY + RUNNING]
    Exercise.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
