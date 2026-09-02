"""
Tiempo real acumulado por tipo de tarea — Deporte y Enfoque, sumando
WorkoutSession.session_duration_seconds y TimerSession.minutes.

No distingue tareas que cuentan para un Plan de tareas sueltas
("freestyle"): las dos generan la misma fila (una WorkoutSession o
TimerSession con su duración), así que sumarlas por categoría ya las
cubre a ambas por igual sin tratamiento aparte. Quien necesite el
desglose de un plan concreto puede filtrar estas mismas tablas por
`plan=...` — no hace falta duplicar nada aquí para eso.

Pensado para: (a) enseñar un número de refuerzo tipo "llevas 200h
estudiando", y (b) derivar insignias por umbrales de horas — ver
ACHIEVEMENT_THRESHOLDS_HOURS. Las insignias se calculan en caliente
contra el total actual, sin guardar ningún registro de "conseguida el
día X": si el historial cambia (se borra una sesión, por ejemplo), el
número de insignias conseguidas se ajusta solo en la siguiente
petición en vez de quedarse "conseguida" con datos que ya no existen.
"""
from django.db.models import Sum
from django.utils import timezone

from .models import Task, TimerSession, WorkoutSession

# Umbrales de horas para las insignias — mismos para todas las
# categorías por ahora. Ordenados de menor a mayor a propósito: el
# primero que no se supera es "next_badge_hours".
ACHIEVEMENT_THRESHOLDS_HOURS = [10, 50, 100, 250, 500, 1000, 2500, 5000, 10000]

# Clave interna → etiqueta a enseñar. La clave de Enfoque sigue el
# patrón "focus_<subcategoría>" para no chocar nunca con "sport".
BUCKET_LABELS = {
    "sport": "Deporte",
    "focus_reading": "Enfoque · Lectura",
    "focus_study_session": "Enfoque · Estudio",
    "focus_stretch": "Enfoque · Estiramientos",
    "focus_focus_other": "Enfoque · Otro",
    # "Idiomas" (SUBCATEGORY_LANGUAGE) no tiene bucket aquí a propósito:
    # no genera TimerSession, va por CourseModule/Occurrence — no hay
    # tiempo real que sumar, solo vídeos vistos.
    "study_udemy": "Estudio · Curso de Udemy",
}


def _year_start():
    now = timezone.localtime()
    return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)


def _sum_field(queryset, field):
    """Suma un campo sobre un queryset ya filtrado. Sum() devuelve None
    con un queryset vacío — aquí se normaliza a 0 para no tener que
    comprobarlo en cada sitio que llama a esto."""
    return queryset.aggregate(total=Sum(field))["total"] or 0


def time_totals(user):
    """
    Devuelve {bucket_key: {"label", "all_time_hours", "this_year_hours",
    "badges_earned", "next_badge_hours"}}, uno por cada categoría/
    subcategoría con al menos una sesión registrada (los buckets sin
    ninguna sesión todavía no aparecen — no tiene sentido enseñar una
    insignia de "0h conseguidas").
    """
    year_start = _year_start()

    workouts = WorkoutSession.objects.filter(user=user, deleted_at__isnull=True)
    timers = TimerSession.objects.filter(user=user, deleted_at__isnull=True)

    seconds_by_bucket = {
        "sport": {
            "all_time": _sum_field(workouts, "session_duration_seconds"),
            "this_year": _sum_field(workouts.filter(recorded_at__gte=year_start), "session_duration_seconds"),
        },
    }
    for subcat, _label in Task.FOCUS_SUBCATEGORY_CHOICES:
        subcat_timers = timers.filter(subcategory=subcat)
        minutes_all = _sum_field(subcat_timers, "minutes")
        minutes_year = _sum_field(subcat_timers.filter(recorded_at__gte=year_start), "minutes")
        seconds_by_bucket[f"focus_{subcat}"] = {
            "all_time": minutes_all * 60,
            "this_year": minutes_year * 60,
        }
    # "Curso de Udemy" vive en category=study (ver Task.SUBCATEGORY_UDEMY)
    # pero también usa TimerSession igual que Enfoque — mismo cálculo,
    # bucket aparte para no mezclarlo con Deporte/Enfoque en la tarjeta.
    udemy_timers = timers.filter(subcategory=Task.SUBCATEGORY_UDEMY)
    udemy_minutes_all = _sum_field(udemy_timers, "minutes")
    udemy_minutes_year = _sum_field(udemy_timers.filter(recorded_at__gte=year_start), "minutes")
    seconds_by_bucket["study_udemy"] = {
        "all_time": udemy_minutes_all * 60,
        "this_year": udemy_minutes_year * 60,
    }

    buckets = {}
    for key, seconds in seconds_by_bucket.items():
        if not seconds["all_time"]:
            continue
        all_hours = seconds["all_time"] / 3600
        buckets[key] = {
            "label": BUCKET_LABELS.get(key, key),
            "all_time_hours": round(all_hours, 1),
            "this_year_hours": round(seconds["this_year"] / 3600, 1),
            "badges_earned": [h for h in ACHIEVEMENT_THRESHOLDS_HOURS if all_hours >= h],
            "next_badge_hours": next((h for h in ACHIEVEMENT_THRESHOLDS_HOURS if all_hours < h), None),
        }
    return buckets
