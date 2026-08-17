# Añade CoursePlaylist.level_to: algunas playlists cubren varios
# niveles MCER seguidos sin cortes (ej. una sola playlist de A1 a B2),
# no siempre uno solo — ver api._catalog_entries_for_language, que ya
# no exige coincidencia exacta de nivel. En blanco = un solo nivel,
# compatible con todo el catálogo ya cargado.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0009_language_native_audience_and_quizzes"),
    ]

    operations = [
        migrations.AddField(
            model_name="courseplaylist",
            name="level_to",
            field=models.CharField(
                blank=True,
                choices=[
                    ("A1", "A1"),
                    ("A2", "A2"),
                    ("B1", "B1"),
                    ("B2", "B2"),
                    ("C1", "C1"),
                    ("C2", "C2"),
                ],
                help_text="Si esta playlist cubre VARIOS niveles seguidos sin cortes (ej. una sola playlist de A1 a B2), el nivel más alto que cubre. En blanco = cubre solo `level`, como hasta ahora.",
                max_length=2,
            ),
        ),
        migrations.AlterField(
            model_name="courseplaylist",
            name="level",
            field=models.CharField(
                choices=[
                    ("A1", "A1"),
                    ("A2", "A2"),
                    ("B1", "B1"),
                    ("B2", "B2"),
                    ("C1", "C1"),
                    ("C2", "C2"),
                ],
                help_text="Nivel más bajo que cubre esta playlist (si solo cubre uno, es el único).",
                max_length=2,
            ),
        ),
    ]
