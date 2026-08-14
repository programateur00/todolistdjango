"""
Herramienta de DESCUBRIMIENTO de cursos de idioma en YouTube — no de
decisión automática. Enseña qué playlists devuelve YouTube para un
idioma/nivel, para que una persona elija cuáles son de verdad buenas y
las añada a mano al catálogo con `add_course_playlist`.

Por qué no se fía de esto ningún otro paso: en la práctica (probado con
francés) la búsqueda de YouTube no entiende "C1"/"C2" como nivel MCER —
cuando no hay contenido real de un nivel, en vez de admitir que no
encontró nada, devuelve lo más parecido por relevancia genérica. Este
comando ahora detecta y avisa cuando la MISMA playlist aparece en varios
niveles pedidos — la señal más clara de que no es contenido específico
de ninguno de ellos, solo relleno.

Uso:
    python manage.py search_courses francés
    python manage.py search_courses francés --levels A1 A2 B1
    python manage.py search_courses italiano --max-playlists 5

Después, para lo que de verdad valga la pena:
    python manage.py add_course_playlist francés B1 "<url de la playlist buena>"
"""
from django.core.management.base import BaseCommand, CommandError

from tasks.models import Plan
from tasks.youtube_search import YouTubeSearchError, find_language_course_candidates


def _fmt_duration(seconds):
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{s:02d}s"


class Command(BaseCommand):
    help = (
        "Descubre candidatos de curso de idioma en YouTube por nivel MCER — para revisar a mano "
        "y añadir los buenos con add_course_playlist. No guarda nada por sí solo."
    )

    def add_arguments(self, parser):
        parser.add_argument("language", help="Idioma a buscar, ej. 'francés'.")
        parser.add_argument(
            "--levels", nargs="+", default=Plan.CEFR_LEVELS, choices=Plan.CEFR_LEVELS,
            help="Niveles MCER a comprobar (por defecto los 6).",
        )
        parser.add_argument(
            "--max-playlists", type=int, default=3,
            help="Playlists a inspeccionar por nivel. Ojo: cada nivel gasta 100 unidades de "
                 "cuota solo en la búsqueda, independientemente de este número.",
        )

    def handle(self, *args, **options):
        language = options["language"]
        levels = options["levels"]
        max_playlists = options["max_playlists"]

        try:
            results = find_language_course_candidates(
                language, levels=levels, max_playlists_per_level=max_playlists,
            )
        except YouTubeSearchError as e:
            raise CommandError(str(e))

        # Cuántos de los niveles pedidos devolvió cada playlist — si una
        # misma playlist aparece en 2+ niveles, no es contenido propio de
        # NINGUNO de ellos, es YouTube rellenando con lo más parecido.
        levels_by_playlist = {}
        for level in levels:
            for p in results.get(level, []):
                levels_by_playlist.setdefault(p["playlist_id"], set()).add(level)

        suspect_levels = set()
        for level in levels:
            playlists = results.get(level, [])
            total_videos = sum(len(p["videos"]) for p in playlists)
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(
                f"== Nivel {level} — {len(playlists)} playlist(s), {total_videos} vídeo(s) en total =="
            ))
            if not playlists:
                self.stdout.write("   (nada encontrado)")
            for p in playlists:
                caps = sum(1 for v in p["videos"] if v["has_captions"])
                seen_in = levels_by_playlist.get(p["playlist_id"], set())
                flag = ""
                if len(seen_in) > 1:
                    flag = f"  ⚠ TAMBIÉN sale en {', '.join(sorted(seen_in - {level}))} — probablemente NO es de {level}"
                    suspect_levels.add(level)
                self.stdout.write(
                    f"   · \"{p['playlist_title']}\" — {p['channel_title']} "
                    f"({len(p['videos'])} vídeo(s), {caps} con subtítulos){flag}"
                )
                for v in p["videos"][:5]:
                    self.stdout.write(f"       - {v['title'][:70]} ({_fmt_duration(v['duration_seconds'])})")
                if len(p["videos"]) > 5:
                    self.stdout.write(f"       … y {len(p['videos']) - 5} más")
            if total_videos == 0:
                suspect_levels.add(level)

        self.stdout.write("")
        if suspect_levels:
            self.stdout.write(self.style.WARNING(
                f"Niveles sin contenido de fiar (nada encontrado, o solo playlists repetidas de "
                f"otros niveles): {', '.join(sorted(suspect_levels))}. No añadas nada de estos al "
                "catálogo sin comprobarlo tú mismo/a viendo el vídeo — probablemente no hay curso "
                f"gratis de {language} de verdad en ese nivel todavía."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "Ningún nivel pedido tiene la señal de \"relleno\" (playlist repetida entre "
                "niveles) — pero sigue revisando a mano antes de añadir nada al catálogo."
            ))
