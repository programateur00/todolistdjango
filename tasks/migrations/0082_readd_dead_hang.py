# Vuelve a añadir "Dead Hang" (aguante en barra) al catálogo. Se había
# quitado en 0022_replace_dead_hang_with_handstand.py por un problema de
# fondo: colgarte con las piernas rectas es indistinguible para MediaPipe
# de estar de pie estirando los brazos hacia la barra sin haber saltado
# todavía (misma relación hombro-muñeca en los dos casos). Tres intentos
# de arreglarlo en su momento (visibilidad de tobillo, proporción
# espinilla/muslo, profundidad z) se descartaron por no funcionar contra
# datos reales -- ver el historial de comentarios en workout.js, junto a
# checkDeadHangPosture.
#
# Vídeo de referencia real (aguanteenbarra.mp4, 2026-09-27, "empieza de
# cero, olvida todo lo anterior"): confirma que el aguante se hace
# doblando las rodillas Y la cadera hacia arriba (no con las piernas
# rectas) -- misma familia de postura que Kneehold Bar (ver 0015), así
# que ahora se reutiliza la misma técnica que ya funciona ahí (cadera-
# rodilla en vertical, sin tobillo), con un criterio de cadera añadido
# (ángulo hombro-cadera-rodilla) que da más margen frente a "fingir" el
# aguante de pie -- ver checkDeadHangPosture en workout.js para el
# análisis completo contra pose real.
#
# body_area="upper_body", igual que en 0018 (antes de quitarse): sigue
# siendo agarre/antebrazo/hombros, ahora con la cadera/rodillas
# trabajando también al subirlas, pero el énfasis principal sigue siendo
# tren superior, igual que Kneehold Bar.
#
# Mismo patrón que 0018/0080/0081 (siembra el catálogo, get_or_create
# idempotente): si alguien ya tiene esta migración aplicada de antes de
# 0022 (imposible en la práctica, pero por si acaso) no se duplica nada.

from django.db import migrations

NEW_EXERCISES = [
    dict(slug="dead-hang", name="Dead Hang", mode="timed", counter_key="deadhang", order=20),
]


def add_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for e in NEW_EXERCISES:
        Exercise.objects.get_or_create(slug=e["slug"], defaults=dict(
            name=e["name"], mode=e["mode"], counter_key=e["counter_key"],
            body_area="upper_body", config={}, is_active=True, order=e["order"],
        ))


def remove_exercises(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    Exercise.objects.filter(slug__in=[e["slug"] for e in NEW_EXERCISES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0081_add_scapular_pull"),
    ]

    operations = [
        migrations.RunPython(add_exercises, remove_exercises),
    ]
