# Cambia mountain climbers por plancha lateral en el circuito.
#
# Motivo: mountain climbers es el único ejercicio del circuito sin
# ilustración en la colección de Everkinetic, y además era el que menos
# abdomen trabajaba de los seis (mete sobre todo cardio). La plancha
# lateral sí tiene sus dos posturas dibujadas, trabaja oblicuos, y
# equilibra el circuito: queda alternando boca abajo y boca arriba.
#
# mountain-climber NO se borra, solo se desactiva: si alguien ya lo tiene
# en un circuito propio, borrarlo se lo rompería.

from django.db import migrations


def swap(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    RoutineItem = apps.get_model("tasks", "RoutineItem")

    side_plank, _ = Exercise.objects.get_or_create(
        slug="side-plank",
        defaults=dict(
            name="Plancha lateral", mode="timed", counter_key="",
            body_area="lower_body", config={}, is_active=True, order=13,
        ),
    )

    mc = Exercise.objects.filter(slug="mountain-climber").first()
    if mc:
        # Sustituirlo allí donde se estuviera usando.
        RoutineItem.objects.filter(exercise=mc).update(exercise=side_plank)
        mc.is_active = False
        mc.save()


def unswap(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    mc = Exercise.objects.filter(slug="mountain-climber").first()
    if mc:
        mc.is_active = True
        mc.save()
    Exercise.objects.filter(slug="side-plank").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0025_task_avoid_fail_label_task_avoid_question_and_more"),
    ]

    operations = [migrations.RunPython(swap, unswap)]
