# Campos de sincronización, escritos a mano a propósito.
#
# `makemigrations` no puede generar esto solo: añadir un campo unique a
# una tabla con filas existentes le obliga a preguntar de forma
# interactiva qué valor poner, y además pondría el MISMO valor en todas
# las filas, violando la unicidad al instante.
#
# La secuencia correcta es en tres pasos por modelo:
#   1. Añadir el campo permitiendo nulos y sin unique.
#   2. Rellenar fila por fila con un uuid4 distinto (RunPython).
#   3. Recién entonces marcarlo unique y no nulo.
#
# Para qué sirve cada campo:
#   uuid       -> identidad global. Si el móvil y la web crean una tarea
#                 cada uno sin conexión, con ids autoincrementales ambas
#                 serían la "número 7" y chocarían al sincronizar.
#   updated_at -> qué versión es más reciente cuando hay conflicto.
#   deleted_at -> borrado suave. Si se borra la fila de verdad, el otro
#                 dispositivo no puede saber que se borró y la resucita.

import uuid

import django.db.models.deletion
from django.db import migrations, models


MODELS = ["task", "occurrence", "workoutsession", "routine"]


def fill_uuids(apps, schema_editor):
    """
    Asigna un uuid4 DISTINTO a cada fila.

    Ojo con el detalle que hace fallar esto si se hace de la forma obvia:
    si el campo se añade con default=uuid.uuid4, Django evalúa esa función
    UNA sola vez durante la migración y escribe el mismo valor en todas
    las filas — con lo que el paso siguiente (marcarlo unique) revienta.
    Por eso el campo se añade sin default (queda NULL) y se rellena aquí
    fila por fila.
    """
    for model_name in MODELS:
        Model = apps.get_model("tasks", model_name)
        for pk in Model.objects.values_list("pk", flat=True).iterator():
            Model.objects.filter(pk=pk).update(uuid=uuid.uuid4())


def noop(apps, schema_editor):
    pass


def _add_uuid(model_name):
    return migrations.AddField(
        model_name=model_name,
        name="uuid",
        field=models.UUIDField(editable=False, null=True),
    )


def _make_uuid_unique(model_name):
    return migrations.AlterField(
        model_name=model_name,
        name="uuid",
        field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
    )


def _add_timestamps(model_name, help_text=""):
    return [
        migrations.AddField(
            model_name=model_name,
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name=model_name,
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True, help_text=help_text),
        ),
    ]


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0020_remove_task_is_avoid_alter_task_category"),
    ]

    operations = (
        [_add_uuid(m) for m in MODELS]
        + [migrations.RunPython(fill_uuids, noop)]
        + [_make_uuid_unique(m) for m in MODELS]
        + _add_timestamps(
            "task",
            "Borrado suave: si se borra de verdad, el otro dispositivo no puede "
            "enterarse al sincronizar y la resucitaría.",
        )
        + _add_timestamps("occurrence")
        + _add_timestamps("workoutsession")
        + _add_timestamps("routine")
    )
