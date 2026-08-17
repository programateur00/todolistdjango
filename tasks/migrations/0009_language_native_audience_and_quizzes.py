# Generado para: B (idioma nativo como filtro del catálogo de idiomas)
# y C (tests de repaso con IA, con su propia racha). A (quitar la IA
# del flujo de asignación de cursos) no toca el esquema.

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0008_video_watch_tracking"),
    ]

    operations = [
        migrations.AddField(
            model_name="courseplaylist",
            name="native_language",
            field=models.CharField(
                blank=True,
                help_text="Idioma en el que se explica el curso (ej. 'español'). En blanco = neutro, vale para cualquier hablante.",
                max_length=40,
            ),
        ),
        migrations.AlterField(
            model_name="courseplaylist",
            name="order",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Orden dentro de su idioma+nivel+idioma nativo, si hay varias — la de menor número es la que se asigna primero.",
            ),
        ),
        migrations.CreateModel(
            name="CourseQuiz",
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
                (
                    "uuid",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ("up_to_order", models.PositiveIntegerField(default=0)),
                (
                    "topics",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="Temas de los vídeos usados para generar este test.",
                    ),
                ),
                ("questions", models.JSONField(blank=True, default=list)),
                ("answers", models.JSONField(blank=True, null=True)),
                ("score", models.PositiveIntegerField(blank=True, null=True)),
                ("total", models.PositiveIntegerField(default=0)),
                ("passed", models.BooleanField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("answered_at", models.DateTimeField(blank=True, null=True)),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="quizzes",
                        to="tasks.plan",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
