# Calorías por ejercicio: Exercise.met (intensidad en METs, valores del
# Compendio de Actividad Física redondeados), WorkoutSession.calories_kcal
# y UserSettings (peso corporal). Ver tasks/calories.py.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

MET_BY_SLUG = {
    # Tren superior — tirones y empujes exigentes
    "pullup": 8.0, "wide-pullup": 8.0, "chinup": 8.0, "jumping-pullup": 6.0,
    "archer-pullup": 8.0, "weighted-pullup": 8.0, "wide-weighted-pullup": 8.0,
    "dips": 8.0, "weighted-dips": 8.0, "handstand-push-up": 8.0,
    "push-up": 6.0, "incline-push-up": 5.0, "pike-push-up": 6.0,
    "bench-dip": 4.0, "dumbbell-curl": 3.5, "scapular-pull": 3.5,
    "dead-hang": 3.0, "handstand": 4.0,
    # Tren inferior / core
    "squat": 5.0, "weighted-squat": 6.0, "split-squat": 5.0, "pistol-squat": 6.0,
    "burpee": 10.0, "situp": 4.5, "crunch": 3.8, "double-crunch": 4.0,
    "leg-raise": 4.0, "scissor-kick": 4.0, "bicycle-crunch": 4.0,
    "superman": 3.5, "l-sit": 5.0,
    "plank": 3.8, "side-plank": 3.8, "wall-sit": 3.8, "superman-hold": 3.5,
    "kneehold-bar": 4.0, "l-sit-hold": 4.5, "tuck-lever-bar": 4.5,
    # Calentamiento / movilidad / estiramientos
    "jumping-jack": 7.0, "heel-kicks": 5.0, "knee-raises": 5.0, "high-leg-raise": 4.5,
    "split-squat-warmup": 3.5, "elephant-steps": 2.8, "elephant-steps-hold": 2.3,
    "arm-circles": 2.5, "arm-scissors": 2.8, "hip-forward-back": 2.8,
    "hip-lateral-mobility": 2.8, "leg-rotation": 2.8, "neck-lateral-mobility": 2.0,
    "neck-turn-side": 2.0, "forearm-rotation-elbow-hold": 2.3,
    "arm-cross-stretch": 2.3, "seated-hamstring-stretch": 2.3,
    "standing-quad-stretch": 2.3, "triceps-overhead-stretch": 2.3,
}


def seed_met(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for slug, met in MET_BY_SLUG.items():
        Exercise.objects.filter(slug=slug, met__isnull=True).update(met=met)


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0095_trainingsession"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="exercise",
            name="met",
            field=models.FloatField(
                blank=True, null=True,
                help_text="Intensidad en METs para estimar calorías (kcal = MET × kg × horas). "
                          "Vacío = valor por defecto según el tipo (ver tasks/calories.py). "
                          "En running no aplica: se calcula con la velocidad.",
            ),
        ),
        migrations.AddField(
            model_name="workoutsession",
            name="calories_kcal",
            field=models.FloatField(
                blank=True, null=True,
                help_text="Calorías aproximadas gastadas en este ejercicio (MET × peso × tiempo, ver "
                          "tasks/calories.py). Se calcula al guardar la sesión con el peso de ese momento.",
            ),
        ),
        migrations.CreateModel(
            name="UserSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body_weight_kg", models.FloatField(
                    blank=True, null=True,
                    help_text="Peso corporal en kg, para estimar las calorías de cada ejercicio.",
                )),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE, related_name="app_settings",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.RunPython(seed_met, migrations.RunPython.noop),
    ]
