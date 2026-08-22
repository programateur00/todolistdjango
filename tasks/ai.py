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

Estudio · Idiomas YA NO pasa por aquí: la asignación de cursos del
catálogo (CoursePlaylist → CourseModule) es puramente determinista,
ver `api.build_language_plan_draft` — sin IA de por medio, mismo
espíritu que este módulo pero sin necesitarlo, porque el catálogo ya
está curado a mano. Lo único de Idiomas que SÍ usa IA es el test de
repaso (`generate_quiz`, al final de este archivo) — preguntas de
opción múltiple sobre lo último visto, que no decide nada del plan en
sí, así que no comparte el resto del diseño de arriba.
"""
import json
import urllib.error
import urllib.request

from django.conf import settings

from .models import Exercise, PlanItem, Task


class PlanAIError(Exception):
    """Error legible en español, pensado para enseñarse tal cual al usuario."""


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

MAX_PROMPT_CHARS = 800
DEFAULT_TIMEOUT = 30


# ------------------------------------------------ cuestionario estructurado
#
# Antes de esto, lo único que decidía el contenido del plan era una frase
# libre ("ponerme en forma") — y ante la ambigüedad, la IA por defecto
# tiraba a lo mínimo seguro (2 series de 10, un par de ejercicios). En vez
# de confiar en que la IA adivine nivel/foco/equipamiento de una frase
# corta, se le piden como campos explícitos al usuario (ver
# plan_ai_form.html / plan-view.js) y se le dan a la IA como hechos, no
# como algo que tenga que inferir.

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
# la IA los propusiera, un item de plan con ese ejercicio se quedaría
# colgado en la pantalla de cámara del móvil sin contar nada. Se excluyen
# aquí (para web Y para móvil por igual, ya que la API no distingue quién
# llama) hasta que se porten — quitar de este set en cuanto workout.js de
# la app cuente con ambos.
_PENDING_MOBILE_PORT = {"archer-pullup", "wall-sit"}

# Dificultad del MOVIMIENTO en sí — no confundir con el nivel del usuario
# (_LEVEL_BRIEF, que ajusta series/reps/peso sobre un mismo ejercicio).
# Esto dice qué variantes tiene sentido siquiera PROPONER: un principiante
# de verdad no debería abrir con dominadas lastradas o kneehold en barra,
# necesita una base antes. Un avanzado, en cambio, puede seguir usando
# ejercicios "de principiante" (sentadillas, flexiones...) sin que eso sea
# un problema — lo que cambia para él es la exigencia (series/reps/peso),
# no que el movimiento deje de valer. Por eso el filtro por dificultad
# (ver generate_plan_draft) solo excluye en duro para "beginner"; para
# intermedio/avanzado es el propio texto del prompt el que empuja hacia
# arriba, sin cerrar la puerta a lo básico.
_EXERCISE_DIFFICULTY = {
    # Tren superior
    "push-up": "beginner",
    "dead-hang": "beginner",
    "jumping-pullup": "beginner",
    "dips": "intermediate",
    "pullup": "intermediate",
    "chinup": "intermediate",
    "wide-pullup": "advanced",
    "weighted-pullup": "advanced",
    "weighted-dips": "advanced",
    "archer-pullup": "advanced",
    # Tren inferior / core
    "squat": "beginner",
    "situp": "beginner",
    "crunch": "beginner",
    "plank": "beginner",
    "wall-sit": "beginner",
    "bicycle-crunch": "intermediate",
    "leg-raise": "intermediate",
    "double-crunch": "intermediate",
    "scissor-kick": "intermediate",
    "side-plank": "intermediate",
    "kneehold-bar": "advanced",
}
_DIFFICULTY_LABEL = {"beginner": "principiante", "intermediate": "intermedio", "advanced": "avanzado"}

# Ejercicios de CORE dentro de tren inferior/core — sirven de relleno de
# un plan de TREN SUPERIOR si ese catálogo por sí solo no llega al mínimo
# pedido (ver _FOCUS_AREA_BRIEF). A propósito NO incluye ejercicios de
# pierna suelta (sentadillas, silla en pared): esos no pintan nada en un
# plan de tren superior aunque anden cortos de ejercicios.
_CORE_SLUGS = {
    "situp", "crunch", "leg-raise", "bicycle-crunch", "side-plank",
    "double-crunch", "scissor-kick", "plank", "kneehold-bar",
}

# Mínimo de objetivos para un plan de UNA sola zona (tren superior o
# inferior) — ver _response_schema. Cuerpo completo usa un rango más
# alto porque tiene que cubrir las dos zonas a la vez (ver
# _FOCUS_AREA_FULL_BODY_BRIEF). Se usa también para decidir si hace
# falta rellenar tren superior con apoyo de core (ver más abajo).
_FOCUSED_ZONE_MIN_ITEMS = 4

# Tope de peso AÑADIDO por defecto (kg) para dominadas/fondos con peso —
# la inmensa mayoría de chalecos lastrados de uso doméstico llegan hasta
# aquí. Sin un `max_load_kg` explícito del usuario, se asume este techo
# en vez de dejar que la IA proponga un peso que nadie puede cargar.
_DEFAULT_MAX_LOAD_KG = 20

BODY_SEX_CHOICES = [
    ("", "Prefiero no decirlo"),
    ("female", "Mujer"),
    ("male", "Hombre"),
]

FITNESS_LEVEL_CHOICES = [
    ("beginner", "Principiante"),
    ("intermediate", "Intermedio"),
    ("advanced", "Avanzado"),
]

_LEVEL_BRIEF = {
    "beginner": (
        "Nivel de partida: PRINCIPIANTE — no entrena de forma regular todavía, o lleva muy poco "
        "tiempo. El punto de partida tiene que ser algo que pueda cumplir desde el primer día, "
        "pero eso no significa quedarse ahí para siempre: tiene que haber una progresión real y "
        "visible a lo largo de las semanas, no un techo bajo mantenido de principio a fin. El "
        "catálogo de abajo YA viene sin los ejercicios de dificultad=avanzado para este nivel (se "
        "han quitado de raíz, ni los menciones ni los eches de menos) — elige con confianza entre "
        "los que quedan."
    ),
    "intermediate": (
        "Nivel de partida: INTERMEDIO — entrena de forma más o menos regular desde hace meses y "
        "ya domina la técnica básica de los movimientos. Empieza más arriba que a un principiante "
        "absoluto — no tiene sentido arrancarle en el mismo sitio que a alguien que no ha hecho "
        "nunca el ejercicio. El catálogo de abajo lleva una etiqueta de dificultad por ejercicio "
        "(dificultad=principiante/intermedio/avanzado): para este nivel, que la MAYORÍA de los "
        "objetivos sean dificultad=intermedio o avanzado — los de dificultad=principiante vale "
        "usarlos como mucho en uno de apoyo, nunca como el grueso del plan."
    ),
    "advanced": (
        "Nivel de partida: AVANZADO — entrena con regularidad desde hace años y ya tiene una base "
        "de fuerza sólida. Empieza alto de verdad (series, repeticiones y/o peso ya exigentes) y "
        "plantea una meta ambiciosa — un plan flojo para alguien con este nivel es peor que no dar "
        "plan. El catálogo de abajo lleva una etiqueta de dificultad por ejercicio: para este "
        "nivel, prioriza los de dificultad=avanzado e intermedio — un ejercicio de "
        "dificultad=principiante solo si de verdad aporta algo (p. ej. como calentamiento breve), "
        "nunca como protagonista del plan."
    ),
}
_LEVEL_UNKNOWN_BRIEF = (
    "Nivel de partida: el usuario no lo ha especificado. Búscalo en sus propias palabras (\"ahora "
    "mismo hago 2 dominadas\", \"llevo meses sin entrenar\"...) y ajústate a eso. Si tampoco hay "
    "ninguna pista, parte de un nivel intermedio-bajo razonable — NUNCA del mínimo absoluto por "
    "defecto; un entrenador de verdad nunca da un plan de mínimos solo porque no le han dado todos "
    "los datos, hace la mejor estimación razonable. El catálogo de abajo lleva una etiqueta de "
    "dificultad por ejercicio (dificultad=principiante/intermedio/avanzado) — úsala como referencia "
    "para ese nivel intermedio-bajo que estás asumiendo."
)

FOCUS_AREA_CHOICES = [
    ("", "Cuerpo completo"),
    (Task.SUBCATEGORY_UPPER_BODY, "Tren superior"),
    (Task.SUBCATEGORY_LOWER_BODY, "Tren inferior / core"),
    (Task.SUBCATEGORY_RUNNING, "Running / cardio"),
]

_FOCUS_AREA_BRIEF = {
    Task.SUBCATEGORY_UPPER_BODY: (
        "Foco elegido por el usuario: TREN SUPERIOR. El catálogo de abajo ya viene filtrado a "
        "solo tren superior (y, únicamente si ese catálogo por sí solo se queda corto, algún "
        "ejercicio de core de apoyo — nunca pierna suelta ni running, aparezca lo que aparezca "
        "en el catálogo). Elige de 4 a 6 objetivos de ahí, con distintos patrones de movimiento "
        "sin repetir variantes del mismo ejercicio — por defecto apunta a la parte alta del "
        "rango (5-6), el catálogo tiene variedad de sobra para no quedarte corto."
    ),
    Task.SUBCATEGORY_LOWER_BODY: (
        "Foco elegido por el usuario: TREN INFERIOR / CORE. El catálogo de abajo ya viene "
        "filtrado a solo esa zona. Elige de 4 a 6 objetivos de ahí — por defecto apunta a la "
        "parte alta del rango (5-6), el catálogo tiene variedad de sobra — sin salir de esa zona "
        "aunque el usuario mencione otra cosa en su frase."
    ),
    Task.SUBCATEGORY_RUNNING: (
        "Foco elegido por el usuario: RUNNING. El ejercicio 'running' es OBLIGATORIAMENTE el "
        "único is_headline=true y el centro absoluto del plan (progresión de distancia y ritmo, "
        "nunca de series/repeticiones). Puedes añadir como mucho 1-2 ejercicios de apoyo (core o "
        "pierna) si de verdad ayudan a correr mejor y a prevenir lesiones — nunca conviertas esto "
        "en un plan de fuerza con el running de relleno, y nunca superes esos 1-2 de apoyo."
    ),
}
_FOCUS_AREA_FULL_BODY_BRIEF = (
    "Foco elegido por el usuario: CUERPO COMPLETO — sin restricción de zona, el catálogo de "
    "abajo trae TODO. Elige de 5 a 8 objetivos (más que un plan de una sola zona, porque aquí "
    "hay que cubrir las dos a la vez): reparte de verdad entre empuje (fondos/flexiones), "
    "tracción (dominadas), pierna (sentadillas) y core/aguantes (plancha, abdominales, plancha "
    "lateral...), con ejercicios de TREN SUPERIOR Y de TREN INFERIOR a la vez — nunca te quedes "
    "en 2-3 ejercicios sueltos de un solo lado del cuerpo. Añade running solo si el objetivo del "
    "usuario tiene algo que ver con correr o resistencia cardio."
)


# --------------------------------------------------------------- prompt

def _catalog_exercises(exclude_slugs=None):
    """Catálogo activo, sin los `exclude_slugs` (p. ej. porque el usuario no
    tiene el equipamiento que necesitan). Devuelve instancias de Exercise,
    no texto — el texto para el prompt lo arma `_exercise_catalog_lines`."""
    exclude_slugs = exclude_slugs or set()
    qs = Exercise.objects.filter(is_active=True).order_by("order", "name")
    return [e for e in qs if e.slug not in exclude_slugs]


def _exercise_catalog_lines(exercises):
    lines = []
    for e in exercises:
        if e.mode == Exercise.MODE_DISTANCE:
            medida = "se mide en distancia (km) y ritmo (min/km) — SIEMPRE progresión 'distance'"
        elif e.mode == Exercise.MODE_TIMED:
            medida = "se mide en SEGUNDOS aguantados (start_seconds/goal_seconds), no en repeticiones"
        else:
            medida = "se mide en REPETICIONES (start_reps/goal_reps)"
        area = {"upper_body": "tren superior", "lower_body": "tren inferior/core", "running": "cardio"}.get(
            e.body_area, e.body_area or "general"
        )
        dificultad = _DIFFICULTY_LABEL.get(_EXERCISE_DIFFICULTY.get(e.slug))
        etiqueta_dificultad = f" · dificultad={dificultad}" if dificultad else ""
        lines.append(f"- slug=\"{e.slug}\" · {e.name} · {area} · {medida}{etiqueta_dificultad}")
    return "\n".join(lines) if lines else "(ninguno disponible con los filtros actuales)"


_PLAN_TYPE_BRIEF = {
    "sport": (
        "Deporte: el plan persigue varios objetivos de ejercicio del catálogo de abajo — cuántos "
        "exactamente depende del foco elegido por el usuario (número exacto justo junto al foco, "
        "más abajo). Un plan de uno o dos ejercicios no es un programa de entrenamiento serio, y "
        "el catálogo de abajo tiene variedad de sobra para no quedarte corto. Exactamente UNO "
        "debe llevar is_headline=true (la medida que define si el plan se ha conseguido, ej. "
        "\"llegar a 4x12 dominadas con 20 kg\"); el resto son apoyo (progresan pero no deciden). "
        "Elige ejercicios que de verdad ayuden al objetivo del usuario y cubran su cuerpo de "
        "forma equilibrada, mezclando movimientos de repeticiones con aguantes isométricos cuando "
        "el catálogo los tenga para esa zona (dan una sesión más completa y variada, no son un "
        "relleno) — no metas relleno ni variantes redundantes del mismo movimiento (dominadas y "
        "dominadas anchas SÍ son la misma variante repetida; sentadillas y plancha lateral NO lo "
        "son, son estímulos distintos y cuentan como diversidad real)."
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


def _build_prompt(
    user_prompt, plan_type, weeks, sessions_per_week, *,
    exercises=None, fitness_level="", focus_area="", no_bar_equipment=False,
    session_minutes=None, limitations="", body_weight_kg=None, height_cm=None,
    sex="", max_load_kg=None,
):
    brief = _PLAN_TYPE_BRIEF.get(plan_type, _PLAN_TYPE_BRIEF["sport"])
    parts = [
        "Eres el mejor entrenador personal/coach posible, diseñando planes de progresión "
        "dentro de la app de tareas \"Strive\" para un cliente real. Programas como lo haría "
        "un profesional de verdad: sobrecarga progresiva de manual (series Y repeticiones "
        "suben con el tiempo, no solo repeticiones sin techo hasta el infinito), variedad real "
        "de patrones de movimiento, y objetivos que de verdad llevan al cliente a su meta — "
        "nada de rellenar con lo primero que se te ocurra, y nunca un plan flojo o genérico solo "
        "porque el usuario ha escrito poco en su frase (para eso están los campos de más abajo). "
        "El usuario ya ha decidido: el TIPO de plan, cuántas SEMANAS va a durar, y CUÁNTOS DÍAS a "
        f"la semana entrena ({sessions_per_week} días/semana). Tu trabajo es traducir su objetivo "
        "en un plan concreto y medible — nada de vaguedades.",
        "",
        f"Tipo de plan: {brief}",
        "",
        f"Duración: {weeks} semanas.",
        "",
        (
            f"Lo que pide el usuario, en sus propias palabras:\n\"{user_prompt}\""
            if user_prompt else
            "El usuario no ha escrito contexto adicional en texto libre — básate solo en los "
            "campos estructurados de abajo (nivel, foco corporal, equipamiento, tiempo, "
            "lesiones). No lo trates como una señal de que hay que dar un plan flojo: la "
            "ausencia de frase no es lo mismo que la ausencia de nivel — usa igualmente el "
            "nivel indicado abajo tal cual."
        ),
    ]
    if plan_type == "sport":
        parts += ["", _LEVEL_BRIEF.get(fitness_level, _LEVEL_UNKNOWN_BRIEF)]
        parts += ["", _FOCUS_AREA_BRIEF.get(focus_area, _FOCUS_AREA_FULL_BODY_BRIEF)]
        if body_weight_kg or height_cm or sex:
            datos = []
            if body_weight_kg:
                datos.append(f"peso corporal {body_weight_kg} kg")
            if height_cm:
                datos.append(f"altura {height_cm} cm")
            if sex:
                datos.append(dict(BODY_SEX_CHOICES).get(sex, sex).lower())
            parts.append(
                "Datos físicos del usuario (" + ", ".join(datos) + "). OJO: esto NO es un peso a "
                "levantar, es su cuerpo — solo sirve para calibrar mejor la dificultad relativa. A "
                "igualdad de repeticiones en dominadas/fondos, alguien más pesado mueve más masa "
                "(es más fuerte de lo que parece); ajusta ligeramente start_reps y el ritmo de "
                "progresión con esto en cuenta, sin exagerar el efecto. El sexo y la altura son "
                "solo referencia estadística de estándares de fuerza típicos — si hay conflicto, "
                "manda siempre el nivel de partida que ya ha dado el usuario arriba, nunca esto."
            )
        if max_load_kg is not None:
            parts.append(
                f"Peso máximo de lastre disponible: {max_load_kg} kg. En cualquier ejercicio con "
                "progresión 'double', el goal_weight_kg NUNCA puede superar "
                f"start_weight_kg + {max_load_kg} — no hay forma de cargar más que eso en casa."
                + (
                    " Con 0 kg disponibles, no uses progresión 'double' en ningún ejercicio — usa "
                    "'reps' en su lugar, porque no hay manera de añadir peso."
                    if max_load_kg <= 0 else ""
                )
            )
        else:
            parts.append(
                f"Peso máximo de lastre disponible: no especificado — asume un máximo realista de "
                f"~{_DEFAULT_MAX_LOAD_KG} kg añadidos (lo habitual en un chaleco lastrado "
                "doméstico) para dominadas/fondos con peso, salvo que el usuario diga "
                "explícitamente en su texto libre que tiene más (un cinturón de dominadas con "
                "discos, por ejemplo, sí puede superar eso)."
            )
        if no_bar_equipment:
            parts.append(
                "Equipamiento: el usuario NO tiene barra de dominadas ni paralelas en casa — el "
                "catálogo de abajo ya viene sin esos ejercicios, no los eches de menos ni los "
                "sugieras en las notas."
            )
        if session_minutes:
            parts.append(
                f"Tiempo disponible: cada sesión tiene que caber en unos {session_minutes} "
                "minutos — ajusta cuántos ejercicios y series metes para que el plan sea realista "
                "en ese tiempo, no lo sobrecargues pensando que hay tiempo ilimitado."
            )
        if limitations:
            parts.append(
                f"Lesión o limitación a tener en cuenta: \"{limitations}\" — adapta o evita "
                "cualquier ejercicio del catálogo que pueda agravarla, y menciona en las notas qué "
                "has tenido en cuenta por esto."
            )
        parts += [
            "",
            "Catálogo de ejercicios disponibles (usa SOLO estos slugs, no inventes otros):",
            _exercise_catalog_lines(exercises or []),
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
            "semanas, no solo las repeticiones o el peso. El punto de partida (series y "
            "repeticiones) tiene que encajar con el NIVEL DE PARTIDA de arriba — ni tan bajo que "
            "sea insultante para alguien con experiencia, ni tan alto que sea imposible para quien "
            "empieza. goal_sets nunca debe quedarse igual que start_sets salvo que el usuario pida "
            "explícitamente mantener el volumen fijo — una progresión que solo mueve las "
            "repeticiones para siempre no es realista (nadie llega a 40 dominadas seguidas).",
            "- 'weeks_to_goal' es en cuántas semanas quiere llegar al destino desde el punto de "
            "partida — sé realista (una progresión de fuerza razonable sube poco a poco).",
            "- Los puntos de partida deben ser alcanzables desde el primer día para alguien que "
            "empieza el plan ahora — mejor quedarse corto que proponer algo imposible.",
            "",
            "Cobertura de ejercicios — respeta el número de objetivos indicado arriba junto al "
            "foco elegido (varía según sea tren superior, tren inferior, running o cuerpo "
            "completo): un programa serio trabaja el cuerpo de forma equilibrada, no un solo "
            "movimiento. NO metas varias variantes del mismo movimiento a la vez (ej. nunca "
            "dominadas + dominadas anchas + chin ups juntas en el mismo plan) salvo que el "
            "usuario pida explícitamente trabajar variantes — eso es relleno, no variedad real.",
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


def _response_schema(plan_type, focus_area=""):
    plan_schema = {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING", "description": "Título general del plan, corto. Ej: \"Ponerme en forma\"."},
            "notes": {"type": "STRING", "description": "1-2 frases de contexto/ánimo sobre el plan."},
        },
        "required": ["name", "notes"],
    }
    if plan_type == "sport" and focus_area == Task.SUBCATEGORY_RUNNING:
        # Un plan de running puro no tiene 3-6 movimientos distintos entre
        # los que elegir — el catálogo solo tiene UN ejercicio de running.
        # El propio "running" es el plan; como mucho 1-2 de apoyo (ver
        # _FOCUS_AREA_BRIEF). Pedir aquí el mismo mínimo de 3 forzaría a la
        # IA a inflar el plan con relleno o a inventar ejercicios.
        items_schema = {"type": "ARRAY", "items": _ITEM_SPORT_SCHEMA, "minItems": 1, "maxItems": 3}
    elif plan_type == "sport" and focus_area in (Task.SUBCATEGORY_UPPER_BODY, Task.SUBCATEGORY_LOWER_BODY):
        # Una sola zona: el catálogo ya viene filtrado a esa zona (ver
        # generate_plan_draft) y es más corto que el completo — pedir el
        # mismo rango alto que cuerpo completo dejaría a la IA rellenando
        # con relleno o variantes repetidas para llegar al mínimo.
        items_schema = {"type": "ARRAY", "items": _ITEM_SPORT_SCHEMA, "minItems": 4, "maxItems": 6}
    elif plan_type == "sport":
        # Cuerpo completo (focus_area vacío): tiene que cubrir tren
        # superior Y tren inferior a la vez, así que necesita más
        # objetivos que un plan de una sola zona — ver
        # _FOCUS_AREA_FULL_BODY_BRIEF (pide 1/3 más que una zona sola).
        items_schema = {"type": "ARRAY", "items": _ITEM_SPORT_SCHEMA, "minItems": 5, "maxItems": 8}
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


def generate_plan_draft(
    *, prompt, plan_type, weeks, sessions_per_week,
    fitness_level="", focus_area="", no_bar_equipment=False,
    session_minutes=None, limitations="", body_weight_kg=None, height_cm=None,
    sex="", max_load_kg=None,
):
    """
    Llama a Gemini y devuelve el dict crudo `{"plan": {...}, "items": [...]}`
    tal como lo mandó la IA — sin aplicar todavía sobre el modelo. La
    validación/clamping de verdad la hace `api.plan_generate` reutilizando
    `_apply_plan_fields` / `_apply_plan_item_fields`.

    `fitness_level` / `focus_area` / `no_bar_equipment` / `session_minutes` /
    `limitations` / `body_weight_kg` / `height_cm` / `sex` / `max_load_kg` son
    el cuestionario estructurado que rellena el usuario antes de generar (ver
    plan_ai_form.html / plan-view.js): se le dan a la IA como hechos
    concretos en vez de esperar que los adivine de una frase libre — que es
    justo lo que producía planes de mínimos ("2 series de 10") cuando el
    usuario escribía algo tan vago como "ponerme en forma".
    """
    user_prompt = (prompt or "").strip()[:MAX_PROMPT_CHARS]
    # Estudio y General no tienen cuestionario estructurado — la frase libre
    # es su ÚNICA fuente de información (ni siquiera el nombre del plan sale
    # de otro sitio), así que ahí sigue siendo obligatoria. Deporte sí tiene
    # nivel/foco/equipamiento como campos propios, así que puede generar un
    # plan serio aunque el usuario no escriba nada más.
    if not user_prompt and plan_type != "sport":
        raise PlanAIError("Cuéntame qué quieres conseguir con este plan.")

    exercises = []
    if plan_type == "sport":
        exclude = (_NEEDS_BAR_EQUIPMENT if no_bar_equipment else set()) | _PENDING_MOBILE_PORT
        catalog = _catalog_exercises(exclude_slugs=exclude)

        # Principiante: fuera del catálogo que ve la IA los ejercicios
        # dificultad=avanzado de raíz (ver _EXERCISE_DIFFICULTY) — no basta
        # con pedírselo por texto, un principiante de verdad no debería ni
        # ver "dominadas lastradas" como opción posible. Intermedio/avanzado
        # NO se filtran así a propósito (ver el comentario en
        # _EXERCISE_DIFFICULTY): ahí es el propio texto del prompt
        # (_LEVEL_BRIEF) el que empuja hacia arriba, sin cerrar la puerta a
        # lo básico cuando de verdad ayuda.
        if fitness_level == "beginner":
            catalog = [e for e in catalog if _EXERCISE_DIFFICULTY.get(e.slug) != "advanced"]

        # Foco por zona — filtro EN DURO sobre la lista que se le enseña a
        # la IA, no solo texto de prompt: esto es lo que de verdad arregla
        # "pido tren superior y me devuelve tren inferior", porque ahora la
        # IA no puede elegir de una lista que ni siquiera contiene esos
        # ejercicios.
        if focus_area == Task.SUBCATEGORY_UPPER_BODY:
            exercises = [e for e in catalog if e.body_area == Task.SUBCATEGORY_UPPER_BODY]
            if len(exercises) < _FOCUSED_ZONE_MIN_ITEMS:
                relleno = [e for e in catalog if e.slug in _CORE_SLUGS and e not in exercises]
                exercises = exercises + relleno
        elif focus_area == Task.SUBCATEGORY_LOWER_BODY:
            exercises = [e for e in catalog if e.body_area == Task.SUBCATEGORY_LOWER_BODY]
        else:
            # Running y cuerpo completo: sin filtrar por zona — running
            # necesita poder ofrecer 1-2 ejercicios de apoyo de otra zona
            # (ver _FOCUS_AREA_BRIEF) y cuerpo completo por definición debe
            # cubrir todo el catálogo.
            exercises = catalog

        if focus_area in (Task.SUBCATEGORY_UPPER_BODY, Task.SUBCATEGORY_LOWER_BODY, Task.SUBCATEGORY_RUNNING):
            if not any(e.body_area == focus_area for e in exercises):
                zona = dict(FOCUS_AREA_CHOICES).get(focus_area, focus_area).lower()
                if no_bar_equipment:
                    raise PlanAIError(
                        f"No hay ningún ejercicio de {zona} en el catálogo que no necesite barra "
                        "de dominadas ni paralelas. Marca que sí tienes barra/paralelas, o elige "
                        "otro foco corporal."
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

    prompt_text = _build_prompt(
        user_prompt, plan_type, weeks, sessions_per_week, exercises=exercises,
        fitness_level=fitness_level, focus_area=focus_area, no_bar_equipment=no_bar_equipment,
        session_minutes=session_minutes, limitations=limitations, body_weight_kg=body_weight_kg,
        height_cm=height_cm, sex=sex, max_load_kg=max_load_kg,
    )
    schema = _response_schema(plan_type, focus_area=focus_area)
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


def apply_pacing(item_fields, *, exercise, sessions_per_week, max_load_kg=None):
    """
    Traduce `weeks_to_goal` (lo que decidió la IA) a `reps_increment` /
    `weight_increment_kg` / `distance_increment_km` / `pace_decrement_seconds`
    (lo que de verdad entiende PlanItem), con la misma fórmula que la
    calculadora del formulario. También sanea combinaciones que la IA
    podría proponer mal (progresión 'double' en un ejercicio cronometrado,
    progresión que no sea 'distance' en running).

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
        # bug que reportó Alex: pasar de 3x12 a 4x6 sin sentido). La IA
        # nunca manda `rep_range_low` (no está en el schema — no hace
        # falta que la IA haga esta cuenta), así que se deriva de
        # `start_reps`, que sí manda siempre.
        low = int(item_fields.get("rep_range_low") or item_fields.get("start_reps") or 6)
        top = int(item_fields.get("goal_reps") or (low + 6))
        if top <= low:
            top = low + 6  # techo inválido propuesto por la IA — evita un rango de 0 o negativo
        span = max(1, top - low + 1)
        cycles = max(1, round(steps / span))

        # Tope de peso añadido realista: la mayoría de chalecos lastrados
        # domésticos llegan hasta ~20 kg — sin esto la IA puede proponer
        # un goal_weight_kg que nadie tiene forma de cargar en casa.
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


