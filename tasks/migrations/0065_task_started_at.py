from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0064_task_reading_day_progress"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="started_at",
            field=models.DateTimeField(
                blank=True, null=True,
                help_text="Cuándo entraste a hacer la tarea (entreno, vídeo, lectura...). Si "
                          "entras antes de la hora límite, no se auto-marca como no hecha "
                          "mientras la estás haciendo (ver Task.STARTED_GRACE_HOURS).",
            ),
        ),
    ]
