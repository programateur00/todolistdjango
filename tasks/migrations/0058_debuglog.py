from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0057_task_reading_plan_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="DebugLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "platform",
                    models.CharField(
                        choices=[("web", "Web"), ("mobile", "Móvil")], max_length=10
                    ),
                ),
                ("counter_key", models.CharField(blank=True, max_length=60)),
                ("build", models.CharField(blank=True, max_length=60)),
                ("content", models.TextField()),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
