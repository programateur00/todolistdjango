# Un único resultado por serie y día.
#
# Antes, marcar hecha -> desmarcar -> marcar hecha creaba TRES ocurrencias
# para el mismo día, y streak_stats() las cuenta todas: las rachas salían
# infladas. Ya había un duplicado real en la base de datos cuando se hizo
# este cambio, así que no es teoría.
#
# El resultado de un día es un hecho corregible, no un registro que se
# apila. Ver Task._record_occurrence(), que ahora hace update_or_create.
#
# Y de paso es lo que hace posible sincronizar: web y móvil pueden
# resolver el mismo día por separado y acaban con UNA fila, no dos.
#
# Ojo al orden: primero se limpian los duplicados existentes, luego se
# aplica la restricción. Al revés, la migración falla en cualquier base
# que ya tenga datos.

from django.db import migrations, models


def dedupe(apps, schema_editor):
    """Deja solo la ocurrencia más reciente de cada (series_id, due_date)."""
    Occurrence = apps.get_model("tasks", "Occurrence")
    seen = {}
    to_delete = []
    # Las más recientes primero: la primera que se ve de cada clave es la
    # que se conserva, el resto se descarta.
    for occ in Occurrence.objects.filter(due_date__isnull=False).order_by("-recorded_at", "-id"):
        key = (occ.series_id, occ.due_date)
        if key in seen:
            to_delete.append(occ.pk)
        else:
            seen[key] = occ.pk
    if to_delete:
        Occurrence.objects.filter(pk__in=to_delete).delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0021_sync_fields"),
    ]

    operations = [
        migrations.RunPython(dedupe, noop),
        migrations.AddConstraint(
            model_name="occurrence",
            constraint=models.UniqueConstraint(
                condition=models.Q(("due_date__isnull", False)),
                fields=("series_id", "due_date"),
                name="unique_occurrence_per_series_day",
            ),
        ),
    ]
