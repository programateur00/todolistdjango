"""
Calorías aproximadas de cada ejercicio.

Método MET estándar (kcal = MET × kg × horas), pero aplicado según cómo se
mide cada ejercicio:

  - Con repeticiones (dominadas, flexiones, sentadillas...): kcal POR
    REPETICIÓN. Cada repetición cuenta como lo que dura una repetición
    típica de ese ejercicio (SECONDS_PER_REP; 3 s si no está en la lista),
    así que 10 flexiones gastan lo mismo las hagas rápido o lento, y los
    descansos, pausas o fallos de la cámara no mueven el resultado.
  - Cronometrados (plancha, dead hang, estiramientos...): por segundo
    aguantado.
  - Running: por distancia y velocidad media (andar y correr no gastan igual).

El MET de cada ejercicio vive en Exercise.met (editable desde /admin;
valores del Compendio de Actividad Física, redondeados). Si un ejercicio no
lo tiene (p. ej. uno nuevo creado desde el admin) se usa un valor por
defecto según su tipo.

Es una ESTIMACIÓN (±25 % fácilmente): no mide pulso ni intensidad real.
Cuenta calorías brutas, como hacen los relojes. Se guarda en
WorkoutSession.calories_kcal al crear la sesión, con el peso corporal de ese
momento, para que cambiar el peso luego no reescriba el histórico (el
comando backfill_calories sí puede recalcular).
"""

DEFAULT_BODY_WEIGHT_KG = 70.0   # si el usuario aún no ha puesto el suyo en Ajustes
DEFAULT_SECONDS_PER_REP = 3.0   # lo que dura una repetición típica

# Duración típica de UNA repetición en los ejercicios que no son de ~3 s.
SECONDS_PER_REP = {
    # rápidos
    "jumping-jack": 1.0, "heel-kicks": 1.0, "knee-raises": 1.0, "arm-circles": 1.5,
    "arm-scissors": 1.5, "high-leg-raise": 1.5, "leg-rotation": 2.0, "scissor-kick": 1.5,
    "crunch": 2.0, "double-crunch": 2.5, "leg-raise": 2.5, "superman": 2.5,
    "scapular-pull": 2.0, "dumbbell-curl": 2.5, "neck-lateral-mobility": 2.0,
    "neck-turn-side": 2.0, "hip-forward-back": 2.0, "hip-lateral-mobility": 2.0,
    "forearm-rotation-elbow-hold": 2.0,
    # lentos / exigentes
    "pullup": 4.0, "wide-pullup": 4.0, "chinup": 4.0, "weighted-pullup": 4.5,
    "wide-weighted-pullup": 4.5, "archer-pullup": 5.0, "jumping-pullup": 3.0,
    "dips": 4.0, "weighted-dips": 4.5, "handstand-push-up": 5.0,
    "burpee": 4.0, "pistol-squat": 5.0, "l-sit": 4.0, "weighted-squat": 4.0,
}

# MET por defecto cuando Exercise.met está vacío.
_DEFAULT_MET_BY_MODE = {"pose": 5.0, "manual": 4.0, "timed": 3.5}
_WARMUP_MET = 2.8


def body_weight_for(user):
    """(kg, es_el_de_por_defecto) del usuario."""
    from .models import UserSettings
    if user is not None:
        us = UserSettings.objects.filter(user=user).only("body_weight_kg").first()
        if us and us.body_weight_kg:
            return float(us.body_weight_kg), False
    return DEFAULT_BODY_WEIGHT_KG, True


def exercise_met(exercise):
    if exercise is None:
        return 4.0
    if exercise.met:
        return float(exercise.met)
    if exercise.body_area == "warmup":
        return _WARMUP_MET
    return _DEFAULT_MET_BY_MODE.get(exercise.mode, 4.0)


def running_met(distance_km, seconds):
    """MET de andar/correr según la velocidad media (fórmulas ACSM)."""
    if not distance_km or not seconds:
        return None
    meters_per_min = distance_km * 1000 / (seconds / 60)
    # Por debajo de ~8 km/h (133 m/min) se considera andar; por encima, correr.
    vo2 = (0.2 if meters_per_min >= 133 else 0.1) * meters_per_min + 3.5
    return vo2 / 3.5


def kcal_per_rep(exercise, kg):
    """Calorías de UNA repetición de `exercise` para una persona de `kg`."""
    slug = exercise.slug if exercise is not None else ""
    seconds = SECONDS_PER_REP.get(slug, DEFAULT_SECONDS_PER_REP)
    return exercise_met(exercise) * kg * seconds / 3600


def estimate_workout_calories(ws):
    """kcal aproximadas de un WorkoutSession, o None si no hay datos para estimarlas."""
    from .models import Exercise
    exercise = Exercise.objects.filter(slug=ws.exercise).first()
    kg, _ = body_weight_for(ws.user)
    total = ws.session_duration_seconds or 0

    # Running: distancia + velocidad.
    if ws.distance_km or (exercise is not None and exercise.mode == Exercise.MODE_DISTANCE):
        met = running_met(ws.distance_km, total)
        if met is None:
            return None
        return round(met * kg * total / 3600, 1)

    # El lastre (chaleco, discos) cuenta como masa extra que se mueve.
    mass = kg + (ws.added_weight_kg or 0)

    # Cronometrados: por segundo aguantado.
    if exercise is not None and exercise.mode == Exercise.MODE_TIMED:
        held = 0.0
        for s in (ws.sets if isinstance(ws.sets, list) else []):
            if isinstance(s, dict) and not s.get("reps"):
                held += sum(d for d in (s.get("durations") or []) if isinstance(d, (int, float)))
        held = held or float(total)
        if held <= 0:
            return None
        return round(exercise_met(exercise) * held / 3600 * mass, 1)

    # Con repeticiones: por repetición.
    reps = ws.total_reps or len([d for d in (ws.rep_durations or []) if isinstance(d, (int, float))])
    if reps <= 0:
        return None
    return round(reps * kcal_per_rep(exercise, mass), 1)
