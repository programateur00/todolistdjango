# Quita "Elevación de pierna alta" del circuito de calentamiento de TREN
# INFERIOR (Alex, 2026-10-08). Ya se había quitado de seed_warmup_routines.py
# el 2026-10-06, pero el seed solo se aplica lanzándolo a mano, así que el
# circuito guardado en la base de datos (el que lee la app móvil por API)
# seguía teniéndolo. Esta migración lo borra para que el cambio llegue solo
# con `migrate` (mismo motivo que 0091).
#
# Solo toca los ítems de ese ejercicio en circuitos de calentamiento
# (is_warmup_bookend) de tren inferior; el ejercicio sigue en el catálogo y
# el resto del circuito queda igual (solo se renumera `order` sin huecos).
# Idempotente.

from django.db import migrations

SLUG = "high-leg-raise"


def remove_item(apps, schema_editor):
    Routine = apps.get_model("tasks", "Routine")
    RoutineItem = apps.get_model("tasks", "RoutineItem")

    routines = Routine.objects.filter(
        subcategory="lower_body", is_warmup_bookend=True, deleted_at__isnull=True,
    )
    for routine in routines:
        deleted, _ = RoutineItem.objects.filter(
            routine=routine, exercise__slug=SLUG,
        ).delete()
        if not deleted:
            continue
        for new_order, item in enumerate(routine.items.order_by("order", "id")):
            if item.order != new_order:
                item.order = new_order
                item.save(update_fields=["order"])


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0097_usersettings_profile"),
    ]

    operations = [
        migrations.RunPython(remove_item, migrations.RunPython.noop),
    ]
