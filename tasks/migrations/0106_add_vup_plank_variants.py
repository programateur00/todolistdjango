# Ejercicios nuevos pedidos por Alex (2026-10-11): "V-ups" (slug "v-up"),
# "Plancha con toques de hombro" (slug "plank-shoulder-taps"), "Plancha
# dinámica" (arriba y abajo, slug "dynamic-plank") y "Plancha lateral con
# cadera" (slug "side-plank-hip-dips").
#
# Sin contador nuevo: misma regla que 0100/0104/0105 -- las variantes que la
# cámara no distingue comparten el contador del ejercicio base. Sin tocar
# workout.js ni las apps:
#   - v-up                -> "vup" (contador propio, processVUp en workout.js:
#                            torso y piernas rectas suben a la vez, manos a los
#                            talones). Al principio compartía "doublecrunch",
#                            pero eso contaba rodillas al pecho; ver 0109.
#   - plank-shoulder-taps -> "plank" (aguante por tiempo, mode timed): la
#                            cámara no ve los toques; solo se cuenta que
#                            mantengas la postura de plancha.
#   - dynamic-plank       -> "pushup" (processPushup: ángulo del codo de
#                            perfil). Subir y bajar de antebrazos a manos es
#                            el mismo ciclo de codo ~90 <-> ~160 que una
#                            flexión; 1 rep = 1 ciclo completo.
#   - side-plank-hip-dips -> "sideplank" (aguante por tiempo, mode timed):
#                            cuenta mientras mantengas la postura lateral.
#                            OJO: al bajar la cadera cerca del suelo en cada
#                            toque puede perder la postura (SIDEPLANK_MIN_HIP_
#                            LIFT) y pausar el cronómetro unos instantes --
#                            pendiente de afinar con un vídeo real.
#
# body_area y met se copian del ejercicio base (así no se inventa una
# clasificación distinta), salvo met de plancha dinámica (4.5: más suave que
# una flexión). La plancha dinámica copia body_area de "plank" (tren inferior,
# como el resto de planchas), aunque use el contador de flexiones. Niveles: v-up "advanced"; toques de hombro, dinámica y
# lateral con cadera "intermediate". order 53-56. get_or_create idempotente.

from django.db import migrations

# slug, nombre, base (slug del que copiar body_area/met), mode, counter_key, nivel, met (None = el del base), order
NEW_EXERCISES = [
    ("v-up", "V-ups", "double-crunch", "pose", "vup", "advanced", None, 53),
    ("plank-shoulder-taps", "Plancha con toques de hombro", "plank", "timed", "plank", "intermediate", None, 54),
    ("dynamic-plank", "Plancha dinámica", "plank", "pose", "pushup", "intermediate", 4.5, 55),
    ("side-plank-hip-dips", "Plancha lateral con cadera", "side-plank", "timed", "sideplank", "intermediate", None, 56),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for slug, name, base_slug, mode, counter_key, level, met, order in NEW_EXERCISES:
        base = Exercise.objects.filter(slug=base_slug).first()
        Exercise.objects.get_or_create(slug=slug, defaults=dict(
            name=name, mode=mode, counter_key=counter_key,
            body_area=base.body_area if base else "",
            level=level,
            met=met if met is not None else (base.met if base else None),
            config={}, is_active=True, order=order,
        ))


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e[0] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0105_add_commando_pullup"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
