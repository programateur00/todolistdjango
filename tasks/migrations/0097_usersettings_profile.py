# Perfil del usuario (nombre, avatar, fecha de nacimiento, altura, peso
# objetivo) en UserSettings, e historial de peso (WeightLog).
# Ver tasks/profile.py.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0096_calories"),
    ]

    operations = [
        migrations.AddField(model_name="usersettings", name="display_name",
                            field=models.CharField(blank=True, default="", max_length=40)),
        migrations.AddField(model_name="usersettings", name="avatar_emoji",
                            field=models.CharField(blank=True, default="💪", max_length=16)),
        migrations.AddField(model_name="usersettings", name="avatar_color",
                            field=models.CharField(blank=True, default="#FF6A1F", max_length=7)),
        migrations.AddField(model_name="usersettings", name="birth_date",
                            field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="usersettings", name="height_cm",
                            field=models.PositiveSmallIntegerField(
                                blank=True, null=True, help_text="Altura en cm (solo informativa).")),
        migrations.AddField(model_name="usersettings", name="goal_weight_kg",
                            field=models.FloatField(blank=True, null=True, help_text="Peso objetivo en kg.")),
        migrations.CreateModel(
            name="WeightLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("weight_kg", models.FloatField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                           related_name="weight_logs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-date"]},
        ),
        migrations.AddConstraint(
            model_name="weightlog",
            constraint=models.UniqueConstraint(fields=("user", "date"), name="unique_weightlog_per_user_day"),
        ),
    ]
