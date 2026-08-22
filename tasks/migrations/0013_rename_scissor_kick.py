# Renombra "Tijeretas" (slug="scissor-kick") a "Scissor Kicks", a petición
# del usuario: el nombre en castellano le resultaba demasiado coloquial.
#
# No basta con cambiar el name= en 0002 y 0012 (ya hecho, por consistencia
# en instalaciones nuevas): esas dos migraciones usan get_or_create, así
# que si 0012 ya se aplicó sobre una base de datos real, la fila de
# Exercise ya existe con name="Tijeretas" y no se entera de que el
# diccionario de origen ha cambiado. Aquí se actualiza explícitamente la
# fila existente. El slug ("scissor-kick") y el counter_key ("scissor")
# no cambian — el contador de cámara en workout.js sigue indexando por
# counter_key, no por el nombre.

from django.db import migrations

OLD_NAME = "Tijeretas"
NEW_NAME = "Scissor Kicks"
SLUG = "scissor-kick"


def rename_forward(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug=SLUG).update(name=NEW_NAME)


def rename_backward(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug=SLUG).update(name=OLD_NAME)


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0012_add_camera_exercises"),
    ]

    operations = [
        migrations.RunPython(rename_forward, rename_backward),
    ]
