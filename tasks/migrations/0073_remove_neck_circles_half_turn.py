# Retira "Círculos de cuello" y "Media vuelta de cuello" (2026-09-21): a petición de Alex, del cuello solo se quedan
# la inclinación oreja-hombro (neck-lateral-mobility) y el giro "no" (neck-turn-side). Borra las filas del catálogo
# (y, por cascada, sus RoutineItem, con lo que el circuito de calentamiento de tren superior queda actualizado
# sin re-lanzar seed_warmup_routines). 0042/0043 se conservan para no romper el historial. Idempotente; la marcha
# atrás no las restaura.

from django.db import migrations


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=["neck-circles", "neck-half-turn"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0072_remove_mountain_climber"),
    ]

    operations = [
        migrations.RunPython(remove_exercises, migrations.RunPython.noop),
    ]
