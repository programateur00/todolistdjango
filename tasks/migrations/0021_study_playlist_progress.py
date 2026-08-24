# Campos para que un objetivo de Estudio · Hábito simple con una playlist
# de YouTube pueda llevar la cuenta de por dónde vas, en vez de reiniciar
# siempre en el vídeo 1 (ver Plan._study_playlist_progress /
# PlanItem.sync_playlist_videos en tasks/models.py): la caché ordenada de
# vídeos de la playlist (con su duración) y cuándo se sincronizó por
# última vez, en PlanItem — y en qué posición de la playlist hay que
# empezar a reproducir hoy, en Task.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0020_add_weighted_squat"),
    ]

    operations = [
        migrations.AddField(
            model_name="planitem",
            name="playlist_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="planitem",
            name="playlist_videos_cache",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="task",
            name="playlist_start_index",
            field=models.PositiveIntegerField(
                blank=True,
                help_text=(
                    "Solo con youtube_playlist_id, en un objetivo de Estudio · Hábito simple "
                    "con seguimiento de progreso (ver PlanItem.playlist_videos_cache): en qué "
                    "posición de la lista (0 = el primero) hay que empezar a reproducir hoy, "
                    "para no volver siempre al principio de la playlist. En blanco = empezar "
                    "por el principio, como antes de que existiera esto (playlist sin "
                    "seguimiento, o un vídeo/playlist sueltos fuera de un plan)."
                ),
                null=True,
            ),
        ),
    ]
