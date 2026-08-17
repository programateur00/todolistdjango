# Generated for D+E: minutos objetivo/día en cursos de idioma, y
# minutos reales vistos guardados en Occurrence.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0007_task_language_level"),
    ]

    operations = [
        migrations.AddField(
            model_name="plan",
            name="language_daily_minutes",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text="Solo con study_subtype='language': minutos de vídeo al día. En "
                           "blanco, exige ver el vídeo del día entero.",
            ),
        ),
        migrations.AddField(
            model_name="occurrence",
            name="minutes_watched",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text="Solo en tareas de vídeo: minutos reales vistos en el navegador "
                           "(IFrame API de YouTube), no un dato introducido a mano.",
            ),
        ),
    ]
