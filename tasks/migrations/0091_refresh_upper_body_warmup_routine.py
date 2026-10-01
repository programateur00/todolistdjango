# Pone al día el circuito de calentamiento de TREN SUPERIOR (Alex, 2026-10-01).
# El circuito guardado en la base de datos era una versión antigua del de
# seed_warmup_routines.py (sin Dead Hang ni dominadas escapulares, con los
# estiramientos de brazo una sola vez...), porque el seed solo se aplica al
# lanzarlo a mano. Esta migración reconstruye sus ítems para que el cambio
# llegue solo con `migrate` (web y app móvil leen el mismo circuito por API).
#
# Debe coincidir con el "tren superior" de seed_warmup_routines.py. Idempotente:
# borra y recrea los ítems de cada circuito de calentamiento de tren superior.

from django.db import migrations

# (slug, target_sets, target_reps) -- None/None = cronometrado.
ITEMS = [
    ("neck-lateral-mobility", 1, 30),
    ("neck-turn-side", 1, 30),
    ("arm-circles", 1, 30),                    # vez 1 de 2
    ("arm-circles", 1, 30),                    # vez 2 de 2
    ("arm-scissors", 1, 30),
    ("arm-cross-stretch", None, None),         # brazo 1
    ("arm-cross-stretch", None, None),         # brazo 2
    ("triceps-overhead-stretch", None, None),  # brazo 1
    ("triceps-overhead-stretch", None, None),  # brazo 2
    ("forearm-rotation-elbow-hold", 1, 30),    # brazo 1
    ("forearm-rotation-elbow-hold", 1, 30),    # brazo 2
    ("jumping-jack", 1, 30),
    ("push-up", 1, 10),
    ("dead-hang", None, None),                 # cronometrado
    ("scapular-pull", 1, 12),
]


def refresh(apps, schema_editor):
    Routine = apps.get_model("tasks", "Routine")
    RoutineItem = apps.get_model("tasks", "RoutineItem")
    Exercise = apps.get_model("tasks", "Exercise")

    routines = Routine.objects.filter(
        subcategory="upper_body", is_warmup_bookend=True, deleted_at__isnull=True,
    )
    for routine in routines:
        routine.items.all().delete()
        order = 0
        for slug, sets, reps in ITEMS:
            exercise = Exercise.objects.filter(slug=slug, is_active=True).first()
            if not exercise:
                continue
            kwargs = {}
            if sets is not None:
                kwargs["target_sets"] = sets
            if reps is not None:
                kwargs["target_reps"] = reps
            RoutineItem.objects.create(routine=routine, exercise=exercise, order=order, **kwargs)
            order += 1


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0090_planitem_no_headline_ordering"),
    ]

    operations = [
        migrations.RunPython(refresh, migrations.RunPython.noop),
    ]
