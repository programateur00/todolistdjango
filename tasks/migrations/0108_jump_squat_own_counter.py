# "Sentadillas con salto" (0104) compartía el contador "squat" y contaba como
# válida una sentadilla normal sin saltar (reportado por Alex, 2026-10-11).
# Ahora tiene el suyo: counter_key="jumpsquat" -> processSquat en workout.js
# (mismo ángulo de rodilla de perfil) pero una repetición solo cuenta si
# además se ve el salto al subir (tobillos o cadera por encima de su altura de
# pie; ver JUMPSQUAT_*). Solo cambia el counter_key; idempotente.

from django.db import migrations


def set_jump_counter(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug="jump-squat").update(counter_key="jumpsquat")


def unset_jump_counter(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug="jump-squat").update(counter_key="squat")


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0107_dynamic_plank_lower_body"),
    ]

    operations = [
        migrations.RunPython(set_jump_counter, unset_jump_counter),
    ]
