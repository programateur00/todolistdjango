from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0065_task_started_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="course_lessons_done",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="task",
            name="course_lessons_total",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
