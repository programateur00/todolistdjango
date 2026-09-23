# Añade Task.watch_requires_audio / PlanItem.watch_requires_audio: para un
# "Curso de Udemy" (Task.SUBCATEGORY_UDEMY) sin apenas vídeo con sonido
# continuo (más ejercicios que clases habladas, ver conversación con Alex
# 2026-09-23), permite desactivar la exigencia de chrome.tabs.audible en
# la extensión de Chrome y contar en su lugar con la pestaña en primer
# plano + sin inactividad de ratón/teclado (mismo mecanismo que ya usa
# Lectura de PDF, ver IDLE_DETECTION_SECONDS en chrome-extension/
# background.js). default=True conserva el comportamiento de siempre
# (exigir audio) para todos los cursos ya existentes.
#
# Solo se configura desde el objetivo (PlanItem) de un Plan de Estudio ·
# Hábito simple con palabra clave puesta -- un Udemy freestyle (Task
# suelta) nunca lleva palabra clave a propósito (ver
# Task.study_link_error), así que ahí este campo no tiene efecto real.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0077_add_elephant_steps_hold"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="watch_requires_audio",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="planitem",
            name="watch_requires_audio",
            field=models.BooleanField(default=True),
        ),
    ]
