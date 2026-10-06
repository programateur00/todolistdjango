# Añade Occurrence.completion_pct: el % de cumplimiento de cada día, para
# que las estadísticas y su gráfica no cuenten solo "hecho / no hecho".
# Filas antiguas: hecho=100; no hecho = lo mejor que se llegó a hacer ese
# día según las sesiones de la tarea (0 si no hubo ninguna).
from django.db import migrations, models


def backfill(apps, schema_editor):
    Occurrence = apps.get_model("tasks", "Occurrence")
    WorkoutSession = apps.get_model("tasks", "WorkoutSession")
    for occ in Occurrence.objects.filter(completion_pct__isnull=True):
        pct = 0
        if occ.result == "done":
            pct = 100
        elif occ.task_id:
            pcts = [
                s.achievement_pct for s in WorkoutSession.objects.filter(task_id=occ.task_id)
                if getattr(s, "achievement_pct", None) is not None
            ]
            pct = max(0, min(100, max(pcts, default=0)))
        occ.completion_pct = pct
        occ.save(update_fields=["completion_pct"])


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0092_add_pistol_squat"),
    ]

    operations = [
        migrations.AddField(
            model_name="occurrence",
            name="completion_pct",
            field=models.PositiveSmallIntegerField(
                blank=True, null=True,
                help_text="% de cumplimiento de ese día (0-100). Hecha=100; no hecha=0, o lo "
                          "que se llegó a hacer si caducó con sesiones parciales. Ver "
                          "Task._day_completion_pct. None en filas antiguas sin calcular.",
            ),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
