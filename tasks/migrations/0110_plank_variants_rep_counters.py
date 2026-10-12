# "Plancha con toques de hombro", "Plancha dinámica" y "Plancha lateral con cadera" (0106) no deben ser
# aguantes cronometrados sino de REPETICIONES (pedido de Alex, 2026-10-11), cada una con su contador propio
# en workout.js:
#   - plank-shoulder-taps -> "plankshouldertaps" (processPlankShoulderTaps: cada mano que se levanta y se
#                            vuelve a apoyar = 1 toque). Antes: timed + "plank".
#   - dynamic-plank       -> "dynamicplank" (processDynamicPlank: codo ~90-115° abajo / ~170° arriba = 1 rep).
#                            Antes: pose + "pushup", que no contaba bien en antebrazos (umbral de 100°).
#   - side-plank-hip-dips -> "sideplankhipdips" (processSidePlankHipDips: la cadera baja hacia el suelo y vuelve
#                            a subir = 1 rep). Antes: timed + "sideplank".
# Solo cambian mode y counter_key (body_area, nivel y MET se quedan como estaban); idempotente.

from django.db import migrations

# slug -> (mode, counter_key) nuevos / anteriores
NEW = {
    "plank-shoulder-taps": ("pose", "plankshouldertaps"),
    "dynamic-plank": ("pose", "dynamicplank"),
    "side-plank-hip-dips": ("pose", "sideplankhipdips"),
}
OLD = {
    "plank-shoulder-taps": ("timed", "plank"),
    "dynamic-plank": ("pose", "pushup"),
    "side-plank-hip-dips": ("timed", "sideplank"),
}


def _apply(apps, mapping):
    Exercise = apps.get_model("tasks", "Exercise")
    for slug, (mode, counter_key) in mapping.items():
        Exercise.objects.filter(slug=slug).update(mode=mode, counter_key=counter_key)


def forwards(apps, schema_editor):
    _apply(apps, NEW)


def backwards(apps, schema_editor):
    _apply(apps, OLD)


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0109_vup_own_counter"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
