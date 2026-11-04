"""Sustituye "Clases de Ilerna (Zoom)" por el tipo genérico "Tiempo en una web".

- Campos nuevos en Task y PlanItem: watch_url, watch_idle_seconds, watch_audio_counts.
- Las tareas/objetivos/sesiones de Ilerna que ya existían pasan a ser una web
  con ilernaonline.zoom.us, con el sonido contando (que es como funcionaban:
  una grabación de clase suena sin tocar nada) y 5 min de margen sin actividad.
"""
from django.db import migrations, models


def ilerna_to_web(apps, schema_editor):
    Task = apps.get_model("tasks", "Task")
    PlanItem = apps.get_model("tasks", "PlanItem")
    TimerSession = apps.get_model("tasks", "TimerSession")
    Task.objects.filter(subcategory="ilerna").update(
        subcategory="web", watch_url="ilernaonline.zoom.us",
        watch_audio_counts=True, watch_idle_seconds=300,
    )
    PlanItem.objects.filter(watch_site="ilerna").update(
        watch_site="web", watch_url="ilernaonline.zoom.us",
        watch_audio_counts=True, watch_idle_seconds=300,
    )
    TimerSession.objects.filter(subcategory="ilerna").update(subcategory="web")


def web_to_ilerna(apps, schema_editor):
    Task = apps.get_model("tasks", "Task")
    PlanItem = apps.get_model("tasks", "PlanItem")
    TimerSession = apps.get_model("tasks", "TimerSession")
    Task.objects.filter(subcategory="web").update(subcategory="ilerna")
    PlanItem.objects.filter(watch_site="web").update(watch_site="ilerna")
    TimerSession.objects.filter(subcategory="web").update(subcategory="ilerna")


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0127_remove_high_leg_raise'),
    ]

    operations = [
        migrations.AddField(
            model_name='planitem',
            name='watch_audio_counts',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='planitem',
            name='watch_idle_seconds',
            field=models.PositiveIntegerField(default=180),
        ),
        migrations.AddField(
            model_name='planitem',
            name='watch_url',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='task',
            name='watch_audio_counts',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='task',
            name='watch_idle_seconds',
            field=models.PositiveIntegerField(default=180),
        ),
        migrations.AddField(
            model_name='task',
            name='watch_url',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterField(
            model_name='task',
            name='subcategory',
            field=models.CharField(blank=True, choices=[('upper_body', 'Tren superior'), ('lower_body', 'Tren inferior'), ('running', 'Running'), ('warmup', 'Estiramientos y calentamientos'), ('reading', 'Lectura'), ('language', 'Idiomas'), ('udemy', 'Curso de Udemy'), ('web', 'Tiempo en una web')], help_text='Deporte → qué entrenar. Enfoque → qué cronometrar. En el resto no se usa.', max_length=16),
        ),
        migrations.RunPython(ilerna_to_web, web_to_ilerna),
    ]
