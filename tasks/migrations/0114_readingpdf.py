import django.db.models.deletion
import tasks.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    PDF de un Plan de lectura guardado en el servidor (ver ReadingPdf).

    Depende de LAS DOS 0113 a la vez: había dos hojas en el grafo
    (0113_add_frog_stand_crow_pose y 0113_add_toes_to_bar, ambas sobre
    0112) y `migrate` se negaba a correr. Esta migración las une.
    """

    dependencies = [
        ("tasks", "0113_add_frog_stand_crow_pose"),
        ("tasks", "0113_add_toes_to_bar"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ReadingPdf",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=64)),
                ("file", models.FileField(upload_to=tasks.models._reading_pdf_path)),
                ("original_name", models.CharField(blank=True, max_length=255)),
                ("size", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                           related_name="reading_pdfs", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="readingpdf",
            constraint=models.UniqueConstraint(fields=("user", "key"), name="uniq_reading_pdf_user_key"),
        ),
    ]
