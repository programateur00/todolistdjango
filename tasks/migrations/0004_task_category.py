from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0003_task_last_result"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="category",
            field=models.CharField(
                choices=[
                    ("general", "General"),
                    ("study", "Estudio"),
                    ("sport", "Deporte"),
                    ("work", "Trabajo"),
                    ("personal", "Personal"),
                    ("other", "Otro"),
                ],
                default="general",
                db_index=True,
                help_text=(
                    "Tipo de tarea. Define qué extras tendrá disponibles "
                    "(timer, pose tracking, etc)."
                ),
                max_length=16,
            ),
        ),
    ]
