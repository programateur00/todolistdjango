# "Plancha dinámica" (0106) pasa a tren inferior, como el resto de planchas
# (plank, side-plank...): Alex (2026-10-11). 0106 la había copiado de
# "push-up" (tren superior). Para quien ya tuviera aplicada 0106 con la zona
# anterior; en una base nueva 0106 ya la crea en tren inferior y esto no
# cambia nada. Solo toca ese slug.

from django.db import migrations


def to_lower_body(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug="dynamic-plank").update(body_area="lower_body")


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0106_add_vup_plank_variants"),
    ]

    operations = [
        migrations.RunPython(to_lower_body, migrations.RunPython.noop),
    ]
