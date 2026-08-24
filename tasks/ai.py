"""
Deporte: generación de planes 100% determinista (sin IA) + test de
repaso de Idiomas con IA (Google Gemini).

Generación de planes de Deporte — YA NO usa IA. Hasta antes, esto le
pedía a Gemini que inventara objetivos/progresión a partir de una frase
libre; se quitó porque depender de una API externa (con su propia cuota
gratis y su propia demanda) para algo tan mecánico como "elige N
ejercicios del nivel pedido y súbeles la exigencia poco a poco" no tenía
sentido — es exactamente el tipo de cálculo que un programa hace mejor,
más rápido y sin límite de peticiones que un LLM. `_select_sport_exercises`
elige los ejercicios (mismo filtro EN DURO por nivel/foco que ya existía)
y `default_item_fields` pone el punto de partida y la meta según tablas
fijas por categoría de ejercicio y nivel (ver más abajo) — ambas cosas
deterministas, sin llamada de red de por medio. `apply_pacing` (que ya
existía, reutilizada tal cual) traduce eso a los incrementos reales de
progresión con la misma cuenta que la calculadora del formulario web/app
(ver plan_item_form.html).

Nada de esto llega a la base de datos directamente: `api.build_plan_draft`
aplica el resultado sobre instancias de Plan/PlanItem SIN GUARDAR,
reutilizando `_apply_plan_fields` / `_apply_plan_item_fields` (las mismas
que usa la creación manual), así que un plan generado automáticamente
pasa por exactamente la misma validación que uno hecho a mano. El
usuario revisa y confirma (y puede tocar los números) antes de que se
guarde nada de verdad.

Estudio · Idiomas tampoco pasa por aquí: la asignación de cursos del
catálogo (CoursePlaylist → CourseModule) es puramente determinista, ver
`api.build_language_plan_draft` — sin IA de por medio, mismo espíritu
que el resto de este módulo. Estudio · Hábito simple y General se crean
a mano, sin nada que generar automáticamente (no hay catálogo del que
elegir).

Lo ÚNICO que sigue usando IA en toda la app es el test de repaso de
Idiomas (`generate_quiz`, al final de este archivo) — preguntas de
opción múltiple sobre los últimos vídeos vistos, que no decide nada de
ningún plan, solo da un empujón a prestar atención. Por eso `_call_gemini`
y GEMINI_API_KEY se quedan — todo lo demás de la llamada a Gemini para
planes (prompt, schema, `generate_plan_draft`) ha desaparecido.
"""
import json
import urllib.error
import urllib.request

from django.conf import settings

from .models import Exercise, PlanItem, Task


class PlanAIError(Exception):
    """Error legible en español, pensado para enseñarse tal cual al usuario."""


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

DEFAULT_TIMEOUT = 30


# ------------------------------------------------ cuestionario estructurado
#
# El usuario elige nivel/foco/equipamiento como campos explícitos (ver
# plan_ai_form.html) — son los datos que `_select_sport_exercises` y
# `default_item_fields` usan para elegir ejercicios y sus números de
# partida/meta, sin nada que adivinar de una frase libre.

# Ejercicios que necesitan barra de dominadas o paralelas — es el único
# "equipamiento" que de verdad cambia qué se puede proponer, porque es lo
# único que falta en muchas casas. El resto del catálogo (core, pierna,
# running) es peso corporal / aire libre.
_NEEDS_BAR_EQUIPMENT = {
    "pullup", "wide-pullup", "chinup", "weighted-pullup", "jumping-pullup",
    "dips", "weighted-dips",
}

# Ejercicios cuyo contador de cámara existe en la web (static/js/workout.js)
# pero todavía no se ha portado a la app móvil (mobile-app/www/js/workout.js
# le falta processArcherPullup(); mobile-app/www/js/workout-view.js no trae
# "wallsit" en POSTURE_COUNTERS ni a checkWallSitPosture en workout.js). Si
# se propusieran, un item de plan con ese ejercicio se quedaría colgado en
# la pantalla de cámara del móvil sin contar nada. Se excluyen aquí (para
# web Y para móvil por igual, ya que la API no distingue quién llama)
# hasta que se porten — quitar de este set en cuanto workout.js de la app
# cuente con ambos.
_PENDING_MOBILE_PORT = {"archer-pullup", "wall-sit"}

# Bicicleta (bicycle-crunch) se excluye del todo del generador automático,
# a petición de Alex: es tren inferior/core, nivel intermedio, y hace
# básicamente el mismo trabajo que scissor-kick (piernas en tijera/pedaleo
# tumbado) — con los dos en el mismo plan sobra uno. Se queda scissor-kick.
# Sigue existiendo en el catálogo por si se crea un plan a mano.
_EXCLUDED_FROM_AUTOGEN = {"bicycle-crunch"}

# Dificultad del MOVIMIENTO en sí — no confundir con el nivel del usuario
# (`_EXERCISE_CATEGORY_DEFAULTS`, que ajusta series/reps/peso sobre un
# mismo ejercicio). Esto dice qué variantes tiene sentido siquiera
# OFRECER: un principiante de verdad no debería abrir con dominadas
# lastradas o kneehold en barra, necesita una base antes. Un avanzado, en
# cambio, puede seguir usando ejercicios "de principiante" (sentadillas,
# flexiones...) sin que eso sea un problema — lo que cambia para él es la
# exigencia (series/reps/peso), no que el movimiento deje de valer.
#
# El filtro por dificultad (ver `_filter_catalog_by_level` /
# `_select_sport_exercises`) es EN DURO para los tres niveles: si un
# ejercicio no está en la lista filtrada, directamente no se puede elegir.
_EXERCISE_DIFFICULTY = {
    # Tren superior
    "push-up": "beginner",
    "jumping-pullup": "beginner",
    "dips": "intermediate",
    "pullup": "intermediate",
    "chinup": "intermediate",
    "wide-pullup": "advanced",
    "weighted-pullup": "advanced",
    "weighted-dips": "advanced",
    "archer-pullup": "advanced",
    # El pino exige equilibrio invertido y estabilidad de hombro que un
    # principiante de verdad no suele tener todavía, aunque se use apoyo
    # en la pared — más cerca de kneehold-bar (también "advanced") que de
    # dead-hang (que quitó su sitio aquí: solo pedía agarre y aguantar).
    "handstand": "advanced",
    # Tren inferior / core
    "squat": "beginner",
    "situp": "beginner",
    "crunch": "beginner",
    "plank": "beginner",
    "bicycle-crunch": "intermediate",
    "leg-raise": "intermediate",
    "side-plank": "intermediate",
    "weighted-squat": "intermediate",
    "wall-sit": "intermediate",
    "double-crunch": "advanced",
    "scissor-kick": "advanced",
    "kneehold-bar": "advanced",
}
_LEVEL_TIER_ORDER = ["beginner", "intermediate", "advanced"]


def _filter_catalog_by_level(catalog, fitness_level):
    """
    Filtro EN DURO por nivel: EXACTAMENTE la dificultad pedida, nunca
    otra — pedir intermedio da ejercicios etiquetados intermedio, punto,
    igual que pedir principiante da solo principiante y avanzado solo
    avanzado. Antes intermedio/avanzado incluían también cualquier
    dificultad más alta (para no quedarse cortos de ejercicios), y eso
    era justo el problema que reportó Alex: pedir nivel intermedio y que
    salieran ejercicios avanzados de verdad (dominadas lastradas,
    kneehold en barra...) sin haberlo pedido. Si para una zona concreta
    esto deja pocos ejercicios, se queda así — mejor un plan corto y
    exacto al nivel pedido que uno más largo mezclando dificultades.

    Sin nivel especificado: catálogo intacto. Los ejercicios sin
    etiqueta en `_EXERCISE_DIFFICULTY` (running, que se mide distinto)
    nunca se tocan aquí.
    """
    if fitness_level not in _LEVEL_TIER_ORDER:
        return catalog
    result = []
    for e in catalog:
        tier = _EXERCISE_DIFFICULTY.get(e.slug)
        if tier is None or tier == fitness_level:
            result.append(e)
    return result

# Máximo de objetivos para un plan de UNA sola zona (tren superior o
# inferior) — ver `_select_sport_exercises`. Cuerpo completo usa un tope
# más alto porque tiene que cubrir las dos zonas a la vez. Sin mínimo a
# propósito: el catálogo de una zona/nivel puede dar menos ejercicios de
# los que caben aquí, y eso es correcto (mejor un plan corto y exacto al
# nivel pedido que uno relleno con otra dificultad u otra zona).
_FOCUSED_ZONE_MAX_ITEMS = 6
_FULL_BODY_MAX_ITEMS = 8

# Tope de peso AÑADIDO por defecto (kg) para dominadas/fondos con peso —
# la inmensa mayoría de chalecos lastrados de uso doméstico llegan hasta
# aquí. Sin un `max_load_kg` explícito del usuario, se asume este techo
# en vez de proponer un peso que nadie puede cargar.
_DEFAULT_MAX_LOAD_KG = 20

FITNESS_LEVEL_CHOICES = [
    ("beginner", "Principiante"),
    ("intermediate", "Intermedio"),
    ("advanced", "Avanzado"),
]

FOCUS_AREA_CHOICES = [
    ("", "Cuerpo completo"),
    (Task.SUBCATEGORY_UPPER_BODY, "Tren superior"),
    (Task.SUBCATEGORY_LOWER_BODY, "Tren inferior / core"),
    (Task.SUBCATEGORY_RUNNING, "Running / cardio"),
]

# ------------------------------------------------------ selección de catálogo

def _catalog_exercises(exclude_slugs=None):
    """Catálogo activo, sin los `exclude_slugs` (p. ej. porque el usuario no
    tiene el equipamiento que necesitan). Devuelve instancias de Exercise,
    en el orden en que deben ofrecerse (`order`, luego nombre)."""
    exclude_slugs = exclude_slugs or set()
    qs = Exercise.objects.filter(is_active=True).order_by("order", "name")
    return [e for e in qs if e.slug not in exclude_slugs]


def all_exercise_choices():
    """
    Todo el catálogo activo, apto para el selector manual del formulario
    (ver plan_ai_form.html) — SIEMPRE el mismo, da igual el nivel o el
    foco corporal que se haya marcado en el resto del formulario: el
    usuario tiene que poder elegir cualquier ejercicio, no solo los que
    la generación automática habría propuesto. La única exclusión es
    técnica (`_PENDING_MOBILE_PORT`, ejercicios sin contador de cámara
    en la app móvil todavía) — ni nivel ni equipamiento se filtran aquí.

    Devuelve una lista de dicts `{slug, name, body_area, body_area_label,
    needs_bar}` YA ORDENADA por zona (tren superior, tren inferior/core,
    running — mismo orden que `FOCUS_AREA_CHOICES`) para poder agrupar
    en la plantilla con `{% regroup %}` sin más (ese tag necesita que
    las filas de un mismo grupo vengan seguidas; el catálogo en sí no
    está ordenado por zona).
    """
    body_area_labels = dict(FOCUS_AREA_CHOICES)
    zone_priority = {value: i for i, (value, _) in enumerate(FOCUS_AREA_CHOICES) if value}
    catalog = sorted(
        _catalog_exercises(exclude_slugs=_PENDING_MOBILE_PORT),
        key=lambda e: zone_priority.get(e.body_area, 99),
    )
    return [
        {
            "slug": e.slug,
            "name": e.name,
            "body_area": e.body_area,
            "body_area_label": body_area_labels.get(e.body_area, e.body_area),
            "needs_bar": e.slug in _NEEDS_BAR_EQUIPMENT,
        }
        for e in catalog
    ]


def _select_exercises_from_slugs(slugs, no_bar_equipment, max_load_kg=None):
    """
    Selección MANUAL: el usuario elige exactamente qué ejercicios quiere
    en el plan (ver selector en plan_ai_form.html) — a propósito SIN
    filtro de nivel ni de zona (eso es cosa de `_filter_catalog_by_level`,
    que aquí no se llama): si lo ha marcado a mano, da igual su
    dificultad o a qué zona pertenezca, entra tal cual. Solo se respetan
    las exclusiones TÉCNICAS/de equipamiento de siempre: barra que no
    tiene (`no_bar_equipment`), peso extra que no tiene
    (`max_load_kg == 0` — ver `_select_sport_exercises`) y ejercicios sin
    contador en la app móvil todavía (`_PENDING_MOBILE_PORT`).

    Devuelve los ejercicios en el mismo orden en que se marcaron (sin
    duplicados), ignorando cualquier slug que no exista o no esté
    disponible con ese equipamiento.
    """
    exclude = (
        (_NEEDS_BAR_EQUIPMENT if no_bar_equipment else set())
        | (_WEIGHTED_SLUGS if max_load_kg == 0 else set())
        | _PENDING_MOBILE_PORT
    )
    catalog = {e.slug: e for e in _catalog_exercises(exclude_slugs=exclude)}
    ordered_unique_slugs = list(dict.fromkeys(slugs or []))
    return [catalog[s] for s in ordered_unique_slugs if s in catalog]


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


def _select_sport_exercises(fitness_level, focus_area, no_bar_equipment, selected_slugs=None, max_load_kg=None):
    """
    Elige qué ejercicios del catálogo entran en un plan de Deporte.

    Si el usuario ha marcado ejercicios a mano en el selector del
    formulario (`selected_slugs`), son esos y solo esos — nivel y foco
    corporal se ignoran para elegir el catálogo (siguen usándose para
    calcular series/repeticiones/peso de partida y meta, ver
    `default_item_fields`). Ver `_select_exercises_from_slugs`.

    Sin selección manual, la elección es automática, determinista (sin
    IA) según nivel + foco corporal + equipamiento — filtro EN DURO por
    nivel/zona (`_filter_catalog_by_level`): EXACTAMENTE el nivel pedido
    y EXACTAMENTE la(s) zona(s) pedida(s), sin mezclar ni rellenar con
    otra dificultad ni otra zona aunque el catálogo se quede corto.

    `max_load_kg == 0` (el campo del formulario es obligatorio — ver
    plan_ai_form.html — así que 0 es como el usuario dice "no tengo
    nada de peso extra en casa") descarta del todo los ejercicios con
    lastre (`_WEIGHTED_SLUGS`: dominadas/fondos/sentadillas con peso) —
    proponerlos sin nada con qué lastrar no tiene sentido. Con
    `max_load_kg` sin especificar (None) o mayor que 0, esos ejercicios
    siguen pudiendo salir con normalidad (el número en sí solo pone tope
    a la meta de peso, eso lo hace `apply_pacing`).

    Devuelve la lista de ejercicios en el orden en que deben entrar en
    el plan (el primero es el candidato natural a `is_headline`, salvo
    en running — ver `build_sport_plan_draft`). Lanza `PlanAIError` si
    no hay ningún ejercicio disponible para lo pedido (equipamiento,
    nivel o foco imposibles con el catálogo actual, o ningún ejercicio
    marcado a mano que siga disponible).
    """
    if selected_slugs:
        exercises = _select_exercises_from_slugs(selected_slugs, no_bar_equipment, max_load_kg=max_load_kg)
        if not exercises:
            raise PlanAIError(
                "Ninguno de los ejercicios marcados está disponible con ese equipamiento — "
                "revisa la selección."
            )
        return exercises

    exclude = (
        (_NEEDS_BAR_EQUIPMENT if no_bar_equipment else set())
        | (_WEIGHTED_SLUGS if max_load_kg == 0 else set())
        | _PENDING_MOBILE_PORT
        | _EXCLUDED_FROM_AUTOGEN
    )
    catalog = _filter_catalog_by_level(_catalog_exercises(exclude_slugs=exclude), fitness_level)

    if focus_area == Task.SUBCATEGORY_UPPER_BODY:
        # Solo tren superior, solo del nivel pedido — a propósito SIN
        # relleno de ningún tipo (ni de core, ni de otra dificultad): si
        # el catálogo de esa zona/nivel se queda corto, el plan sale con
        # menos ejercicios, nunca con ejercicios de otra zona o de otro
        # nivel que no se ha pedido.
        exercises = [e for e in catalog if e.body_area == Task.SUBCATEGORY_UPPER_BODY]
        exercises = exercises[:_FOCUSED_ZONE_MAX_ITEMS]
    elif focus_area == Task.SUBCATEGORY_LOWER_BODY:
        exercises = [e for e in catalog if e.body_area == Task.SUBCATEGORY_LOWER_BODY]
        exercises = exercises[:_FOCUSED_ZONE_MAX_ITEMS]
    elif focus_area == Task.SUBCATEGORY_RUNNING:
        # El propio "running" es el plan — nada de otra zona (antes se
        # añadía algún ejercicio de core como "apoyo", pero eso ya no es
        # running: si se pide running, sale running y punto).
        exercises = [e for e in catalog if e.body_area == Task.SUBCATEGORY_RUNNING]
    else:
        # Cuerpo completo (focus_area vacío): tren superior + tren
        # inferior + running, EN BLOQUES — todo el tren superior seguido,
        # LUEGO todo el tren inferior, luego running al final. A
        # propósito NO se intercalan (antes sí, para "repartir" entre las
        # dos zonas, pero eso significaba saltar de sentadillas a
        # dominadas a abdominales a flexiones sin parar — nadie entrena
        # así de verdad, mejor terminar una zona antes de pasar a la
        # siguiente). El tope de ejercicios solo se aplica a tren
        # superior + inferior — running siempre entra, no cuenta contra
        # ese tope (si no, en algunos niveles se quedaba fuera).
        upper = [e for e in catalog if e.body_area == Task.SUBCATEGORY_UPPER_BODY]
        lower = [e for e in catalog if e.body_area == Task.SUBCATEGORY_LOWER_BODY]
        running = [e for e in catalog if e.body_area == Task.SUBCATEGORY_RUNNING]
        exercises = (upper + lower)[:_FULL_BODY_MAX_ITEMS] + running

    if focus_area in (Task.SUBCATEGORY_UPPER_BODY, Task.SUBCATEGORY_LOWER_BODY, Task.SUBCATEGORY_RUNNING):
        if not any(e.body_area == focus_area for e in exercises):
            zona = dict(FOCUS_AREA_CHOICES).get(focus_area, focus_area).lower()
            if no_bar_equipment:
                raise PlanAIError(
                    f"No hay ningún ejercicio de {zona} en el catálogo que no necesite barra "
                    "de dominadas ni paralelas. Marca que sí tienes barra/paralelas, o elige "
                    "otro foco corporal."
                )
            if max_load_kg == 0:
                raise PlanAIError(
                    f"No hay ningún ejercicio de {zona} en el catálogo sin peso añadido para ese "
                    "nivel. Pon cuánto peso extra tienes disponible, o elige otro foco corporal."
                )
            if fitness_level == "beginner":
                raise PlanAIError(
                    f"No hay ningún ejercicio de {zona} de nivel principiante en el catálogo "
                    "todavía. Prueba con nivel intermedio, o elige otro foco corporal."
                )
            raise PlanAIError(f"No hay ningún ejercicio activo de {zona} en el catálogo todavía.")

    if not exercises:
        raise PlanAIError(
            "No queda ningún ejercicio activo en el catálogo con ese equipamiento y nivel — "
            "revisa el catálogo de ejercicios antes de generar un plan de Deporte."
        )

    return exercises


# ------------------------------------------------ números de partida y meta
#
# Lo que antes decidía la IA "a ojo" (con qué series/repeticiones/segundos
# empezar, hasta dónde llegar) ahora sale de estas tablas fijas — una por
# categoría de ejercicio (según cómo se mide y cuánto exige de verdad:
# dominadas/fondos a pulso no empiezan por los mismos números que
# sentadillas o flexiones) y nivel. `default_item_fields` deja el
# resultado listo para `apply_pacing`, que es quien calcula el
# incremento real por escalón a partir de `weeks_to_goal`.

# Dominadas/fondos a peso corporal — más duros por repetición que el
# resto del catálogo pose (sentadillas, flexiones...), empiezan más bajo.
_LOW_REP_STRENGTH_SLUGS = {"pullup", "wide-pullup", "chinup", "dips"}
# Variantes con lastre — llevan progresión 'double' (reps dentro de un
# rango y, al llegar arriba, más peso), el resto de pose usa 'reps'.
# Tracción/empuje a pulso (dominadas, fondos) y pierna (sentadillas) no
# aguantan ni suben el mismo peso ni las mismas repeticiones — de ahí
# `_WEIGHTED_CATEGORY_BY_SLUG`, que dice con qué tabla de
# `_EXERCISE_CATEGORY_DEFAULTS` calcular cada una (ver más abajo).
_WEIGHTED_SLUGS = {"weighted-pullup", "weighted-dips", "weighted-squat"}
_WEIGHTED_CATEGORY_BY_SLUG = {
    "weighted-pullup": "weighted_pull",
    "weighted-dips": "weighted_pull",
    "weighted-squat": "weighted_legs",
}

_EXERCISE_CATEGORY_DEFAULTS = {
    # pose/timed: en vez de una meta fija, `rate` es cuánto sube CADA
    # ESCALÓN (`sessions_per_step` sesiones) — así la meta se recalcula
    # según cuántas semanas pida el usuario (ver comentario grande más
    # abajo) en vez de quedarse corta para un plan largo. `max_goal` es
    # el techo realista de un entrenador de verdad (nadie llega a 200
    # dominadas), por si el plan es muy largo.
    "high_rep": {  # pose, peso corporal, series largas (sentadillas, flexiones, abdominales...)
        "beginner":     {"sets": 2, "start": 8,  "rate": 1, "sessions_per_step": 2, "max_goal": 35},
        "intermediate": {"sets": 3, "start": 12, "rate": 1, "sessions_per_step": 2, "max_goal": 45},
        "advanced":     {"sets": 4, "start": 15, "rate": 1, "sessions_per_step": 2, "max_goal": 55},
    },
    "low_rep": {  # pose, tracción/empuje a pulso (dominadas, fondos) — sube más despacio
        "beginner":     {"sets": 2, "start": 3, "rate": 1, "sessions_per_step": 4, "max_goal": 14},
        "intermediate": {"sets": 3, "start": 4, "rate": 1, "sessions_per_step": 4, "max_goal": 18},
        "advanced":     {"sets": 4, "start": 6, "rate": 1, "sessions_per_step": 4, "max_goal": 22},
    },
    "timed": {  # aguantes (plancha, pino...) — sube en segundos, no en repeticiones
        "beginner":     {"sets": 2, "start": 20, "rate": 2, "sessions_per_step": 2, "max_goal": 100},
        "intermediate": {"sets": 3, "start": 30, "rate": 2, "sessions_per_step": 2, "max_goal": 140},
        "advanced":     {"sets": 4, "start": 40, "rate": 3, "sessions_per_step": 2, "max_goal": 210},
    },
    "weighted_pull": {  # dominadas/fondos con lastre — progresión 'double'
        "beginner":     {"sets": 2, "low": 3, "top": 6,  "weight_goal": 10},
        "intermediate": {"sets": 3, "low": 4, "top": 8,  "weight_goal": 15},
        "advanced":     {"sets": 4, "low": 5, "top": 10, "weight_goal": 20},
    },
    "weighted_legs": {  # sentadillas con lastre — progresión 'double'. La
        # pierna aguanta muchas más repeticiones por serie que un tirón/
        # empuje a pulso (dominadas/fondos), de ahí el rango de reps más
        # alto con el mismo tope de peso (`_DEFAULT_MAX_LOAD_KG`/lo que
        # diga el usuario — mismo chaleco lastrado, no hay otro dato de
        # equipamiento en el formulario).
        "beginner":     {"sets": 2, "low": 6,  "top": 10, "weight_goal": 10},
        "intermediate": {"sets": 3, "low": 8,  "top": 12, "weight_goal": 15},
        "advanced":     {"sets": 4, "low": 10, "top": 15, "weight_goal": 20},
    },
    "running": {
        "beginner":     {"start_km": 1.0, "goal_km": 3.0, "start_pace": 420, "goal_pace": 360},
        "intermediate": {"start_km": 2.0, "goal_km": 5.0, "start_pace": 360, "goal_pace": 300},
        "advanced":     {"start_km": 3.0, "goal_km": 8.0, "start_pace": 300, "goal_pace": 240},
    },
}


def _rate_based_goal(start, weeks, sessions_per_week, sessions_per_step, rate, max_goal):
    """
    Mete cuánto va a subir `apply_pacing` en el sitio: en vez de una
    meta fija (que un plan de pocas semanas nunca alcanza y uno de
    muchas remata a las pocas semanas — el bug que reportó Alex: pedir
    12 semanas y que la tabla de progreso solo llegue a la 4 o 5,
    porque `apply_pacing` calcula el incremento como
    `round(meta - inicio) / escalones)` y con una meta pequeña y muchos
    escalones eso sale por debajo de 1 y se redondea para arriba a 1,
    o sea que en la práctica sube MÁS rápido de lo pensado y se llega a
    la meta mucho antes de agotar las semanas), la meta se calcula para
    que encaje EXACTO con el número de escalones de esas semanas: así
    `apply_pacing` recupera un incremento de `rate` unidades por
    escalón y el plan usa las semanas enteras que se han pedido, ni más
    ni menos. `max_goal` evita que un plan muy largo dispare la meta a
    algo irreal (nadie llega a 40+ dominadas).
    """
    steps = _steps_for_weeks(max(1, int(weeks or 1)), sessions_per_week, sessions_per_step)
    return min(max_goal, start + rate * steps)


def default_item_fields(exercise, fitness_level, weeks, sessions_per_week):
    """
    Punto de partida + meta predeterminados para `exercise`, según nivel
    (ver `_EXERCISE_CATEGORY_DEFAULTS`) — esto es lo que sustituye a la
    IA: en vez de pedirle a un modelo que invente series/repeticiones
    razonables, se usan tablas fijas por categoría de ejercicio y nivel.
    `weeks_to_goal` es siempre la duración completa del plan — sin IA no
    hay quien decida "en cuántas semanas" salvo el propio usuario, y ya
    lo ha dicho al elegir cuántas semanas dura el plan. La META en
    reps/segundos (no así en running ni en dominadas/fondos con peso,
    ver `_rate_based_goal`) se calcula a partir de esas semanas para que
    la progresión encaje con la duración pedida en vez de rematarse a
    las pocas semanas o quedarse corta.

    Devuelve un dict listo para pasar a `apply_pacing`, que es quien
    calcula los incrementos reales de progresión a partir de estos
    start_*/goal_* (misma función que ya usaba el camino con IA).
    """
    level = fitness_level if fitness_level in _LEVEL_TIER_ORDER else "intermediate"
    weeks = max(1, int(weeks or 1))
    sessions_per_week = max(1, int(sessions_per_week or 1))
    fields = {"weeks_to_goal": weeks}

    if exercise.mode == Exercise.MODE_DISTANCE:
        d = _EXERCISE_CATEGORY_DEFAULTS["running"][level]
        fields.update(
            sessions_per_step=2,
            progression=PlanItem.PROG_DISTANCE,
            start_distance_km=d["start_km"], goal_distance_km=d["goal_km"],
            start_pace_seconds_per_km=d["start_pace"], goal_pace_seconds_per_km=d["goal_pace"],
        )
        return fields

    if exercise.mode == Exercise.MODE_TIMED:
        d = _EXERCISE_CATEGORY_DEFAULTS["timed"][level]
        goal = _rate_based_goal(
            d["start"], weeks, sessions_per_week, d["sessions_per_step"], d["rate"], d["max_goal"]
        )
        fields.update(
            sessions_per_step=d["sessions_per_step"],
            progression=PlanItem.PROG_REPS,
            start_sets=d["sets"], goal_sets=d["sets"] + 2,
            start_seconds=d["start"], goal_seconds=goal,
        )
        return fields

    if exercise.slug in _WEIGHTED_SLUGS:
        d = _EXERCISE_CATEGORY_DEFAULTS[_WEIGHTED_CATEGORY_BY_SLUG[exercise.slug]][level]
        fields.update(
            sessions_per_step=2,
            progression=PlanItem.PROG_DOUBLE,
            start_sets=d["sets"], goal_sets=d["sets"] + 2,
            start_reps=d["low"], rep_range_low=d["low"], goal_reps=d["top"],
            start_weight_kg=0, goal_weight_kg=d["weight_goal"],
        )
        return fields

    category = "low_rep" if exercise.slug in _LOW_REP_STRENGTH_SLUGS else "high_rep"
    d = _EXERCISE_CATEGORY_DEFAULTS[category][level]
    goal = _rate_based_goal(
        d["start"], weeks, sessions_per_week, d["sessions_per_step"], d["rate"], d["max_goal"]
    )
    fields.update(
        sessions_per_step=d["sessions_per_step"],
        progression=PlanItem.PROG_REPS,
        start_sets=d["sets"], goal_sets=d["sets"] + 2,
        start_reps=d["start"], goal_reps=goal,
    )
    return fields


# ------------------------------------------------------- ritmo → escalón

def _steps_for_weeks(weeks_to_goal, sessions_per_week, sessions_per_step):
    """Misma cuenta que `escalones()` en plan_item_form.html."""
    total_sessions = max(1, weeks_to_goal) * max(1, sessions_per_week)
    return max(1, round(total_sessions / max(1, sessions_per_step)))


def _sanitize_sets(item_fields):
    """
    Red de seguridad: fuerza que las series también progresen (no solo
    reps/peso), incluso si el usuario ha tocado los números a mano en la
    vista previa antes de confirmar. Un entrenador de verdad sube series
    poco a poco (2-3 -> 3-5), nunca las deja fijas para siempre ni las
    dispara a un número absurdo.
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


def apply_pacing(item_fields, *, exercise, sessions_per_week, max_load_kg=None):
    """
    Traduce `weeks_to_goal` a `reps_increment` / `weight_increment_kg` /
    `distance_increment_km` / `pace_decrement_seconds` (lo que de verdad
    entiende PlanItem), con la misma fórmula que la calculadora del
    formulario. También sanea combinaciones inválidas (progresión
    'double' en un ejercicio cronometrado, progresión que no sea
    'distance' en running).

    `max_load_kg` es el tope de peso AÑADIDO (chaleco lastrado, cinturón
    con discos...) que el usuario tiene disponible de verdad — sin esto
    por defecto se asume ~20 kg (`_DEFAULT_MAX_LOAD_KG`), lo habitual en
    un chaleco lastrado doméstico, para no proponer un `goal_weight_kg`
    que nadie puede cargar en casa.

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
        # El suelo del ciclo de doble progresión tiene que ser de dónde
        # parte el usuario de verdad, no un valor inventado — si no, el
        # primer escalón del plan le manda "bajar" a un número que no
        # tiene nada que ver con lo que puede hacer ya el primer día (el
        # bug que reportó Alex: pasar de 3x12 a 4x6 sin sentido). Si no
        # llega `rep_range_low` explícito, se deriva de `start_reps`, que
        # sí manda siempre.
        low = int(item_fields.get("rep_range_low") or item_fields.get("start_reps") or 6)
        top = int(item_fields.get("goal_reps") or (low + 6))
        if top <= low:
            top = low + 6  # rango inválido (ej. editado a mano en la vista previa) — evita 0 o negativo
        span = max(1, top - low + 1)
        cycles = max(1, round(steps / span))

        # Tope de peso añadido realista: la mayoría de chalecos lastrados
        # domésticos llegan hasta ~20 kg — sin esto se podría proponer un
        # goal_weight_kg que nadie tiene forma de cargar en casa.
        start_weight = float(item_fields.get("start_weight_kg") or 0)
        cap = start_weight + (max_load_kg if max_load_kg is not None else _DEFAULT_MAX_LOAD_KG)
        goal_weight = min(float(item_fields.get("goal_weight_kg") or 0), cap)
        item_fields["goal_weight_kg"] = goal_weight

        d_weight = goal_weight - start_weight
        item_fields["weight_increment_kg"] = round(max(0.5, d_weight / cycles), 1) if d_weight > 0 else 2.5
        item_fields["rep_range_low"] = low
        item_fields["goal_reps"] = top
        return item_fields

    # PROG_REPS
    start_key, goal_key = ("start_seconds", "goal_seconds") if is_timed else ("start_reps", "goal_reps")
    delta = int(item_fields.get(goal_key) or 0) - int(item_fields.get(start_key) or 0)
    item_fields["reps_increment"] = max(1, round(delta / steps)) if delta > 0 else 1
    return item_fields


# ================================================== TESTS DE REPASO (IDIOMAS)
#
# No blocking, no progresión que decidir — al contrario que arriba, aquí
# la IA no toca ni un solo campo del plan. Solo escribe preguntas de
# opción múltiple sobre los temas de los últimos vídeos vistos, para dar
# un empujón a prestar atención. Ver CourseQuiz (tasks/models.py) y
# api.maybe_trigger_quiz para el disparo y el guardado.

_QUIZ_OPTIONS_COUNT = 4


def _quiz_schema(n_questions):
    return {
        "type": "OBJECT",
        "properties": {
            "questions": {
                "type": "ARRAY",
                "minItems": n_questions,
                "maxItems": n_questions,
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "question": {"type": "STRING"},
                        "options": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "minItems": _QUIZ_OPTIONS_COUNT,
                            "maxItems": _QUIZ_OPTIONS_COUNT,
                        },
                        "correct_index": {
                            "type": "INTEGER",
                            "description": "Índice (0-3) de la opción correcta dentro de 'options'.",
                        },
                    },
                    "required": ["question", "options", "correct_index"],
                },
            },
        },
        "required": ["questions"],
    }


def _build_quiz_prompt(*, language, level, topics, known_languages):
    parts = [
        f"Eres un profesor de {language}, nivel MCER {level or 'A1'}. Prepara un test corto de "
        "opción múltiple (4 opciones, una sola correcta) para un estudiante que acaba de ver estos "
        "vídeos — no es un examen formal, es un empujón rápido para comprobar que ha prestado "
        "atención de verdad mientras estudiaba, dentro de la app de tareas \"Strive\".",
        "",
        "Temas cubiertos en los últimos vídeos vistos, en el orden en que los vio:",
        "\n".join(f"- {t}" for t in topics),
        "",
        f"Escribe entre 3 y 5 preguntas, EN {language} (vocabulario y gramática de ese nivel — "
        "nunca en español salvo que el idioma a aprender sea el español), repartidas entre esos "
        "temas, no todas del mismo. Las 4 opciones de cada pregunta van también en ese idioma. "
        "Nunca preguntes datos del vídeo en sí (título, canal, duración...) — solo el idioma que "
        "se está aprendiendo.",
    ]
    if known_languages:
        parts.append(
            f"El estudiante ya domina: {known_languages} — puedes apoyarte en eso para que la "
            f"pregunta se entienda si hace falta, pero las opciones siguen siendo en {language}."
        )
    return "\n".join(parts)


def generate_quiz(*, language, level, topics, known_languages=""):
    """
    Test corto (opción múltiple) sobre los temas de los últimos vídeos
    vistos de un curso de idioma. Devuelve
    {"questions": [{"question", "options": [4], "correct_index"}, ...]}
    — nunca guarda nada, quien llama (api.maybe_trigger_quiz) crea el
    CourseQuiz con esto.
    """
    language = (language or "").strip()
    if not language:
        raise PlanAIError("Falta el idioma del curso para generar el test.")

    clean_topics = []
    for t in topics or []:
        t = (t or "").strip()
        if t and t not in clean_topics:
            clean_topics.append(t[:100])
    clean_topics = clean_topics[:8]
    if not clean_topics:
        raise PlanAIError("No hay suficiente contenido de los últimos vídeos para armar un test.")

    n_questions = min(5, max(3, len(clean_topics)))
    prompt_text = _build_quiz_prompt(
        language=language, level=level, topics=clean_topics,
        known_languages=(known_languages or "").strip()[:200],
    )
    raw = _call_gemini(prompt_text, _quiz_schema(n_questions))
    if not isinstance(raw, dict) or "questions" not in raw:
        raise PlanAIError("La IA devolvió un test con un formato inesperado. Prueba a generar de nuevo.")

    questions = []
    for q in raw.get("questions") or []:
        if not isinstance(q, dict):
            continue
        options = q.get("options")
        question_text = (q.get("question") or "").strip()
        if not question_text or not isinstance(options, list) or len(options) != _QUIZ_OPTIONS_COUNT:
            continue
        try:
            correct_index = int(q.get("correct_index"))
        except (TypeError, ValueError):
            continue
        if not (0 <= correct_index < _QUIZ_OPTIONS_COUNT):
            continue
        questions.append({
            "question": question_text[:300],
            "options": [str(o).strip()[:120] for o in options],
            "correct_index": correct_index,
        })

    if not questions:
        raise PlanAIError("La IA no devolvió ninguna pregunta válida. Prueba a generar de nuevo.")
    return {"questions": questions}


