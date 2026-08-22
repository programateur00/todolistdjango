# Corrige "Kneehold Bar" (slug="kneehold-bar") de tren superior a tren
# inferior — a petición del usuario, nada más ver el ejercicio ya
# clasificado en el sitio equivocado. Mismo criterio que el resto del
# catálogo de tren inferior (plancha, crunch, elevación de piernas,
# silla en pared): lo que se trabaja al subir las rodillas es el
# abdomen y la cadera, no el agarre — la barra solo sostiene el cuerpo,
# igual que el suelo sostiene una plancha.
#
# No basta con cambiar el body_area= en 0015 (ya hecho, por consistencia
# en instalaciones nuevas): esa migración usa get_or_create, así que si
# 0015 ya se aplicó sobre una base de datos real (como esta), la fila de
# Exercise ya existe con body_area="upper_body" y no se entera de que el
# diccionario de origen ha cambiado — mismo caso que 0013_rename_scissor_kick
# con el nombre de las tijeretas. Aquí se actualiza explícitamente la fila
# existente. El slug, mode y counter_key no cambian — solo la subcategoría
# bajo la que aparece al elegir "Deporte" en una tarea.

from django.db import migrations

SLUG = "kneehold-bar"
OLD_BODY_AREA = "upper_body"
NEW_BODY_AREA = "lower_body"


def move_forward(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug=SLUG).update(body_area=NEW_BODY_AREA)


def move_backward(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug=SLUG).update(body_area=OLD_BODY_AREA)


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0015_add_kneehold_bar"),
    ]

    operations = [
        migrations.RunPython(move_forward, move_backward),
    ]
