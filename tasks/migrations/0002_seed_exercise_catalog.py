# Siembra el catálogo de ejercicios y la rutina por defecto.
#
# Reconstruida a partir de seis migraciones de datos antiguas
# (0008, 0009, 0011, 0018, 0026, 0031 del historial previo al reseteo
# de migraciones) en una sola, reflejando el estado FINAL.
#
# Segunda pasada (ver 0011_camera_exercise_updates, que aplica lo mismo
# a bases de datos que ya habían corrido esta migración con el estado
# viejo): "Superman" y "Circuito de abdominales" (un placeholder de
# sesión combinada, deprecado desde que cada ejercicio guarda su propia
# WorkoutSession — ver routine_save) se quitan del todo. Crunch y
# elevación de piernas pasan a mode="pose": ya tienen contador de
# cámara propio en workout.js, así que no tiene sentido dejarlos solo
# cronometrados. Plancha y plancha lateral se quedan cronometradas (una
# plancha se aguanta, no se cuenta en repeticiones) pero con
# counter_key puesto: el reproductor de circuitos usa la cámara para
# comprobar la postura y pausar la cuenta atrás si se rompe.
#
# config={} en todos: no hay ajustes de MediaPipe que perder aquí — el
# conteo por cámara vive en el JS, indexado por counter_key, no en
# este campo.
#
# Tercera pasada (ver 0012_add_camera_exercises): doble crunch y
# tijeretas, dos ejercicios de abdominales que no existían antes, ambos
# con contador de cámara propio en workout.js desde el principio.

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
    dict(slug="plank", name="Plancha", mode="timed", counter_key="plank", order=8),
    dict(slug="crunch", name="Crunch", mode="pose", counter_key="crunch", order=9),
    dict(slug="leg-raise", name="Elevación de piernas", mode="pose", counter_key="legraise", order=10),
    dict(slug="bicycle-crunch", name="Bicicleta", mode="timed", counter_key="", order=11),
    dict(slug="side-plank", name="Plancha lateral", mode="timed", counter_key="sideplank", order=12),
    # Añadidos en 0012_add_camera_exercises — puestos aquí también (get_or_create,
    # así que no pasa nada si 0012 los crea de todas formas) para que una
    # instalación nueva los tenga desde el primer momento, igual que el
    # resto del catálogo. Ver ese archivo para el porqué de cada uno.
    dict(slug="double-crunch", name="Doble crunch", mode="pose", counter_key="doublecrunch", order=13),
    dict(slug="scissor-kick", name="Scissor Kicks", mode="pose", counter_key="scissor", order=14),
]

RUNNING = [
    dict(slug="running", name="Correr", mode="distance", counter_key="", order=7),
]

DEFAULT_ROUTINE_NAME = "Abdominales completo"
DEFAULT_ROUTINE_ORDER = ["plank", "crunch", "leg-raise", "bicycle-crunch", "side-plank"]


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
