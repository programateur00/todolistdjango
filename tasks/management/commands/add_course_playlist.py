"""
Añade una playlist al catálogo curado de cursos de idioma
(CoursePlaylist) — a mano, con vista previa real, nunca a ciegas.

Por qué existe esto en vez de fiarse de `search_courses`: esa búsqueda
demostró que para niveles con poco contenido gratis (C1/C2 sobre todo)
YouTube devuelve "lo más parecido" en vez de admitir que no hay nada —
en la práctica, cursos de principiantes reetiquetados. Este comando es
el paso donde una persona de verdad decide "sí, esto es C1 y es bueno",
antes de que quede fijado en el catálogo del que luego elegirá la IA.

Flujo:
    1. Busca candidatos con `search_courses` (o pega directamente una
       URL de playlist que ya conozcas y confíes).
    2. `python manage.py add_course_playlist francés B1 <url-o-id>`
    3. El comando trae los vídeos reales (título, duración, subtítulos)
       y los enseña ANTES de guardar nada.
    4. Confirmas ("s") o cancelas ("n") — con --yes te saltas la
       pregunta, para cuando ya lo has revisado por tu cuenta.

Uso:
    python manage.py add_course_playlist francés B1 "https://www.youtube.com/playlist?list=PL..."
    python manage.py add_course_playlist francés A1 PL_id_directo --notes "Muy clara, con subtítulos"
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
        parser.add_argument("level", choices=Plan.CEFR_LEVELS, help="Nivel MCER real de esta playlist.")
        parser.add_argument("playlist", help="URL completa de la playlist o su ID directamente.")
        parser.add_argument("--notes", default="", help="Por qué se eligió / qué cubre (opcional).")
        parser.add_argument(
            "--yes", action="store_true",
            help="No preguntar confirmación — para cuando ya revisaste la playlist por tu cuenta.",
        )

    def handle(self, *args, **options):
        language = options["language"]
        level = options["level"]
        playlist_id = _extract_playlist_id(options["playlist"])
        notes = options["notes"]

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
        self.stdout.write(f"Se va a guardar como: {language} · {level} · playlist_id={playlist_id}")

        if not options["yes"]:
            answer = input("\n¿Es de verdad de este idioma y nivel? Guardar en el catálogo [s/N]: ").strip().lower()
            if answer not in ("s", "si", "sí", "y", "yes"):
                self.stdout.write(self.style.WARNING("Cancelado — no se ha guardado nada."))
                return

        CoursePlaylist.objects.create(
            language=language,
            level=level,
            youtube_playlist_id=playlist_id,
            title=playlist_info["title"],
            channel_title=playlist_info["channel_title"],
            notes=notes,
        )
        self.stdout.write(self.style.SUCCESS(f"Guardado en el catálogo: {language} · {level} · {playlist_id}"))
