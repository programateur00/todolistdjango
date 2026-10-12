# Ejercicios nuevos "Flexiones diamante" (slug "diamond-push-up") y "Flexiones
# anchas" (slug "wide-push-up"), pedidos por Alex (2026-10-11): versiones
# "idénticas" a las flexiones normales, porque de perfil a la cámara la
# diferencia (manos juntas en diamante / manos más abiertas que los hombros)
# no se ve.
#
# Mismo contador de cámara que "Flexiones" (counter_key="pushup" ->
# processPushup en workout.js), sin tocar workout.js ni las apps: el contador
# solo mide el ángulo del codo de perfil, igual que "wide-weighted-pullup"
# (0085) comparte contador con "wide-pullup" y "weighted-crunch" (0099) con
# "crunch". Al compartir counter_key heredan también todo lo que cuelga de
# "pushup" (selector de lado, auto-avance, cierre de serie, etc.).
#
# Niveles: diamante "intermediate" (más exigente para tríceps/muñecas que la
# normal, que es "beginner"); anchas "beginner" (misma exigencia que la
# normal). MET 6.0 como "push-up" (0096). order 41/42: justo detrás de
# "weighted-crunch" (40) para que el generador automático de planes de tren
# superior (tope _FOCUSED_ZONE_MAX_ITEMS) los ponga los últimos y no llenen
# el plan de flexiones. get_or_create idempotente, mismo patrón que 0085/0099.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="diamond-push-up", name="Flexiones diamante",
         mode="pose", counter_key="pushup", body_area="upper_body",
         level="intermediate", met=6.0, order=41),
    dict(slug="wide-push-up", name="Flexiones anchas",
         mode="pose", counter_key="pushup", body_area="upper_body",
         level="beginner", met=6.0, order=42),
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
        ("tasks", "0099_add_weighted_crunch"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
