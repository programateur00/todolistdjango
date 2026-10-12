# Ejercicios nuevos "Sentadillas búlgaras" (slug "bulgarian-split-squat"),
# "Sentadillas sumo" (slug "sumo-squat") y "Sentadillas con salto" (slug
# "jump-squat"), pedidos por Alex (2026-10-11). Tren inferior.
#
# Sin contador nuevo: misma regla que 0100 (flexiones diamante/anchas) -- las
# variantes que la cámara no distingue comparten el contador del ejercicio
# base y hacerlas bien es cosa del usuario. Sin tocar workout.js ni las apps:
#   - búlgara  -> counter_key="splitsquat" (processSplitSquat: ángulo de la
#                 rodilla delantera, igual que "split-squat", con el pie
#                 trasero apoyado en un banco/silla).
#   - sumo     -> counter_key="squat" (processSquat: ángulo de rodilla de
#                 perfil, igual que "squat"; la postura ancha no cambia nada).
#   - con salto-> counter_key="squat" (cada rep = bajar y volver a subir del
#                 todo; el salto es la subida).
#
# Niveles (ajustables en el admin): búlgara "intermediate" (unilateral +
# equilibrio con el pie trasero elevado), sumo "intermediate" (como "squat"),
# con salto "advanced" (pliométrico). MET 5.5 / 5.0 / 8.0. order 49-51, detrás
# de "pseudo-planche-push-up" (48). get_or_create idempotente.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="bulgarian-split-squat", name="Sentadillas búlgaras",
         mode="pose", counter_key="splitsquat", body_area="lower_body",
         level="intermediate", met=5.5, order=49),
    dict(slug="sumo-squat", name="Sentadillas sumo",
         mode="pose", counter_key="squat", body_area="lower_body",
         level="intermediate", met=5.0, order=50),
    dict(slug="jump-squat", name="Sentadillas con salto",
         mode="pose", counter_key="squat", body_area="lower_body",
         level="advanced", met=8.0, order=51),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for ex in NEW_EXERCISES:
        Exercise.objects.get_or_create(slug=ex["slug"], defaults=dict(
            name=ex["name"], mode=ex["mode"], counter_key=ex["counter_key"],
            body_area=ex["body_area"], level=ex["level"], met=ex["met"],
            config={}, is_active=True, order=ex["order"],
        ))


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0103_add_pseudo_planche_push_up"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
