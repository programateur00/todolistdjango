# Seguimiento de la playlist de un objetivo de Estudio (Hábito simple):
#  - playlist_position: por qué vídeo vas. Lo guarda el reproductor mientras ves
#    (antes solo se deducía de las sesiones CUMPLIDAS, así que cerrar a medias
#    o ver más vídeos de los que pedía el día hacía volver a empezar).
#  - playlist_cache_id: qué playlist describe la caché. Antes, guardar el
#    objetivo (o editar el plan) volvía a sincronizar y REINICIABA el avance
#    aunque la lista fuera la misma; ahora solo se reinicia al cambiar de lista.
# Los objetivos que ya tenían caché reciben su playlist actual como
# playlist_cache_id, para que el primer guardado tras actualizar no reinicie nada.

from django.db import migrations, models
from django.db.models import F


def fill_cache_id(apps, schema_editor):
    PlanItem = apps.get_model("tasks", "PlanItem")
    PlanItem.objects.filter(playlist_synced_at__isnull=False).exclude(youtube_playlist_id="").update(
        playlist_cache_id=F("youtube_playlist_id")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0122_add_split_jump"),
    ]

    operations = [
        migrations.AddField(
            model_name="planitem",
            name="playlist_cache_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="planitem",
            name="playlist_position",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(fill_cache_id, migrations.RunPython.noop),
    ]
