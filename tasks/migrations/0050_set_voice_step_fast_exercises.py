# La voz que cuenta reps en alto (workout.js, speakRep) anunciaba SIEMPRE
# de 5 en 5 (REP_VOICE_STEP=5, fijo, en todos los ejercicios), porque
# decirlas todas no daba tiempo a seguir el ritmo real de la serie. El
# usuario pidió que esto vuelva a ser "1 en 1" (anunciar cada rep) por
# defecto -- que es lo que ya hace Exercise.voice_step sin config, ver
# models.py -- y que se quede en "5 en 5" solo en los pocos ejercicios de
# cadencia muy rápida y continua que sí necesitan el salto para que la
# voz no se quede atrás: Jumping Jacks, Círculos de brazos, Talones al
# glúteo y Rodillas altas (los únicos que el usuario señaló explícitamente
# en el chat; el resto del catálogo -- incluido el resto de calentamiento/
# movilidad -- pasa a 1 en 1).
#
# Ajustable después sin migración nueva: el campo config del admin de
# Exercise (ver ExerciseAdmin.voice_step_display) acepta {"voice_step": N}
# para cualquier ejercicio.

from django.db import migrations

FAST_EXERCISE_SLUGS = ["jumping-jack", "arm-circles", "heel-kicks", "knee-raises"]


def set_voice_step_5(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for exercise in Exercise.objects.filter(slug__in=FAST_EXERCISE_SLUGS):
        config = dict(exercise.config or {})
        config["voice_step"] = 5
        exercise.config = config
        exercise.save(update_fields=["config"])


def unset_voice_step(apps, schema_editor):
    Exercise = apps.get_model("tasks", "Exercise")
    for exercise in Exercise.objects.filter(slug__in=FAST_EXERCISE_SLUGS):
        config = dict(exercise.config or {})
        config.pop("voice_step", None)
        exercise.config = config
        exercise.save(update_fields=["config"])


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0049_simplify_categories"),
    ]

    operations = [
        migrations.RunPython(set_voice_step_5, unset_voice_step),
    ]
