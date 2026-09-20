# Añade "Pike push-ups" (flexiones en V invertida) con cámara (2026-09-20).
#
#   - "pike-push-up" (mode="pose", counter_key="pikepushup"): repeticiones. De perfil a la cámara, en V
#     invertida (manos y pies en el suelo, caderas en alto, brazos y piernas estirados); una rep = bajar
#     doblando los brazos mientras la cabeza baja hacia el suelo y volver a estirarlos del todo.
#
# El contador vive en workout.js (processPikePushup, bloque PIKE_*), en la copia web y en la de la app
# móvil. body_area="upper_body" (hombros/tríceps, igual que "Flexiones").
#
# Mismo patrón que 0069 (get_or_create idempotente; no toca filas ya existentes con ese slug).

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="pike-push-up", name="Pike push-ups", mode="pose", counter_key="pikepushup", order=30),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for e in NEW_EXERCISES:
        Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode=e["mode"], counter_key=e["counter_key"],
            body_area="upper_body", config={}, is_active=True, order=e["order"],
        ))


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0069_add_superman"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
