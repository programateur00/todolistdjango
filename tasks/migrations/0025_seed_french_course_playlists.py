# -*- coding: utf-8 -*-
# Siembra en el catálogo (CoursePlaylist) los cursos de francés que ya
# se habían añadido a mano en local con `add_course_playlist`.
#
# Por qué hace falta esto: `db.sqlite3` está en .gitignore (cada
# entorno tiene el suyo — ver DEPLOY.md), así que lo que se añade con
# el comando en localhost NUNCA llega a PythonAnywicnhe/producción con
# un `git push` normal. El síntoma era justo ese: en local
# "build_language_plan_draft" encontraba los cursos de francés sin
# problema, pero en PythonAnywhere seguía diciendo "todavía no hay
# ningún curso verificado" para el mismo idioma/nivel, porque su
# `db.sqlite3` nunca tuvo esas filas. Una migración de datos sí viaja
# con el código y se aplica igual en cualquier sitio con
# `python manage.py migrate` — mismo patrón que 0012 (siembra
# idempotente vía get_or_create, sin nada que migrar de un estado
# viejo).
#
# added_at usa auto_now_add, así que no hace falta (ni se puede) fijar
# ese campo aquí: cada entorno lo pondrá a la hora en la que corra
# esta migración la primera vez.

from django.db import migrations

COURSE_PLAYLISTS = [
    dict(
        language="francés", level="A1", level_to="", native_language="español",
        youtube_playlist_id="PLRt_sFUAViN28hdOPUxHCVHujNaK4LR18",
        title="Curso de Francés A1 [Gratis y Certificado 🥇] - Edutin Academy",
        channel_title="Edutin Academy", order=0,
    ),
    dict(
        language="francés", level="A2", level_to="", native_language="español",
        youtube_playlist_id="PLRt_sFUAViN0qlTsLvnleaYy13k49GK35",
        title="Curso de Francés A2 [Gratis y Certificado] - Edutin Academy",
        channel_title="Edutin Academy", order=0,
    ),
    dict(
        language="francés", level="B1", level_to="", native_language="español",
        youtube_playlist_id="PLRt_sFUAViN1oVwBZcu9BZFt7p9GHW60w",
        title="Curso de Francés B1.2 [Gratis y Certificado] - Edutin Academy",
        channel_title="Edutin Academy", order=0,
    ),
    dict(
        language="francés", level="B2", level_to="", native_language="español",
        youtube_playlist_id="PLRt_sFUAViN3dJO229wf9c5stmdwWWkZh",
        title="Curso de Francés B2 [Gratis y Certificado] - Edutin Academy",
        channel_title="Edutin Academy", order=0,
    ),
    dict(
        language="francés", level="A1", level_to="B2", native_language="inglés",
        youtube_playlist_id="PL_bt5rj27IIUGgY2ZIe199_APdgOU6I7f",
        title="The Complete French Grammar Course 🇫🇷 A1 to B2",
        channel_title="The perfect French with Dylane", order=0,
    ),
]


def add_course_playlists(apps, schema_editor):
    CoursePlaylist = apps.get_model("tasks", "CoursePlaylist")
    for c in COURSE_PLAYLISTS:
        CoursePlaylist.objects.get_or_create(
            youtube_playlist_id=c["youtube_playlist_id"],
            defaults=dict(
                language=c["language"], level=c["level"], level_to=c["level_to"],
                native_language=c["native_language"], title=c["title"],
                channel_title=c["channel_title"], notes="", is_active=True,
                order=c["order"],
            ),
        )


def remove_course_playlists(apps, schema_editor):
    CoursePlaylist = apps.get_model("tasks", "CoursePlaylist")
    CoursePlaylist.objects.filter(
        youtube_playlist_id__in=[c["youtube_playlist_id"] for c in COURSE_PLAYLISTS],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0024_add_dumbbell_curl"),
    ]

    operations = [
        migrations.RunPython(add_course_playlists, remove_course_playlists),
    ]
