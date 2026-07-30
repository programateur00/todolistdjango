# Añade fondos (dips), normales y con peso.
#
# Usan counter_key="dip", que es un contador DISTINTO al de dominadas:
# una dominada se detecta por posición (calibras dónde está la barra y
# cuentas cuando la nariz la pasa), pero un fondo no tiene barra de
# referencia. Se detecta por el ángulo del codo — extendido arriba,
# doblado abajo — que además no depende de la distancia a la cámara.

from django.db import migrations

DIPS = [
    dict(slug="dips", name="Fondos", order=15),
    dict(slug="weighted-dips", name="Fondos con peso", order=16),
]


def seed(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for d in DIPS:
        Exercise.objects.get_or_create(
            slug=d["slug"],
            defaults=dict(
                name=d["name"], mode="pose", counter_key="dip",
                body_area="upper_body", config={}, is_active=True, order=d["order"],
            ),
        )


def unseed(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[d["slug"] for d in DIPS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0030_plan_custom_days_plan_due_time_plan_interval_and_more"),
    ]

    operations = [migrations.RunPython(seed, unseed)]
