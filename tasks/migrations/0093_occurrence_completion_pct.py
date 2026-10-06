# Occurrence.completion_pct: el % de cumplimiento de cada día (media del %
# de todos los ejercicios hechos ese día), para que las estadísticas y su
# gráfica no cuenten solo "hecho / no hecho". Filas antiguas: null (se
# muestran como 100/0 según el resultado, ver Occurrence.pct; para
# recalcularlas con las sesiones guardadas: manage.py backfill_completion_pct).
from django.db import migrations, models


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
                help_text="% de cumplimiento de ese día: media del % de cada ejercicio hecho "
                          "(puede pasar de 100). Sin sesiones con objetivo: hecha=100, no hecha=0. "
                          "Ver Task.day_completion_pct. None en filas antiguas (ver Occurrence.pct y "
                          "el comando backfill_completion_pct).",
            ),
        ),
    ]
