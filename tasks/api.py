"""
API JSON para la app móvil (Capacitor).

Por qué Django "a pelo" y no Django REST Framework: son ~15 endpoints de
CRUD sencillo, y DRF traería una dependencia grande a un hosting con 512
MiB de disco. Aquí no hay magia — cada vista recibe JSON, valida y
devuelve JSON.

Identidad: la API usa el campo `uuid`, no la clave primaria numérica. Es
lo que permite que un dispositivo cree algo sin conexión sin chocar con
lo que haya creado otro (dos móviles crearían la "tarea 7" cada uno).

Autenticación: la maneja BasicAuthMiddleware a nivel de proyecto, así que
la app debe mandar la cabecera Authorization en cada llamada. Las vistas
van con @csrf_exempt porque la API no usa cookies de sesión — la
protección CSRF existe para ataques basados en cookies, y aquí no aplica.
"""
import json
from functools import wraps

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date, parse_time
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Exercise, Occurrence, Routine, RoutineItem, Task, WorkoutSession
from .utils import get_current_user


# ---------------------------------------------------------------- utils

def api(*methods):
    """Decorador común: exime de CSRF, limita métodos y convierte
    cualquier excepción no prevista en JSON en vez de en una página de
    error HTML (que la app no sabría interpretar)."""
    def decorator(view):
        @csrf_exempt
        @require_http_methods(list(methods))
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            try:
                return view(request, *args, **kwargs)
            except json.JSONDecodeError:
                return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)
            except Http404:
                # Sin esto Django devuelve su página HTML de "Page not
                # found", la app hace resp.json(), revienta, y el usuario
                # ve un error incomprensible en vez de saber qué pasó.
                return JsonResponse(
                    {"ok": False, "error": "No encontrado (¿ya se había borrado?)"},
                    status=404,
                )
        return wrapper
    return decorator


def body(request):
    if not request.body:
        return {}
    return json.loads(request.body)


def _user():
    return get_current_user()


def tasks_qs():
    """Tareas del usuario actual, excluyendo las borradas (borrado suave)."""
    return Task.objects.filter(user=_user(), deleted_at__isnull=True)


# ----------------------------------------------------- serializadores

def task_json(t):
    return {
        "uuid": str(t.uuid),
        "series_id": str(t.series_id),
        "title": t.title,
        "notes": t.notes,
        "category": t.category,
        "category_display": t.get_category_display(),
        "subcategory": t.subcategory,
        "is_avoid": t.is_avoid,
        "capabilities": t.category_capabilities,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "due_time": t.due_time.strftime("%H:%M") if t.due_time else None,
        "repeat": t.repeat,
        "interval": t.interval,
        "custom_days": t.custom_days_list(),
        "is_important": t.is_important,
        "is_done": t.is_done,
        "expired": t.expired,
        "is_overdue": t.is_overdue(),
        "minutes_left": t.minutes_remaining(),
        # La app programa el aviso a due_time y deja que el servidor
        # resuelva sola la tarea pasado el margen. Se manda calculado para
        # que app y web usen exactamente el mismo criterio.
        "avoid_grace_hours": Task.AVOID_GRACE_HOURS if t.is_avoid else None,
        "avoid_question": t.avoid_question or "¿Has caído hoy?",
        "avoid_success_label": t.avoid_success_label or "Sigo con la racha",
        "avoid_fail_label": t.avoid_fail_label or "Romper racha",
        "updated_at": t.updated_at.isoformat(),
    }


def exercise_json(e):
    return {
        "slug": e.slug, "name": e.name, "mode": e.mode,
        "mode_display": e.get_mode_display(),
        "counter_key": e.counter_key, "body_area": e.body_area,
        "config": e.config, "order": e.order,
    }


def routine_json(r):
    return {
        "uuid": str(r.uuid),
        "name": r.name,
        "subcategory": r.subcategory,
        "default_work_seconds": r.default_work_seconds,
        "default_rest_seconds": r.default_rest_seconds,
        "total_seconds": r.total_seconds,
        "items": [
            {
                "slug": i.exercise.slug,
                "name": i.exercise.name,
                "mode": i.exercise.mode,
                "counter_key": i.exercise.counter_key,
                "order": i.order,
                "work": i.effective_work_seconds,
                "rest": i.effective_rest_seconds,
                "target_sets": i.target_sets,
                "target_reps": i.target_reps,
            }
            for i in r.items.select_related("exercise")
        ],
        "updated_at": r.updated_at.isoformat(),
    }


# ------------------------------------------------------------- lectura

@api("GET")
def meta(request):
    """Catálogos fijos (categorías, días de la semana...) para que la app
    no tenga que repetirlos hardcodeados y desincronizarse del servidor."""
    return JsonResponse({
        "categories": [{"value": v, "label": l} for v, l in Task.CATEGORY_CHOICES],
        "subcategories": [{"value": v, "label": l} for v, l in Task.SUBCATEGORY_CHOICES],
        "repeats": [{"value": v, "label": l} for v, l in Task.REPEAT_CHOICES],
        "weekdays": [{"value": v, "label": l} for v, l in Task.WEEKDAYS],
        "capabilities": Task.CATEGORY_CAPABILITIES,
    })


@api("GET")
def task_list(request):
    Task.expire_overdue()
    qs = tasks_qs()
    category = request.GET.get("category")
    if category:
        qs = qs.filter(category=category)
    return JsonResponse({
        "pending": [task_json(t) for t in qs.filter(is_done=False)],
        "completed": [task_json(t) for t in qs.filter(is_done=True)],
    })


@api("GET")
def exercise_list(request):
    qs = Exercise.objects.filter(is_active=True)
    body_area = request.GET.get("body_area")
    if body_area:
        qs = qs.filter(body_area=body_area)
    return JsonResponse({"exercises": [exercise_json(e) for e in qs]})


@api("GET")
def stats_list(request):
    """Resumen por serie: rachas y totales. Mismo criterio que la web."""
    summary = {}
    for occ in Occurrence.objects.filter(user=_user()).order_by("recorded_at"):
        key = str(occ.series_id)
        s = summary.setdefault(key, {
            "series_id": key, "title": occ.title, "done": 0, "not_done": 0,
        })
        s["title"] = occ.title
        if occ.result == Occurrence.RESULT_DONE:
            s["done"] += 1
        else:
            s["not_done"] += 1
    for key, s in summary.items():
        s.update(Occurrence.streak_stats(key))
        total = s["done"] + s["not_done"]
        s["total"] = total
        s["rate"] = round(100 * s["done"] / total) if total else 0
    return JsonResponse({"stats": list(summary.values())})


# ------------------------------------------------------- escritura

def _apply_task_fields(t, data):
    """Campos editables de una tarea, validando contra los choices del
    modelo para que la app no pueda meter valores inventados."""
    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return "El título no puede estar vacío."
        t.title = title[:255]
    if "notes" in data:
        t.notes = data.get("notes") or ""
    if "category" in data:
        valid = {k for k, _ in Task.CATEGORY_CHOICES}
        t.category = data["category"] if data["category"] in valid else Task.CATEGORY_GENERAL
    if "subcategory" in data:
        valid = {k for k, _ in Task.SUBCATEGORY_CHOICES}
        t.subcategory = data["subcategory"] if data["subcategory"] in valid else ""
    if "due_date" in data:
        raw = data["due_date"]
        if not raw:
            t.due_date = None
        else:
            parsed = parse_date(raw) if isinstance(raw, str) else raw
            if parsed is None:
                return "Fecha inválida (usa AAAA-MM-DD)."
            t.due_date = parsed
    if "due_time" in data:
        raw = data["due_time"]
        if not raw:
            t.due_time = None
        else:
            parsed = parse_time(raw) if isinstance(raw, str) else raw
            if parsed is None:
                return "Hora inválida (usa HH:MM)."
            t.due_time = parsed
    if "repeat" in data:
        valid = {k for k, _ in Task.REPEAT_CHOICES}
        t.repeat = data["repeat"] if data["repeat"] in valid else Task.REPEAT_NONE
    if "interval" in data:
        try:
            t.interval = max(1, int(data["interval"]))
        except (TypeError, ValueError):
            t.interval = 1
    if "custom_days" in data:
        days = data["custom_days"] or []
        if isinstance(days, list):
            valid = {k for k, _ in Task.WEEKDAYS}
            t.custom_days = ",".join(str(d) for d in days if str(d) in valid)
    if "is_important" in data:
        t.is_important = bool(data["is_important"])
    for field, limit in (("avoid_question", 120), ("avoid_success_label", 32), ("avoid_fail_label", 32)):
        if field in data:
            setattr(t, field, (data.get(field) or "").strip()[:limit])
    return None


@api("POST")
def task_create(request):
    data = body(request)
    t = Task(user=_user())
    error = _apply_task_fields(t, data)
    if error:
        return JsonResponse({"ok": False, "error": error}, status=400)
    if not t.title:
        return JsonResponse({"ok": False, "error": "Falta el título."}, status=400)
    t.save()
    return JsonResponse({"ok": True, "task": task_json(t)}, status=201)


@api("GET", "PATCH", "DELETE")
def task_detail(request, uuid):
    t = get_object_or_404(tasks_qs(), uuid=uuid)

    if request.method == "GET":
        return JsonResponse({"task": task_json(t)})

    if request.method == "PATCH":
        error = _apply_task_fields(t, body(request))
        if error:
            return JsonResponse({"ok": False, "error": error}, status=400)
        t.save()
        return JsonResponse({"ok": True, "task": task_json(t)})

    # DELETE — borrado suave, no se borra la fila. Si se borrara de
    # verdad, el otro dispositivo no podría enterarse al sincronizar y la
    # resucitaría en la siguiente subida.
    from django.utils import timezone
    t.deleted_at = timezone.now()
    t.save(update_fields=["deleted_at", "updated_at"])
    return JsonResponse({"ok": True})


@api("POST")
def task_mark(request, uuid, action):
    t = get_object_or_404(tasks_qs(), uuid=uuid)
    if action == "done":
        t.mark_done()
    elif action == "not-done":
        t.mark_not_done()
    elif action == "failed":
        t.mark_failed()
    elif action == "reopen":
        # Deshacer: revierte la ocurrencia y la instancia futura, para que
        # las estadísticas vuelvan exactamente a como estaban.
        t.reopen()
    else:
        return JsonResponse({"ok": False, "error": "Acción desconocida"}, status=400)
    return JsonResponse({"ok": True, "task": task_json(t)})


# --------------------------------------------------------- circuitos

@api("GET", "POST")
def routine_list(request):
    if request.method == "GET":
        qs = Routine.objects.filter(user=_user(), deleted_at__isnull=True)
        subcategory = request.GET.get("subcategory")
        if subcategory:
            qs = qs.filter(subcategory=subcategory)
        return JsonResponse({"routines": [routine_json(r) for r in qs]})

    data = body(request)
    slugs = data.get("items") or []
    if not slugs:
        return JsonResponse({"ok": False, "error": "El circuito necesita al menos un ejercicio."}, status=400)

    r = Routine.objects.create(
        user=_user(),
        name=(data.get("name") or "").strip()[:64] or "Circuito sin nombre",
    )
    _apply_routine(r, data)
    return JsonResponse({"ok": True, "routine": routine_json(r)}, status=201)


def _apply_routine(r, data):
    """Campos editables de un circuito. Compartido por crear y editar."""
    name = (data.get("name") or "").strip()
    if name:
        r.name = name[:64]
    if "subcategory" in data:
        valid = {k for k, _ in Task.SUBCATEGORY_CHOICES}
        sub = data.get("subcategory") or ""
        r.subcategory = sub if sub in valid else ""
    for field in ("default_work_seconds", "default_rest_seconds"):
        if field in data:
            try:
                value = int(data[field])
            except (TypeError, ValueError):
                continue
            setattr(r, field, max(5 if "work" in field else 0, value))
    r.save()

    if "items" in data:
        raw_items = data.get("items") or []
        # Se admiten dos formatos: una lista de slugs sueltos (lo simple)
        # o una lista de objetos con los objetivos de cada ejercicio
        # {"slug": "pullup", "target_sets": 3, "target_reps": 8}. Lo
        # segundo es lo que usa el constructor de la app y lo que hará
        # falta para los planes progresivos.
        normalized = []
        for it in raw_items:
            if isinstance(it, str):
                normalized.append({"slug": it})
            elif isinstance(it, dict) and it.get("slug"):
                normalized.append(it)

        slugs = [it["slug"] for it in normalized]
        # Se admite cualquier ejercicio activo, no solo los cronometrados:
        # un circuito de tren superior (dominadas, anchas, chin ups) es
        # tan válido como uno de abdominales. Cada uno se reproduce luego
        # con lo que le toque — cámara o cronómetro.
        by_slug = {e.slug: e for e in Exercise.objects.filter(slug__in=slugs, is_active=True)}
        r.items.all().delete()
        order = 0
        for it in normalized:
            ex = by_slug.get(it["slug"])
            if not ex:
                continue

            def _int(key, default):
                try:
                    return max(1, int(it.get(key, default)))
                except (TypeError, ValueError):
                    return default

            RoutineItem.objects.create(
                routine=r, exercise=ex, order=order,
                target_sets=_int("target_sets", 3),
                target_reps=_int("target_reps", 8),
                work_seconds=it.get("work_seconds") or None,
                rest_seconds=it.get("rest_seconds") if it.get("rest_seconds") is not None else None,
            )
            order += 1
    return r


@api("GET", "PATCH", "DELETE")
def routine_detail(request, uuid):
    r = get_object_or_404(Routine.objects.filter(user=_user(), deleted_at__isnull=True), uuid=uuid)

    if request.method == "GET":
        return JsonResponse({"routine": routine_json(r)})

    if request.method == "PATCH":
        data = body(request)
        if "items" in data and not data["items"]:
            return JsonResponse(
                {"ok": False, "error": "El circuito necesita al menos un ejercicio."}, status=400
            )
        _apply_routine(r, data)
        return JsonResponse({"ok": True, "routine": routine_json(r)})

    from django.utils import timezone
    r.deleted_at = timezone.now()
    r.save(update_fields=["deleted_at", "updated_at"])
    return JsonResponse({"ok": True})


# ------------------------------------------------------ entrenamientos

@api("POST")
def workout_save(request, uuid):
    """Sesión con cámara (dominadas). Mismo formato que manda workout.js."""
    t = get_object_or_404(tasks_qs(), uuid=uuid)
    data = body(request)

    exercise_slug = data.get("exercise") or "pullup"
    rep_durations = [float(d) for d in data.get("rep_durations", []) if isinstance(d, (int, float))]
    raw_sets = data.get("sets", [])
    clean_sets = []
    if isinstance(raw_sets, list):
        for s in raw_sets:
            if isinstance(s, dict):
                clean_sets.append({
                    "reps": int(s.get("reps", 0)),
                    "durations": [float(d) for d in s.get("durations", []) if isinstance(d, (int, float))],
                })
    avg = round(sum(rep_durations) / len(rep_durations), 2) if rep_durations else None

    ws = WorkoutSession.objects.create(
        task=t, user=_user(), series_id=t.series_id, exercise=exercise_slug,
        total_reps=int(data.get("total_reps", 0)),
        total_sets=int(data.get("total_sets", len(clean_sets))),
        sets=clean_sets,
        session_duration_seconds=int(data.get("session_duration_seconds", 0)),
        avg_rep_seconds=avg,
        rest_alerts_triggered=int(data.get("rest_alerts_triggered", 0)),
        rep_durations=rep_durations,
        added_weight_kg=data.get("added_weight_kg"),
    )
    # finish=false permite guardar un ejercicio y seguir con otro en la
    # misma sesion: la tarea solo se cierra cuando el usuario lo dice.
    if data.get("finish", True):
        t.mark_done()
    return JsonResponse({"ok": True, "session_uuid": str(ws.uuid), "task": task_json(t)})


@api("POST")
def workout_save_manual(request, uuid):
    """Running: distancia/duración/pasos escritos a mano."""
    t = get_object_or_404(tasks_qs(), uuid=uuid)
    data = body(request)

    def _f(v):
        try:
            return float(str(v).replace(",", "."))
        except (TypeError, ValueError):
            return None

    distance_km = _f(data.get("distance_km"))
    duration_minutes = _f(data.get("duration_minutes"))
    if not distance_km and not duration_minutes:
        return JsonResponse({"ok": False, "error": "Pon al menos distancia o duración."}, status=400)

    pace = round((duration_minutes * 60) / distance_km, 2) if (distance_km and duration_minutes) else None
    steps = data.get("steps")
    ws = WorkoutSession.objects.create(
        task=t, user=_user(), series_id=t.series_id,
        exercise=data.get("exercise") or "running",
        session_duration_seconds=int(round(duration_minutes * 60)) if duration_minutes else 0,
        avg_rep_seconds=pace,
        distance_km=distance_km,
        steps=int(steps) if steps else None,
    )
    # finish=false permite guardar un ejercicio y seguir con otro en la
    # misma sesion: la tarea solo se cierra cuando el usuario lo dice.
    if data.get("finish", True):
        t.mark_done()
    return JsonResponse({"ok": True, "session_uuid": str(ws.uuid), "task": task_json(t)})


@api("POST")
def routine_result(request, uuid, routine_uuid):
    """Resultado de un circuito terminado (o cortado antes)."""
    t = get_object_or_404(tasks_qs(), uuid=uuid)
    r = get_object_or_404(Routine.objects.filter(user=_user()), uuid=routine_uuid)
    data = body(request)

    breakdown, total = [], 0
    for b in data.get("breakdown", []) or []:
        if not isinstance(b, dict):
            continue
        seconds = int(b.get("seconds", 0)) if isinstance(b.get("seconds"), (int, float)) else 0
        breakdown.append({"exercise": str(b.get("exercise", ""))[:32], "seconds": seconds})
        total += seconds
    if not breakdown:
        return JsonResponse({"ok": False, "error": "Sin datos que guardar"}, status=400)

    ws = WorkoutSession.objects.create(
        task=t, user=_user(), routine=r, series_id=t.series_id,
        exercise="ab-circuit", session_duration_seconds=total,
        sets=breakdown, total_sets=len(breakdown),
    )
    # finish=false permite guardar un ejercicio y seguir con otro en la
    # misma sesion: la tarea solo se cierra cuando el usuario lo dice.
    if data.get("finish", True):
        t.mark_done()
    return JsonResponse({"ok": True, "session_uuid": str(ws.uuid), "task": task_json(t)})
