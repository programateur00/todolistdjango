# Una tarea suelta (freestyle) de Estudio con una playlist de YouTube no
# tenia forma de saber cuantos videos tiene la lista ni cual es el
# ultimo -- eso solo lo sabia PlanItem (ver 0021_study_playlist_progress),
# porque solo un objetivo de Plan podia tener cache de playlist. Sin
# saber donde acaba la lista, una tarea suelta con playlist nunca podia
# cerrarse sola al terminarla: se quedaba repitiendose para siempre.
#
# Este campo replica en Task exactamente lo mismo que ya tiene PlanItem
# (mismo formato de cache, mismo mecanismo de sincronizacion via
# Task.sync_playlist_videos()), para que una tarea suelta con playlist
# tambien pueda detectar "esto era el ultimo video" y cerrar la serie
# con finish_recurring_series() -- ver tasks/models.py.
#
# De paso se actualiza el texto de ayuda de playlist_start_index, que
# hasta ahora decia que solo aplicaba a objetivos de Plan.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0052_add_jumping_jack"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="playlist_videos_cache",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="task",
            name="playlist_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="task",
            name="playlist_start_index",
            field=models.PositiveIntegerField(
                blank=True,
                help_text=(
                    "Solo con youtube_playlist_id: en que posicion de la lista (0 = el "
                    "primero) hay que empezar a reproducir hoy, para no volver siempre al "
                    "principio de la playlist. Lo mantienen al dia tanto Plan.sync_task() "
                    "(objetivos de Plan) como _spawn_next() (tareas sueltas repetidas), "
                    "usando playlist_videos_cache de abajo. En blanco = empezar por el "
                    "principio (playlist sin seguimiento, o recien puesta)."
                ),
                null=True,
            ),
        ),
    ]
