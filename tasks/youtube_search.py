"""
Búsqueda real de cursos de idioma en YouTube (YouTube Data API v3).

Por qué existe esto: Gemini no puede navegar YouTube ni comprobar que un
vídeo existe de verdad — pedirle directamente "dame los vídeos de un
curso de francés de A1 a C2" produce IDs inventados que no cargan, o
que ni siquiera son de francés. Este módulo hace la parte que Gemini no
puede hacer: buscar playlists y vídeos REALES con la propia API de
YouTube. La curación (elegir y ordenar estos resultados con IA) es la
Fase 2 — aquí todavía no entra ningún LLM, a propósito, para poder
juzgar la calidad de los datos reales antes de construir nada encima.

Clave gratis, DISTINTA de GEMINI_API_KEY: se pide en Google Cloud
Console, no en AI Studio — ver el README, sección "Cursos de idiomas ·
YouTube". Sin YOUTUBE_API_KEY definida, todo esto falla con un error
legible en vez de reventar, igual que tasks/ai.py sin GEMINI_API_KEY.

Cuota: `search.list` cuesta 100 unidades por llamada; el resto de
llamadas de aquí (`playlistItems.list`, `videos.list`) cuestan 1. Con
la cuota gratis de 10.000 unidades/día, un barrido de los 6 niveles
MCER (6 búsquedas) cuesta ~600 unidades — de sobra para probar esto a
mano varias veces al día sin preocuparse.

Nota sobre subtítulos: `has_captions` viene de `contentDetails.caption`
(si YouTube dice que el vídeo TIENE subtítulos), no de si se pueden
descargar — eso es otra pelea aparte (ver la discusión sobre
`youtube-transcript-api` y sus bloqueos en el diseño de la Fase 3). Aquí
sirve solo como pista de calidad para elegir entre varios candidatos.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings


class YouTubeSearchError(Exception):
    """Error legible en español, pensado para enseñarse tal cual al usuario."""


YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
DEFAULT_TIMEOUT = 20

_ISO8601_DURATION_RE = re.compile(
    r"^PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
)


def _duration_to_seconds(iso_duration):
    """'PT15M33S' -> 933. Directos/formatos raros sin duración fija -> None."""
    if not iso_duration:
        return None
    m = _ISO8601_DURATION_RE.match(iso_duration)
    if not m:
        return None
    parts = m.groupdict()
    hours = int(parts["hours"] or 0)
    minutes = int(parts["minutes"] or 0)
    seconds = int(parts["seconds"] or 0)
    return hours * 3600 + minutes * 60 + seconds


def _api_key():
    key = getattr(settings, "YOUTUBE_API_KEY", "")
    if not key:
        raise YouTubeSearchError(
            "Falta configurar la búsqueda de cursos en el servidor: define la variable de "
            "entorno YOUTUBE_API_KEY (clave gratis en Google Cloud Console — ver el README, "
            "sección \"Cursos de idiomas · YouTube\")."
        )
    return key


def _get(endpoint, **params):
    params["key"] = _api_key()
    url = f"{YOUTUBE_API_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:300]
        if e.code == 403:
            raise YouTubeSearchError(
                "La clave de YouTube del servidor no es válida, no tiene la \"YouTube Data API "
                "v3\" activada en Google Cloud, o se agotó la cuota gratis de hoy. Revisa "
                f"YOUTUBE_API_KEY. Detalle: {detail}"
            ) from e
        if e.code == 400:
            raise YouTubeSearchError(f"Petición mal formada a la API de YouTube: {detail}") from e
        raise YouTubeSearchError(f"La API de YouTube respondió con un error ({e.code}): {detail}") from e
    except urllib.error.URLError as e:
        raise YouTubeSearchError(
            "No se pudo contactar con la API de YouTube. Comprueba la conexión e inténtalo de nuevo."
        ) from e
    except TimeoutError as e:
        raise YouTubeSearchError("La API de YouTube tardó demasiado en responder. Inténtalo de nuevo.") from e


def search_playlists(query, max_results=5, relevance_language=None):
    """
    Busca playlists públicas por texto libre. Cuesta 100 unidades de
    cuota por llamada — es la parte cara, así que quien llame a esto
    decide cuántas búsquedas hacer, no se repite "por si acaso".

    Devuelve una lista de dicts: playlist_id, title, channel_title,
    description.
    """
    params = dict(
        part="snippet", type="playlist", q=query, maxResults=max_results, safeSearch="strict",
    )
    if relevance_language:
        params["relevanceLanguage"] = relevance_language
    data = _get("search", **params)
    out = []
    for item in data.get("items", []):
        pid = (item.get("id") or {}).get("playlistId")
        if not pid:
            continue
        snippet = item.get("snippet", {})
        out.append({
            "playlist_id": pid,
            "title": snippet.get("title", ""),
            "channel_title": snippet.get("channelTitle", ""),
            "description": snippet.get("description", ""),
        })
    return out


def get_playlist_details(playlist_id):
    """
    Título y canal de la propia playlist (no de sus vídeos) — llamada
    barata (1 unidad), separada de `search_playlists` a propósito: esta
    no busca nada, solo mira una playlist que ya se conoce por su ID
    (ver el comando `add_course_playlist`, que nunca pasa por
    `search_playlists`). Devuelve None si el ID no existe o es privada.
    """
    data = _get("playlists", part="snippet", id=playlist_id)
    items = data.get("items", [])
    if not items:
        return None
    snippet = items[0].get("snippet", {})
    return {
        "title": snippet.get("title", ""),
        "channel_title": snippet.get("channelTitle", ""),
        "description": snippet.get("description", ""),
    }


def list_playlist_items(playlist_id, max_results=50):
    """
    Vídeos de una playlist, en orden. `max_results` tiene un tope de 50
    (límite por página de la API) — de sobra para lo que necesitamos
    (unas pocas semanas de curso por playlist).
    """
    data = _get(
        "playlistItems", part="snippet,contentDetails",
        playlistId=playlist_id, maxResults=min(max_results, 50),
    )
    out = []
    for item in data.get("items", []):
        video_id = (item.get("contentDetails") or {}).get("videoId")
        if not video_id:
            continue
        snippet = item.get("snippet", {})
        out.append({
            "video_id": video_id,
            "title": snippet.get("title", ""),
            "position": snippet.get("position", 0),
        })
    return out


def get_videos_details(video_ids):
    """
    Duración, subtítulos y si se puede incrustar, de hasta 50 vídeos a
    la vez (límite de IDs por llamada de la API — por eso se trocea).
    Devuelve {video_id: {...}}.
    """
    out = {}
    ids = [v for v in video_ids if v]
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        data = _get("videos", part="snippet,contentDetails,status", id=",".join(chunk))
        for item in data.get("items", []):
            vid = item.get("id")
            snippet = item.get("snippet", {})
            content = item.get("contentDetails", {})
            status = item.get("status", {})
            out[vid] = {
                "title": snippet.get("title", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "description": snippet.get("description", ""),
                "duration_seconds": _duration_to_seconds(content.get("duration")),
                "has_captions": content.get("caption") == "true",
                "embeddable": status.get("embeddable", True),
            }
    return out


def find_language_course_candidates(
    language, levels=None, max_playlists_per_level=3, max_videos_per_playlist=15,
):
    """
    Orquesta las tres llamadas de arriba para un idioma y una lista de
    niveles MCER: por cada nivel, busca playlists, mira sus vídeos y
    trae duración/subtítulos de cada uno.

    NO decide nada (ni orden, ni qué playlist es mejor de verdad) — eso
    es curación, y la hace la IA en la Fase 2 sobre estos datos reales.
    Esto solo responde "qué hay de verdad", que es lo que hace falta
    para juzgar si un nivel como C2 tiene contenido gratis suficiente
    antes de prometerle al usuario un temario completo.

    Devuelve {nivel: [{playlist_id, playlist_title, channel_title,
    videos: [{video_id, title, duration_seconds, has_captions}]}]}.
    """
    from .models import Plan  # import diferido: evita un ciclo de imports con models.py

    levels = levels or Plan.CEFR_LEVELS
    results = {}
    for level in levels:
        query = f"curso de {language} {level} gratis completo"
        playlists = search_playlists(query, max_results=max_playlists_per_level)
        level_out = []
        for pl in playlists:
            items = list_playlist_items(pl["playlist_id"], max_results=max_videos_per_playlist)
            details = get_videos_details([it["video_id"] for it in items])
            videos = []
            for it in items:
                d = details.get(it["video_id"], {})
                if d and d.get("embeddable") is False:
                    continue  # no se podría incrustar en la tarea — descartado directamente
                videos.append({
                    "video_id": it["video_id"],
                    "title": d.get("title") or it["title"],
                    "duration_seconds": d.get("duration_seconds"),
                    "has_captions": d.get("has_captions", False),
                })
            level_out.append({
                "playlist_id": pl["playlist_id"],
                "playlist_title": pl["title"],
                "channel_title": pl["channel_title"],
                "videos": videos,
            })
        results[level] = level_out
    return results
