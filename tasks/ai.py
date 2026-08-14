"""
Generación de planes con IA (Google Gemini).

Por qué Gemini: es el único de los grandes que ofrece un tier
permanentemente gratis (sin tarjeta, sin caducidad de prueba) con
"structured output" — le pides un JSON con un esquema exacto y te lo
devuelve validado contra ese esquema, en vez de tener que rezar para que
el texto libre se deje parsear. Se pide la clave gratis en
https://aistudio.google.com/apikey y se guarda en la variable de entorno
GEMINI_API_KEY (ver settings.py) — sin ella, esta función falla con un
error legible en vez de reventar.

Diseño: la IA NO decide los ajustes "de fontanería" del plan (semanas,
qué días se entrena, tipo de plan) — esos los pone el usuario en el
formulario, como en la creación manual. La IA solo decide el NOMBRE, las
notas, y — para Deporte y Estudio — qué objetivos concretos persigue y su
progresión (punto de partida, destino, y en cuántas semanas quiere
llegar). El "en cuántas semanas" se traduce aquí a `sessions_per_step` y
al incremento por escalón con la misma cuenta que ya usa la calculadora
del formulario web/app (ver plan_item_form.html) — no se le pide a la IA
que haga esa aritmética, que es donde un LLM más se equivoca.

Nada de esto llega a la base de datos directamente: `api.plan_generate`
aplica el resultado sobre instancias de Plan/PlanItem SIN GUARDAR,
reutilizando `_apply_plan_fields` / `_apply_plan_item_fields` (las mismas
que usa la creación manual), así que un plan generado por IA pasa por
exactamente la misma validación y los mismos límites que uno hecho a
mano. El usuario revisa y confirma antes de que se guarde nada de verdad.
"""
import json
import urllib.error
import urllib.request

from django.conf import settings

from .models import CoursePlaylist, Exercise, Plan, PlanItem
from .youtube_search import YouTubeSearchError, get_playlists_details


class PlanAIError(Exception):
    """Error legible en español, pensado para enseñarse tal cual al usuario."""


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

MAX_PROMPT_CHARS = 800
DEFAULT_TIMEOUT = 30


# --------------------------------------------------------------- prompt

def _exercise_catalog_lines():
    lines = []
    for e in Exercise.objects.filter(is_active=True).order_by("order", "name"):
        if e.mode == Exercise.MODE_DISTANCE:
            medida = "se mide en distancia (km) y ritmo (min/km) — SIEMPRE progresión 'distance'"
        elif e.mode == Exercise.MODE_TIMED:
            medida = "se mide en SEGUNDOS aguantados (start_seconds/goal_seconds), no en repeticiones"
        else:
            medida = "se mide en REPETICIONES (start_reps/goal_reps)"
        area = {"upper_body": "tren superior", "lower_body": "tren inferior/core", "running": "cardio"}.get(
            e.body_area, e.body_area or "general"
        )
        lines.append(f"- slug=\"{e.slug}\" · {e.name} · {area} · {medida}")
    return "\n".join(lines)


_PLAN_TYPE_BRIEF = {
    "sport": (
        "Deporte: el plan persigue de 3 a 6 objetivos de ejercicio del catálogo de abajo — un "
        "plan de un solo ejercicio no es un programa de entrenamiento serio. Exactamente UNO "
        "debe llevar is_headline=true (la medida que define si el plan se ha conseguido, ej. "
        "\"llegar a 4x12 dominadas con 20 kg\"); el resto son apoyo (progresan pero no deciden). "
        "Elige ejercicios que de verdad ayuden al objetivo del usuario y cubran su cuerpo de "
        "forma equilibrada — no metas relleno ni variantes redundantes del mismo movimiento."
    ),
    "study": (
        "Estudio: el plan persigue UN solo hábito diario (estudiar francés, leer, practicar "
        "piano...). No hay ejercicios del catálogo — solo un nombre corto para ese hábito y, si "
        "el usuario dio una duración, unos minutos objetivo por sesión."
    ),
    "general": (
        "General: un hábito simple de cumplir o no cumplir cada día (ej. \"no fumar\", \"meditar\"). "
        "No lleva objetivos — la propia tarea diaria ES el objetivo. Devuelve items como lista vacía."
    ),
}


def _build_prompt(user_prompt, plan_type, weeks, sessions_per_week):
    catalog = _exercise_catalog_lines()
    brief = _PLAN_TYPE_BRIEF.get(plan_type, _PLAN_TYPE_BRIEF["sport"])
    parts = [
        "Eres el mejor entrenador personal/coach posible, diseñando planes de progresión "
        "dentro de la app de tareas \"Strive\" para un cliente real. Programas como lo haría "
        "un profesional de verdad: sobrecarga progresiva de manual (series Y repeticiones "
        "suben con el tiempo, no solo repeticiones sin techo hasta el infinito), variedad real "
        "de patrones de movimiento, y objetivos que de verdad llevan al cliente a su meta — "
        "nada de rellenar con lo primero que se te ocurra. El usuario ya ha decidido: el TIPO "
        "de plan, cuántas SEMANAS va a durar, y CUÁNTOS DÍAS a la semana entrena "
        f"({sessions_per_week} días/semana). Tu trabajo es traducir su objetivo en un plan "
        "concreto y medible — nada de vaguedades.",
        "",
        f"Tipo de plan: {brief}",
        "",
        f"Duración: {weeks} semanas.",
        "",
        f"Lo que pide el usuario, en sus palabras:\n\"{user_prompt}\"",
    ]
    if plan_type == "sport":
        parts += [
            "",
            "Catálogo de ejercicios disponibles (usa SOLO estos slugs, no inventes otros):",
            catalog,
            "",
            "Reglas de progresión:",
            "- 'reps' (o 'seconds' si el ejercicio se mide en segundos): sube hasta un techo y se "
            "queda ahí. Para abdominales, plancha, resistencia.",
            "- 'double': sube repeticiones dentro de un rango y, al llegar arriba, añade peso y "
            "vuelve abajo. SOLO para ejercicios de fuerza medidos en repeticiones (dominadas, "
            "fondos, sentadillas) — nunca para uno medido en segundos.",
            "- 'completion': objetivo fijo, no sube. Para hábitos sin progresión numérica.",
            "- El ejercicio de correr ('running') no elige progresión: siempre es 'distance', con "
            "distancia en km y ritmo en segundos/km (más bajo = más rápido).",
            "",
            "Sobrecarga progresiva DE VERDAD — esto es lo que distingue a un buen entrenador de uno "
            "vago: en 'reps' y 'double', start_sets y goal_sets TAMBIÉN tienen que subir con las "
            "semanas, no solo las repeticiones o el peso. Empieza conservador (2-3 series, algo que "
            "el cliente pueda cumplir desde el primer día) y sube hacia 3-5 según el nivel de partida "
            "y las semanas disponibles. goal_sets nunca debe quedarse igual que start_sets salvo que "
            "el usuario pida explícitamente mantener el volumen fijo — una progresión que solo mueve "
            "las repeticiones para siempre no es realista (nadie llega a 40 dominadas seguidas).",
            "- 'weeks_to_goal' es en cuántas semanas quiere llegar al destino desde el punto de "
            "partida — sé realista (una progresión de fuerza razonable sube poco a poco).",
            "- Los puntos de partida deben ser alcanzables desde el primer día para alguien que "
            "empieza el plan ahora — mejor quedarse corto que proponer algo imposible.",
            "",
            "Cobertura de ejercicios — elige entre 3 y 6 ejercicios DISTINTOS, nunca uno o dos "
            "sueltos: un programa serio trabaja el cuerpo de forma equilibrada, no un solo "
            "movimiento. Si el objetivo es general (\"ponerme en forma\"), reparte entre empuje "
            "(fondos), tracción (dominadas), pierna (sentadillas) y core (plancha/abdominales) — un "
            "cuerpo completo, no 2-3 ejercicios sueltos. Si el objetivo es específico de una zona "
            "(ej. \"tren superior\"), cúbrela igualmente con 3-4 movimientos distintos de esa zona, "
            "no uno solo. NO metas varias variantes del mismo movimiento a la vez (ej. nunca "
            "dominadas + dominadas anchas + chin ups juntas en el mismo plan) salvo que el usuario "
            "pida explícitamente trabajar variantes — eso es relleno, no variedad real. Y running "
            "solo si el objetivo del usuario tiene algo que ver con correr o resistencia cardio.",
        ]

    return "\n".join(parts)


# --------------------------------------------------------------- schema

_ITEM_SPORT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "exercise_slug": {"type": "STRING", "description": "Slug exacto del catálogo."},
        "label": {"type": "STRING", "description": "Nombre corto opcional; vacío para usar el del ejercicio."},
        "is_headline": {"type": "BOOLEAN"},
        "progression": {"type": "STRING", "enum": ["reps", "double", "completion"]},
        "start_sets": {"type": "INTEGER"},
        "goal_sets": {"type": "INTEGER", "description": "Series al llegar al destino. Debe ser mayor que start_sets salvo que el volumen se mantenga fijo a propósito."},
        "start_reps": {"type": "INTEGER"},
        "start_seconds": {"type": "INTEGER"},
        "start_weight_kg": {"type": "NUMBER"},
        "goal_reps": {"type": "INTEGER"},
        "goal_seconds": {"type": "INTEGER"},
        "goal_weight_kg": {"type": "NUMBER"},
        "start_distance_km": {"type": "NUMBER"},
        "start_pace_seconds_per_km": {"type": "INTEGER"},
        "goal_distance_km": {"type": "NUMBER"},
        "goal_pace_seconds_per_km": {"type": "INTEGER"},
        "weeks_to_goal": {"type": "INTEGER"},
        "sessions_per_step": {"type": "INTEGER"},
    },
    "required": [
        "exercise_slug", "is_headline", "progression",
        "start_sets", "goal_sets", "start_reps", "start_seconds", "start_weight_kg",
        "goal_reps", "goal_seconds", "goal_weight_kg",
        "start_distance_km", "start_pace_seconds_per_km",
        "goal_distance_km", "goal_pace_seconds_per_km",
        "weeks_to_goal", "sessions_per_step",
    ],
}

_ITEM_STUDY_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "label": {"type": "STRING"},
        "target_minutes": {"type": "INTEGER", "description": "0 si no aplica un objetivo en minutos."},
    },
    "required": ["label", "target_minutes"],
}


def _response_schema(plan_type):
    plan_schema = {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING", "description": "Título general del plan, corto. Ej: \"Ponerme en forma\"."},
            "notes": {"type": "STRING", "description": "1-2 frases de contexto/ánimo sobre el plan."},
        },
        "required": ["name", "notes"],
    }
    if plan_type == "sport":
        items_schema = {"type": "ARRAY", "items": _ITEM_SPORT_SCHEMA, "minItems": 3, "maxItems": 6}
    elif plan_type == "study":
        items_schema = {"type": "ARRAY", "items": _ITEM_STUDY_SCHEMA, "minItems": 1, "maxItems": 1}
    else:
        items_schema = {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {}}, "maxItems": 0}

    return {
        "type": "OBJECT",
        "properties": {"plan": plan_schema, "items": items_schema},
        "required": ["plan", "items"],
    }


# ----------------------------------------------------------------- API

def _call_gemini(prompt_text, schema):
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        raise PlanAIError(
            "Falta configurar la IA en el servidor: define la variable de entorno "
            "GEMINI_API_KEY (clave gratis en aistudio.google.com/apikey)."
        )
    model = getattr(settings, "GEMINI_MODEL", "") or "gemini-3-flash-preview"

    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema,
            "temperature": 0.7,
        },
    }
    req = urllib.request.Request(
        GEMINI_URL.format(model=model, key=api_key),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:300]
        if e.code in (401, 403):
            raise PlanAIError("La clave de IA del servidor no es válida. Revisa GEMINI_API_KEY.") from e
        if e.code == 429:
            raise PlanAIError("Se ha agotado la cuota gratis de la IA por ahora. Prueba de nuevo en un rato.") from e
        if e.code == 404 and "no longer available" in detail.lower():
            raise PlanAIError(
                f"El modelo de IA configurado ({model}) ya no está disponible — Google cambia estos "
                "nombres de vez en cuando. Actualiza GEMINI_MODEL en el servidor a un modelo vigente "
                "(mira la lista de modelos gratis en ai.google.dev/gemini-api/docs/pricing)."
            ) from e
        raise PlanAIError(f"El servicio de IA respondió con un error ({e.code}): {detail}") from e
    except urllib.error.URLError as e:
        raise PlanAIError("No se pudo contactar con el servicio de IA. Comprueba la conexión e inténtalo de nuevo.") from e
    except TimeoutError as e:
        raise PlanAIError("El servicio de IA tardó demasiado en responder. Inténtalo de nuevo.") from e

    try:
        text = raw["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise PlanAIError("La IA devolvió algo que no se pudo interpretar. Prueba a generar de nuevo.") from e


def generate_plan_draft(*, prompt, plan_type, weeks, sessions_per_week):
    """
    Llama a Gemini y devuelve el dict crudo `{"plan": {...}, "items": [...]}`
    tal como lo mandó la IA — sin aplicar todavía sobre el modelo. La
    validación/clamping de verdad la hace `api.plan_generate` reutilizando
    `_apply_plan_fields` / `_apply_plan_item_fields`.
    """
    user_prompt = (prompt or "").strip()[:MAX_PROMPT_CHARS]
    if not user_prompt:
        raise PlanAIError("Cuéntame qué quieres conseguir con este plan.")

    prompt_text = _build_prompt(user_prompt, plan_type, weeks, sessions_per_week)
    schema = _response_schema(plan_type)
    draft = _call_gemini(prompt_text, schema)
    if not isinstance(draft, dict) or "plan" not in draft:
        raise PlanAIError("La IA devolvió un plan con un formato inesperado. Prueba a generar de nuevo.")
    return draft


# ------------------------------------------------------- ritmo → escalón

def _steps_for_weeks(weeks_to_goal, sessions_per_week, sessions_per_step):
    """Misma cuenta que `escalones()` en plan_item_form.html."""
    total_sessions = max(1, weeks_to_goal) * max(1, sessions_per_week)
    return max(1, round(total_sessions / max(1, sessions_per_step)))


def _sanitize_sets(item_fields):
    """
    Red de seguridad: fuerza que las series también progresen (no solo
    reps/peso), incluso si la IA no ha seguido la instrucción del prompt.
    Un entrenador de verdad sube series poco a poco (2-3 -> 3-5), nunca
    las deja fijas para siempre ni las dispara a un número absurdo.
    """
    try:
        start_sets = max(1, int(item_fields.get("start_sets") or 3))
    except (TypeError, ValueError):
        start_sets = 3
    try:
        goal_sets = int(item_fields.get("goal_sets") or 0)
    except (TypeError, ValueError):
        goal_sets = 0
    if goal_sets <= start_sets:
        goal_sets = start_sets + 1          # progresión mínima garantizada
    goal_sets = min(goal_sets, start_sets + 3, 6)   # nunca una barbaridad
    item_fields["start_sets"] = start_sets
    item_fields["goal_sets"] = goal_sets


def apply_pacing(item_fields, *, exercise, sessions_per_week):
    """
    Traduce `weeks_to_goal` (lo que decidió la IA) a `reps_increment` /
    `weight_increment_kg` / `distance_increment_km` / `pace_decrement_seconds`
    (lo que de verdad entiende PlanItem), con la misma fórmula que la
    calculadora del formulario. También sanea combinaciones que la IA
    podría proponer mal (progresión 'double' en un ejercicio cronometrado,
    progresión que no sea 'distance' en running).

    Muta y devuelve `item_fields` (el dict que luego se pasa tal cual a
    `_apply_plan_item_fields`).
    """
    is_running = bool(exercise and exercise.mode == Exercise.MODE_DISTANCE)
    is_timed = bool(exercise and exercise.mode == Exercise.MODE_TIMED)

    sessions_per_step = max(1, int(item_fields.get("sessions_per_step") or 2))
    weeks_to_goal = max(1, int(item_fields.get("weeks_to_goal") or 1))
    item_fields["sessions_per_step"] = sessions_per_step

    if is_running:
        item_fields["progression"] = PlanItem.PROG_DISTANCE
        steps = _steps_for_weeks(weeks_to_goal, sessions_per_week, sessions_per_step)
        d_dist = float(item_fields.get("goal_distance_km") or 0) - float(item_fields.get("start_distance_km") or 0)
        d_pace = int(item_fields.get("start_pace_seconds_per_km") or 0) - int(item_fields.get("goal_pace_seconds_per_km") or 0)
        item_fields["distance_increment_km"] = round(max(0.1, d_dist / steps), 2) if d_dist > 0 else 0.5
        item_fields["pace_decrement_seconds"] = max(1, round(d_pace / steps)) if d_pace > 0 else 10
        return item_fields

    prog = item_fields.get("progression") or PlanItem.PROG_REPS
    if is_timed and prog == PlanItem.PROG_DOUBLE:
        prog = PlanItem.PROG_REPS  # 'double' no tiene sentido en algo cronometrado
    item_fields["progression"] = prog

    if prog == PlanItem.PROG_COMPLETION:
        return item_fields

    _sanitize_sets(item_fields)
    steps = _steps_for_weeks(weeks_to_goal, sessions_per_week, sessions_per_step)

    if prog == PlanItem.PROG_DOUBLE:
        low = int(item_fields.get("rep_range_low") or 6)
        top = int(item_fields.get("goal_reps") or (low + 6))
        span = max(1, top - low + 1)
        cycles = max(1, round(steps / span))
        d_weight = float(item_fields.get("goal_weight_kg") or 0) - float(item_fields.get("start_weight_kg") or 0)
        item_fields["weight_increment_kg"] = round(max(0.5, d_weight / cycles), 1) if d_weight > 0 else 2.5
        item_fields["rep_range_low"] = low
        item_fields["goal_reps"] = top
        return item_fields

    # PROG_REPS
    start_key, goal_key = ("start_seconds", "goal_seconds") if is_timed else ("start_reps", "goal_reps")
    delta = int(item_fields.get(goal_key) or 0) - int(item_fields.get(start_key) or 0)
    item_fields["reps_increment"] = max(1, round(delta / steps)) if delta > 0 else 1
    return item_fields


# ============================================================ IDIOMAS
#
# Diseño distinto a Deporte/Estudio a propósito: para ejercicios, el
# catálogo (Exercise) es fijo y pequeño, así que se le pasa entero a la
# IA. Para idiomas, el catálogo (CoursePlaylist) lo cura una persona a
# mano, playlist a playlist — la búsqueda automática de YouTube
# demostró (ver tasks/youtube_search.py) que no se puede confiar en
# ella para decidir qué es de verdad un nivel u otro. Así que aquí la
# IA elige y ORDENA entre cursos YA VERIFICADOS, nunca busca ni
# inventa ninguno — mismo espíritu que con los ejercicios, un peldaño
# más estricto porque el coste de equivocarse (un vídeo del nivel
# equivocado, o que no existe) es peor que una repetición mal contada.
#
# El reparto de semanas entre los cursos elegidos es aritmética pura
# (`_allocate_weeks`), no se le pide a la IA — mismo motivo que
# `apply_pacing` para Deporte.

def _levels_in_range(level_from, level_to):
    """
    ['A1', 'A2', ...] entre level_from y level_to (incluidos). En
    blanco, level_from se trata como el nivel más bajo (A1) y level_to
    como el más alto (C2) — "sin techo" documentado en el propio campo
    del modelo.
    """
    levels = Plan.CEFR_LEVELS
    start = levels.index(level_from) if level_from in levels else 0
    end = levels.index(level_to) if level_to in levels else len(levels) - 1
    if end < start:
        start, end = end, start
    return levels[start:end + 1]


def _catalog_entries_for_language(language, level_from, level_to):
    """
    Playlists curadas (CoursePlaylist) para este idioma y rango de
    nivel, con su nº de vídeos REAL a día de hoy (llamada barata a la
    API de YouTube — playlists.list, 1 unidad — nunca una búsqueda
    nueva; una playlist puede haber cambiado desde que se curó, o
    haberse borrado).

    Devuelve (entries, missing_levels, levels, stale):
      - entries: lista de dicts con una `ref` corta y estable
        (ej. "cat_7") que es lo ÚNICO que se le enseña a la IA — así no
        hay forma de que invente un ID de playlist que no exista, solo
        puede elegir de aquí.
      - missing_levels: niveles del rango pedido sin NINGUNA playlist
        curada todavía (o cuya única playlist curada resultó borrada/
        privada desde entonces).
      - levels: el rango completo pedido, para los mensajes de error.
      - stale: las CoursePlaylist que ya no se pudieron confirmar
        (para poder avisar a quien mantiene el catálogo).
    """
    levels = _levels_in_range(level_from, level_to)
    qs = CoursePlaylist.objects.filter(
        language__iexact=language, level__in=levels, is_active=True,
    ).order_by("level", "order")

    entries, stale = [], []
    if qs.exists():
        try:
            details = get_playlists_details([c.youtube_playlist_id for c in qs])
        except YouTubeSearchError as e:
            # Traducido a PlanAIError: quien llama a esto (build_language_plan_draft)
            # solo espera fallos de tipo PlanAIError, igual que con Gemini.
            raise PlanAIError(str(e)) from e
        for c in qs:
            d = details.get(c.youtube_playlist_id)
            if not d or not d.get("is_public") or not d.get("item_count"):
                stale.append(c)
                continue
            entries.append({
                "ref": f"cat_{c.pk}",
                "catalog_id": c.pk,
                "level": c.level,
                "title": d.get("title") or c.title,
                "channel_title": d.get("channel_title") or c.channel_title,
                "item_count": d["item_count"],
                "youtube_playlist_id": c.youtube_playlist_id,
            })

    covered = {e["level"] for e in entries}
    missing_levels = [lvl for lvl in levels if lvl not in covered]
    return entries, missing_levels, levels, stale


def _build_language_prompt(*, prompt, language, levels, weeks, sessions_per_week, known_languages, entries, missing_levels):
    catalog_lines = [
        f"- {e['ref']} · nivel {e['level']} · \"{e['title']}\" — canal {e['channel_title']} "
        f"({e['item_count']} vídeos)"
        for e in entries
    ]
    parts = [
        "Eres el mejor diseñador de currículos de idiomas posible, dentro de la app de tareas "
        "\"Strive\", para un estudiante real que va a ver estos vídeos de verdad, día a día. Va "
        f"a estudiar {language}, en un plan de {weeks} semanas a {sessions_per_week} "
        "sesiones por semana — eso ya lo decidió el usuario, no lo toques.",
        "",
        f"Niveles MCER a cubrir, de más bajo a más alto: {', '.join(levels)}.",
    ]
    if known_languages:
        parts.append(
            f"Idiomas que el estudiante ya domina (dale color a tus notas con esto si ayuda de "
            f"verdad — comparar gramática o vocabulario parecido — pero NO cambia qué cursos "
            f"eliges): {known_languages}."
        )
    if prompt:
        parts.append(f"Contexto adicional del estudiante, en sus palabras: \"{prompt}\"")
    parts += [
        "",
        "Catálogo de cursos YA VERIFICADOS por una persona (usa SOLO estas referencias exactas, "
        "nunca inventes otra, ni un ID de YouTube, ni un nivel que no esté en esta lista):",
        "\n".join(catalog_lines) if catalog_lines else "(ninguno disponible para estos niveles)",
    ]
    if missing_levels:
        parts += [
            "",
            f"AVISO: no hay ningún curso verificado todavía para: {', '.join(missing_levels)}. "
            "No los inventes ni fuerces algo del catálogo para rellenar ese hueco — sáltatelos "
            "sin más. Menciónalo en tus notas de forma natural y honesta, como haría un profesor "
            "real que no tiene material para esa parte todavía.",
        ]
    parts += [
        "",
        "Tu trabajo: elige, de la lista de arriba, qué cursos usar y en qué ORDEN (normalmente "
        "de nivel más bajo a más alto). Si para un mismo nivel hay más de una opción, elige la "
        "que te parezca más completa o mejor explicada por el título y el canal — no hace falta "
        "usar todas las opciones de un nivel si una ya es suficiente. NO hagas ningún cálculo de "
        "semanas ni de ritmo — eso lo hace la app; tu única decisión es la selección y el orden.",
        "",
        "Escribe también un nombre corto para el plan y 1-2 frases de notas — con ánimo, algo de "
        "contexto sobre el camino que le espera, y mencionando los niveles que falten en el "
        "catálogo si los hay, para que no se lleve una sorpresa a mitad de curso.",
    ]
    return "\n".join(parts)


_LANGUAGE_ITEM_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "ref": {"type": "STRING", "description": "Referencia EXACTA del catálogo, ej. 'cat_7'. Nunca inventada."},
    },
    "required": ["ref"],
}


def _language_response_schema():
    return {
        "type": "OBJECT",
        "properties": {
            "plan": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING", "description": "Título corto, ej. \"Francés desde cero\"."},
                    "notes": {"type": "STRING"},
                },
                "required": ["name", "notes"],
            },
            "selected": {
                "type": "ARRAY", "items": _LANGUAGE_ITEM_SCHEMA, "minItems": 1,
                "description": "En el orden en que se deben estudiar.",
            },
        },
        "required": ["plan", "selected"],
    }


def _allocate_weeks(item_counts, weeks):
    """
    Reparte `weeks` entre los cursos elegidos, a ojo proporcional a
    cuántos vídeos tiene cada uno. PURAMENTE INFORMATIVO — solo decide
    la etiqueta "semana X" que se enseña en el temario
    (CourseModule.scheduled_week); el avance real es por sesiones
    CUMPLIDAS (ver Plan._language_completed_count), así que un reparto
    algo torcido por redondeo aquí no rompe nada.
    """
    n = len(item_counts)
    if n == 0:
        return []
    weeks = max(weeks, n)  # al menos 1 semana "propia" por curso elegido
    total_items = sum(item_counts) or n
    allocated = [max(1, round(weeks * c / total_items)) for c in item_counts]
    diff = weeks - sum(allocated)
    while diff != 0:
        idx = allocated.index(max(allocated)) if diff < 0 else allocated.index(min(allocated))
        if diff < 0 and allocated[idx] <= 1:
            break  # nunca por debajo de 1 semana propia
        allocated[idx] += 1 if diff > 0 else -1
        diff += -1 if diff > 0 else 1
    return allocated


def generate_language_plan_draft(*, prompt, language, level_from, level_to, weeks, sessions_per_week, known_languages):
    """
    Curación con IA de un plan de Estudio · Idiomas: la IA elige y
    ordena entre las playlists YA CURADAS a mano (CoursePlaylist) para
    este idioma — nunca busca ni inventa nada nuevo. Igual que
    `generate_plan_draft`, no guarda nada: `api.build_language_plan_draft`
    convierte esto en Plan/CourseModule sin guardar todavía, para que
    el usuario lo revise y confirme.
    """
    language = (language or "").strip()[:40]
    if not language:
        raise PlanAIError("Falta decir qué idioma quieres aprender.")

    entries, missing_levels, levels, stale = _catalog_entries_for_language(language, level_from, level_to)
    if not entries:
        niveles = ", ".join(levels) if levels else "los niveles pedidos"
        raise PlanAIError(
            f"No hay ningún curso de {language} verificado en el catálogo para {niveles} "
            f"todavía. Añade alguno primero con: python manage.py add_course_playlist "
            f"{language} {levels[0] if levels else 'A1'} \"<url de la playlist>\"."
        )

    user_prompt = (prompt or "").strip()[:MAX_PROMPT_CHARS]
    prompt_text = _build_language_prompt(
        prompt=user_prompt, language=language, levels=levels, weeks=weeks,
        sessions_per_week=sessions_per_week, known_languages=(known_languages or "").strip()[:200],
        entries=entries, missing_levels=missing_levels,
    )
    raw = _call_gemini(prompt_text, _language_response_schema())
    if not isinstance(raw, dict) or "selected" not in raw:
        raise PlanAIError("La IA devolvió un plan con un formato inesperado. Prueba a generar de nuevo.")

    by_ref = {e["ref"]: e for e in entries}
    seen, chosen = set(), []
    for raw_item in (raw.get("selected") or []):
        if not isinstance(raw_item, dict):
            continue
        ref = raw_item.get("ref")
        if ref not in by_ref or ref in seen:
            continue  # referencia inventada o repetida — se descarta, nunca se inventa nada
        seen.add(ref)
        chosen.append(by_ref[ref])

    if not chosen:
        raise PlanAIError("La IA no eligió ningún curso válido del catálogo. Prueba a generar de nuevo.")

    weeks_allocated = _allocate_weeks([c["item_count"] for c in chosen], weeks)
    selected_out = [{**entry, "weeks_allocated": wk} for entry, wk in zip(chosen, weeks_allocated)]

    plan_raw = raw.get("plan") or {}
    return {
        "plan": {
            "name": (plan_raw.get("name") or f"Aprender {language}").strip()[:80],
            "notes": (plan_raw.get("notes") or "").strip(),
        },
        "selected": selected_out,
        "missing_levels": missing_levels,
        "stale_catalog_ids": [c.pk for c in stale],
    }
