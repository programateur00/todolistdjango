"""
Añade una playlist al catálogo curado de cursos de idioma
(CoursePlaylist) — a mano, con vista previa real, nunca a ciegas.

Por qué existe esto en vez de fiarse de `search_courses`: esa búsqueda
demostró que para niveles con poco contenido gratis (C1/C2 sobre todo)
YouTube devuelve "lo más parecido" en vez de admitir que no hay nada —
en la práctica, cursos de principiantes reetiquetados. Este comando es
el paso donde una persona de verdad decide "sí, esto es C1 y es bueno",
antes de que quede fijado en el catálogo del que luego asigna la app
(sin IA — ver api.build_language_plan_draft).

Flujo:
    1. Busca candidatos con `search_courses` (o pega directamente una
       URL de playlist que ya conozcas y confíes).
    2. `python manage.py add_course_playlist francés B1 <url-o-id> --native-language español`
    3. El comando trae los vídeos reales (título, duración, subtítulos)
       y los enseña ANTES de guardar nada.
    4. Confirmas ("s") o cancelas ("n") — con --yes te saltas la
       pregunta, para cuando ya lo has revisado por tu cuenta.

Uso:
    python manage.py add_course_playlist francés B1 "https://www.youtube.com/playlist?list=PL..." --native-language español
    python manage.py add_course_playlist francés A1 PL_id_directo --notes "Muy clara, con subtítulos"

    Si la playlist cubre VARIOS niveles seguidos sin cortes (ej. un
    curso completo de A1 a B2 en una sola lista), añade --level-to con
    el nivel más alto que cubre:
    python manage.py add_course_playlist francés A1 "https://www.youtube.com/playlist?list=PL..." --level-to B2 --native-language inglés

--native-language: en qué idioma están las EXPLICACIONES del curso, no
el idioma que se aprende (eso es el primer argumento). Ej. un curso de
francés "para hispanohablantes" lleva --native-language español — así
solo se le ofrece a quien puso "español" como idioma que ya sabe (ver
Plan.known_languages / api._catalog_entries_for_language). Sin este
flag, la playlist queda NEUTRA (vale para cualquiera, ej. subtítulos
en el propio idioma que se aprende, sin explicaciones de por medio) —
no "para nadie".
"""
import re

from django.core.management.base import BaseCommand, CommandError

from tasks.models import CoursePlaylist, Plan
from tasks.youtube_search import (
    YouTubeSearchError, get_playlist_details, get_videos_details, list_playlist_items,
)

_PLAYLIST_ID_RE = re.compile(r"[?&]list=([A-Za-z0-9_-]+)")


def _fmt_duration(seconds):
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{s:02d}s"


def _extract_playlist_id(raw):
    raw = (raw or "").strip()
    m = _PLAYLIST_ID_RE.search(raw)
    return m.group(1) if m else raw


class Command(BaseCommand):
    help = "Añade una playlist verificada a mano al catálogo de cursos de idioma (CoursePlaylist)."

    def add_arguments(self, parser):
        parser.add_argument("language", help="Idioma, ej. 'francés' (igual que luego en Plan.language_name).")
        parser.add_argument("level", choices=Plan.CEFR_LEVELS, help="Nivel MCER real de esta playlist (el más bajo que cubre, si cubre varios).")
        parser.add_argument("playlist", help="URL completa de la playlist o su ID directamente.")
        parser.add_argument(
            "--level-to", choices=Plan.CEFR_LEVELS, default="",
            help="Si esta playlist cubre VARIOS niveles seguidos sin cortes, el nivel más alto "
                 "que cubre (ej. --level-to B2 con level=A1). En blanco = cubre solo `level`.",
        )
        parser.add_argument(
            "--native-language", default="",
            help="Idioma en el que se explica el curso (ej. 'español'). En blanco = neutro, "
                 "vale para cualquier hablante — ver docstring del módulo.",
        )
        parser.add_argument("--notes", default="", help="Por qué se eligió / qué cubre (opcional).")
        parser.add_argument(
            "--order", type=int, default=0,
            help="Orden dentro de su idioma+nivel+idioma nativo, si hay varias (menor = primera). 0 por defecto.",
        )
        parser.add_argument(
            "--yes", action="store_true",
            help="No preguntar confirmación — para cuando ya revisaste la playlist por tu cuenta.",
        )

    def handle(self, *args, **options):
        language = options["language"]
        level = options["level"]
        level_to = options["level_to"]
        playlist_id = _extract_playlist_id(options["playlist"])
        native_language = options["native_language"].strip()
        notes = options["notes"]
        order = options["order"]

        if level_to and Plan.CEFR_LEVELS.index(level_to) < Plan.CEFR_LEVELS.index(level):
            raise CommandError(f"--level-to ({level_to}) no puede ser más bajo que level ({level}).")

        if CoursePlaylist.objects.filter(youtube_playlist_id=playlist_id).exists():
            raise CommandError("Esta playlist ya está en el catálogo (comprueba con el admin o la shell).")

        try:
            playlist_info = get_playlist_details(playlist_id)
            if not playlist_info:
                raise CommandError("No se encontró esa playlist — revisa el enlace/ID (¿es pública?).")
            items = list_playlist_items(playlist_id, max_results=50)
            if not items:
                raise CommandError("Esa playlist no tiene vídeos — revisa el enlace/ID.")
            details = get_videos_details([it["video_id"] for it in items])
        except YouTubeSearchError as e:
            raise CommandError(str(e))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Playlist: \"{playlist_info['title']}\" — {playlist_info['channel_title']}"))
        self.stdout.write(self.style.SUCCESS(
            f"Vista previa real de la playlist ({len(items)} vídeo(s)):"
        ))
        for it in items:
            d = details.get(it["video_id"], {})
            caps = "✓ subtítulos" if d.get("has_captions") else "sin subtítulos"
            self.stdout.write(
                f"   {it['position'] + 1:>2}. {it['title'][:70]} "
                f"({_fmt_duration(d.get('duration_seconds'))}, {caps})"
            )

        self.stdout.write("")
        audiencia = f"para hablantes de {native_language}" if native_language else "neutra (para cualquiera)"
        nivel_label = f"{level} → {level_to}" if level_to and level_to != level else level
        self.stdout.write(f"Se va a guardar como: {language} · {nivel_label} · {audiencia} · playlist_id={playlist_id}")
        if level_to and level_to != level:
            self.stdout.write(self.style.WARNING(
                "Cubre VARIOS niveles seguidos — los vídeos se repartirán en tramos iguales entre "
                f"{level} y {level_to} (no hay forma de saber en qué vídeo exacto cambia de nivel)."
            ))

        if not options["yes"]:
            answer = input("\n¿Es de verdad de este idioma y nivel? Guardar en el catálogo [s/N]: ").strip().lower()
            if answer not in ("s", "si", "sí", "y", "yes"):
                self.stdout.write(self.style.WARNING("Cancelado — no se ha guardado nada."))
                return

        CoursePlaylist.objects.create(
            language=language,
            level=level,
            level_to=level_to,
            native_language=native_language,
            youtube_playlist_id=playlist_id,
            title=playlist_info["title"],
            channel_title=playlist_info["channel_title"],
            notes=notes,
            order=order,
        )
        self.stdout.write(self.style.SUCCESS(
            f"Guardado en el catálogo: {language} · {nivel_label} · {audiencia} · {playlist_id}"
        ))
