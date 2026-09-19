from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0066_task_course_lessons"),
    ]

    operations = [
        migrations.AddField(
            model_name="planitem",
            name="course_progress_pct",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="planitem",
            name="course_lessons_done",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="planitem",
            name="course_lessons_total",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
