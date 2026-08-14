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
import uuid
from functools import wraps

from django.db.models import Q, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from . import ai
from .models import (
    Exercise, Occurrence, Plan, PlanItem, Routine, RoutineItem, SavedVideo, Task, TimerSession, WorkoutSession,
)
from .utils import get_current_user, resolve_plan_target as _plan_context


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
        # Qué tipo de sesión abre: "camera", "timer", "distance", "focus" o
        # null. La app elige el icono con esto, para no enseñar una cámara
        # en una tarea que no va a grabar nada.
        "workout_kind": t.workout_kind,
        # Solo relevante si category="work" (Enfoque): objetivo en minutos
        # del temporizador. None = sesión libre, sin objetivo.
        "target_minutes": t.target_minutes,
        "youtube_video_id": t.youtube_video_id,
        "youtube_playlist_id": t.youtube_playlist_id,
        "target_video_count": t.target_video_count,
        "has_local_video": t.has_local_video,
        "sport_mode": t.sport_mode,
        "target_steps": t.target_steps,
        "target_distance_km": t.target_distance_km,
        "max_pace_seconds_per_km": t.max_pace_seconds_per_km,
        # Racha actual de esta serie — mismo cálculo que Rachas, para
        # poder enseñarla en la tarjeta sin ir a buscarla.
        "current_streak": t.current_streak,
        # Si la tarea la generó un plan, la app va directa a la sesión sin
        # pasar por el selector de ejercicios: el plan ya decidió.
        "plan_uuid": str(t.plan.uuid) if t.plan else None,
        "plan_name": t.plan.name if t.plan else None,
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


def _routine_item_json(i):
    """
    Un ejercicio del circuito con su objetivo YA resuelto.

    Si el ejercicio está en un plan activo manda el plan (y el objetivo
    sube solo con las sesiones); si no, mandan los números fijos del
    circuito. Así conviven plan y entrenar a tu aire. Se manda también
    `target_source` para poder decir en pantalla de dónde sale la cifra.
    """
    t = i.resolved_target()
    return {
        "slug": i.exercise.slug,
        "name": i.exercise.name,
        "mode": i.exercise.mode,
        "counter_key": i.exercise.counter_key,
        "order": i.order,
        "work": t["seconds"],
        "rest": i.effective_rest_seconds,
        "target_sets": t["sets"],
        "target_reps": t["reps"],
        "target_source": t["source"],
        "target_weight_kg": t.get("weight_kg") or 0,
        "plan_name": t["plan_name"],
        "plan_uuid": t["plan_uuid"],
        "session_index": t["session_index"],
        "sessions_to_goal": t.get("sessions_to_goal"),
    }


def routine_json(r):
    return {
        "uuid": str(r.uuid),
        "name": r.name,
        "subcategory": r.subcategory,
        "default_work_seconds": r.default_work_seconds,
        "default_rest_seconds": r.default_rest_seconds,
        "total_seconds": r.total_seconds,
        "items": [_routine_item_json(i) for i in r.items.select_related("exercise")],
        "updated_at": r.updated_at.isoformat(),
    }


# ------------------------------------------------------------- lectura

@api("GET")
def meta(request):
    """Catálogos fijos (categorías, días de la semana...) para que la app
    no tenga que repetirlos hardcodeados y desincronizarse del servidor."""
    return JsonResponse({
        "categories": [{"value": v, "label": l} for v, l in Task.CATEGORY_CHOICES],
        # Separadas porque significan cosas distintas según la categoría:
        # en Deporte filtran qué ejercicios se ofrecen; en Enfoque, qué se
        # está cronometrando. Mezclarlas en una sola lista confundiría el
        # selector (verías "Lectura" al elegir un ejercicio de deporte).
        "sport_subcategories": [{"value": v, "label": l} for v, l in Task.SPORT_SUBCATEGORY_CHOICES],
        "focus_subcategories": [{"value": v, "label": l} for v, l in Task.FOCUS_SUBCATEGORY_CHOICES],
        "repeats": [{"value": v, "label": l} for v, l in Task.REPEAT_CHOICES],
        "weekdays": [{"value": v, "label": l} for v, l in Task.WEEKDAYS],
        "capabilities": Task.CATEGORY_CAPABILITIES,
    })


@api("GET")
def task_list(request):
    Task.expire_overdue()
    Plan.auto_close_expired(user=_user())
    Plan.sync_all_tasks(user=_user())
    hoy = timezone.localtime(timezone.now()).date()
    qs = tasks_qs()
    category = request.GET.get("category")
    if category:
        qs = qs.filter(category=category)
    return JsonResponse({
        # Mismo criterio que la web: la tarea de mañana no es de hoy.
        "pending": [task_json(t) for t in Task.for_today(qs.filter(is_done=False))],
        "completed": [task_json(t) for t in Task.completed_today(qs)],
        "weekly": Occurrence.weekly_completion(_user()),
    })


@api("GET")
def exercise_list(request):
    qs = Exercise.objects.filter(is_active=True)
    body_area = request.GET.get("body_area")
    if body_area:
        qs = qs.filter(body_area=body_area)
    return JsonResponse({"exercises": [exercise_json(e) for e in qs]})


@api("GET")
def exercise_target(request, slug):
    """
    El objetivo ACTUAL de un ejercicio, si algún plan activo lo sigue.

    Hace falta como endpoint aparte porque, a diferencia de la web (que
    resuelve esto al renderizar la página en el servidor), la app móvil
    es una SPA que solo habla con la API — antes de esto no tenía forma
    de saber el objetivo hasta guardar la sesión, cuando ya era tarde
    para avisar en directo al llegar a él.
    """
    ctx = _plan_context(slug)
    return JsonResponse({
        "target_sets": ctx["target_sets"],
        "target_reps": ctx["target_reps"],
        "target_seconds": ctx["target_seconds"],
        "plan_name": ctx["plan"].name if ctx["plan"] else None,
    })


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
    return JsonResponse({
        "stats": list(summary.values()),
        "weekly": Occurrence.weekly_completion(_user()),
    })


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
    if "target_minutes" in data:
        raw = data["target_minutes"]
        if raw in (None, "", 0):
            t.target_minutes = None
        else:
            try:
                t.target_minutes = max(1, int(raw))
            except (TypeError, ValueError):
                t.target_minutes = None
    if "youtube_video_id" in data:
        # La normalización a un ID limpio la hace Task.save(), no hace
        # falta duplicarla aquí.
        t.youtube_video_id = (data.get("youtube_video_id") or "").strip()[:255]
    if "youtube_playlist_id" in data:
        t.youtube_playlist_id = (data.get("youtube_playlist_id") or "").strip()[:255]
    if "target_video_count" in data:
        raw = data["target_video_count"]
        if raw in (None, "", 0):
            t.target_video_count = None
        else:
            try:
                t.target_video_count = max(1, int(raw))
            except (TypeError, ValueError):
                t.target_video_count = None
    if "has_local_video" in data:
        t.has_local_video = bool(data.get("has_local_video"))
    if "sport_mode" in data:
        valid = {k for k, _ in Task.SPORT_MODE_CHOICES}
        t.sport_mode = data["sport_mode"] if data.get("sport_mode") in valid else ""
    for campo, minimo in (("target_steps", 1), ("target_distance_km", 0.1), ("max_pace_seconds_per_km", 1)):
        if campo in data:
            raw = data[campo]
            if raw in (None, "", 0):
                setattr(t, campo, None)
            else:
                try:
                    valor = float(raw) if campo == "target_distance_km" else int(raw)
                    if campo == "max_pace_seconds_per_km" and valor not in Task.PACE_PRESET_SECONDS:
                        # Solo se aceptan los presets del desplegable — un
                        # número suelto no dice nada de si es rápido o
                        # lento sin el contexto que da la etiqueta.
                        setattr(t, campo, None)
                    else:
                        setattr(t, campo, max(minimo, valor))
                except (TypeError, ValueError):
                    setattr(t, campo, None)
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
    # Si el cliente ya trae un uuid (offline-first, o porque generó uno
    # de antemano para poder guardar un vídeo local con esa clave antes
    # de crear la tarea), se respeta en vez de generar uno nuevo.
    raw_uuid = (data.get("uuid") or data.get("client_uuid") or "").strip()
    if raw_uuid:
        try:
            t.uuid = uuid.UUID(raw_uuid)
        except ValueError:
            pass
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
def task_mark_by_series(request, series_id, action):
    """
    Como task_mark, pero resuelve la tarea PENDIENTE actual de la serie
    en vez de una tarea concreta.

    Hace falta porque cada repetición es una fila nueva con su propio
    uuid. Una notificación local recurrente (Android la repite sola, sin
    reabrir la app) se programa una sola vez y mantiene siempre el mismo
    contenido — si apuntara al uuid de la tarea de HOY, dejaría de
    servir en cuanto esa tarea se resolviera y naciera la de mañana.
    Apuntando a la serie en su lugar, la misma notificación sigue
    resolviendo el día que toque, indefinidamente, sin depender de que
    se reabra la app para "refrescarla".
    """
    task = get_object_or_404(
        tasks_qs().filter(is_done=False), series_id=series_id
    )
    if action == "done":
        task.mark_done()
    elif action == "not-done":
        task.mark_not_done()
    elif action == "failed":
        task.mark_failed()
    else:
        return JsonResponse({"ok": False, "error": "Acción desconocida"}, status=400)
    return JsonResponse({"ok": True, "task": task_json(task)})


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


@api("POST")
def video_save(request, uuid):
    """
    El vídeo llegó al final en el móvil -> la tarea se marca hecha
    directamente. Sin sesión que guardar: la tarea ENTERA es "ver el
    vídeo", verlo entero es todo lo que hace falta.
    """
    t = get_object_or_404(tasks_qs(), uuid=uuid)
    t.mark_done()
    return JsonResponse({"ok": True, "task": task_json(t)})


# ---------------------------------------------------- vídeos guardados

def saved_video_json(v):
    return {
        "uuid": str(v.uuid), "scope": v.scope,
        "title": v.title, "youtube_video_id": v.youtube_video_id,
    }


@api("GET", "POST")
def saved_video_list(request):
    """
    GET ?scope=lower_body -> tus vídeos guardados de ese tipo, para el
    selector de tren superior/inferior/estudio.
    POST -> guarda uno nuevo (se elige justo después de crearlo, un
    paso menos que guardar y luego ir a buscarlo en la lista).
    """
    if request.method == "GET":
        qs = SavedVideo.objects.filter(user=_user(), deleted_at__isnull=True)
        scope = request.GET.get("scope")
        if scope:
            qs = qs.filter(scope=scope)
        return JsonResponse({"videos": [saved_video_json(v) for v in qs]})

    data = body(request)
    valid_scopes = {k for k, _ in SavedVideo.SCOPE_CHOICES}
    scope = data.get("scope")
    raw = (data.get("youtube_video_id") or "").strip()
    if scope not in valid_scopes:
        return JsonResponse({"ok": False, "error": "scope no válido"}, status=400)
    if not raw:
        return JsonResponse({"ok": False, "error": "Falta el enlace de YouTube"}, status=400)

    v = SavedVideo.objects.create(
        user=_user(), scope=scope, youtube_video_id=raw,
        title=(data.get("title") or "").strip()[:120],
    )
    return JsonResponse({"ok": True, "video": saved_video_json(v)}, status=201)


@api("DELETE")
def saved_video_delete(request, uuid):
    """Borrado suave, para poder limpiar la lista sin romper el historial."""
    v = get_object_or_404(SavedVideo, uuid=uuid, user=_user())
    from django.utils import timezone
    v.deleted_at = timezone.now()
    v.save(update_fields=["deleted_at"])
    return JsonResponse({"ok": True})


# ------------------------------------------------------------- enfoque

@api("POST")
def focus_save(request, uuid):
    """
    Sesión de temporizador (leer, estudiar, estirar…). El móvil manda los
    minutos ya contados y, si el subtipo es "reading" y vino del plugin
    nativo, la fuente y el paquete de la app. Mismo criterio de
    completado que workout_save: si hay objetivo y no se llega, la tarea
    se queda pendiente con el porcentaje guardado.
    """
    t = get_object_or_404(tasks_qs(), uuid=uuid)
    data = body(request)

    minutes = max(0, int(data.get("minutes", 0)))
    source = data.get("source") if data.get("source") in dict(TimerSession.SOURCE_CHOICES) else TimerSession.SOURCE_MANUAL
    app_package = (data.get("app_package") or "")[:120] if source == TimerSession.SOURCE_APP_USAGE else ""

    ts = TimerSession.objects.create(
        task=t, user=_user(), series_id=t.series_id,
        subcategory=t.subcategory, source=source, app_package=app_package,
        minutes=minutes, target_minutes=t.target_minutes,
    )
    if ts.target_met:
        t.mark_done()
    return JsonResponse({"ok": True, "session_uuid": str(ts.uuid), "task": task_json(t)})


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

    ctx = _plan_context(
        exercise_slug,
        sets=data.get("target_sets"),
        reps=data.get("target_reps"),
    )
    ws = WorkoutSession.objects.create(
        task=t, user=_user(), series_id=t.series_id, exercise=exercise_slug,
        plan=ctx["plan"], target_sets=ctx["target_sets"],
        target_reps=ctx["target_reps"], target_seconds=ctx["target_seconds"],
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
    # Y si el usuario SÍ dice que ha terminado, la tarea solo se
    # completa si llegó al objetivo — si se quedó corta, se queda
    # pendiente con el porcentaje ya guardado en la sesión, para poder
    # volver e intentarlo otra vez el mismo día.
    if data.get("finish", True) and ws.target_met:
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
def running_import(request, uuid):
    """
    Importa carreras venidas de fuera (Health Connect, y en su día OCR
    de la cinta) para una tarea de running.

    Recibe una lista, no una sola, porque al sincronizar lo natural es
    traer "todo lo de los últimos N días" de golpe: puede haber varias
    carreras, o ninguna. Las que ya se importaron antes se saltan por
    su external_id, así que sincronizar dos veces seguidas no duplica
    nada — importante, porque el móvil puede reintentar sin saber si la
    primera llamada llegó.

    Solo marca la tarea como hecha si alguna carrera cumple el ritmo
    mínimo pedido (si lo hay): correr 20 minutos andando no cuenta como
    haber hecho la tarea de correr.
    """
    t = get_object_or_404(tasks_qs(), uuid=uuid)
    data = body(request)
    runs = data.get("runs")
    if not isinstance(runs, list):
        return JsonResponse({"ok": False, "error": "Falta la lista 'runs'."}, status=400)

    source = data.get("source") or WorkoutSession.SOURCE_HEALTH_CONNECT
    valid_sources = {k for k, _ in WorkoutSession.SOURCE_CHOICES}
    if source not in valid_sources:
        source = WorkoutSession.SOURCE_HEALTH_CONNECT

    def _f(v):
        try:
            return float(str(v).replace(",", "."))
        except (TypeError, ValueError):
            return None

    # Los objetivos viven en la tarea, no en la petición: así el móvil
    # solo manda "esto es lo que hice" y el servidor decide si cuenta —
    # un solo sitio donde está la regla, y cambiarla en la tarea aplica
    # sin tener que actualizar la app.
    max_pace = t.max_pace_seconds_per_km
    min_steps = t.target_steps
    min_distance = t.target_distance_km

    imported, skipped, qualifying = [], 0, 0
    total_steps, total_distance = 0, 0.0
    for run in runs:
        if not isinstance(run, dict):
            continue
        external_id = str(run.get("external_id") or "").strip()[:120]
        if external_id and WorkoutSession.objects.filter(
            user=_user(), external_id=external_id, deleted_at__isnull=True
        ).exists():
            skipped += 1
            continue

        distance_km = _f(run.get("distance_km"))
        duration_seconds = _f(run.get("duration_seconds"))
        steps_raw = run.get("steps")
        try:
            steps = int(steps_raw) if steps_raw else None
        except (TypeError, ValueError):
            steps = None
        if not distance_km and not duration_seconds and not steps:
            continue

        pace = round(duration_seconds / distance_km, 2) if (distance_km and duration_seconds) else None
        ws = WorkoutSession.objects.create(
            task=t, plan=t.plan, user=_user(), series_id=t.series_id,
            exercise=run.get("exercise") or t.subcategory or "running",
            session_duration_seconds=int(round(duration_seconds)) if duration_seconds else 0,
            avg_rep_seconds=pace,
            distance_km=distance_km,
            steps=steps,
            source=source,
            external_id=external_id,
            # Objetivo vigente en ESE momento — si viene de un plan que
            # progresa semana a semana, esto deja constancia de qué se
            # pedía entonces, no de lo que se pide ahora.
            target_distance_km=min_distance,
            target_pace_seconds_per_km=max_pace,
        )
        imported.append(str(ws.uuid))
        total_steps += steps or 0
        # La distancia solo cuenta si la carrera se hizo al ritmo pedido:
        # el objetivo es "5 km a 6:30/km", no "5 km O 6:30/km". Andar 5 km
        # muy despacio no completa una tarea de correr.
        cumple_ritmo = max_pace is None or (pace is not None and pace <= max_pace)
        if cumple_ritmo:
            total_distance += distance_km or 0
            # Con ritmo pedido pero sin distancia, basta con una carrera
            # que dé ese ritmo.
            if max_pace is not None and min_distance is None and pace is not None:
                qualifying += 1

    # Pasos y distancia se acumulan a lo largo del día: 10.000 pasos en
    # tres paseos cuentan igual que en uno. Y hay que contar TODO lo de
    # hoy, no solo lo de esta tanda — si sincronizas a mediodía y otra
    # vez por la tarde, la segunda solo trae lo nuevo.
    if min_steps is not None:
        hoy = timezone.localtime(timezone.now()).date()
        de_hoy = WorkoutSession.objects.filter(
            user=_user(), series_id=t.series_id,
            recorded_at__date=hoy, deleted_at__isnull=True,
        )
        total_steps = de_hoy.aggregate(pasos=Sum("steps"))["pasos"] or 0

    if min_steps is not None and total_steps >= min_steps:
        qualifying += 1
    if min_distance is not None and total_distance >= min_distance:
        qualifying += 1
    # Sin ningún objetivo puesto, basta con haber hecho algo.
    if max_pace is None and min_steps is None and min_distance is None and imported:
        qualifying += 1

    # Solo se da por hecha si de verdad se cumplió algún objetivo.
    if qualifying:
        t.mark_done()
        # Si venía de un plan, el escalón puede haber subido con esta
        # sesión — se refresca ya, no hay que esperar a la próxima
        # carga de la lista para que la tarea de mañana traiga el
        # objetivo correcto.
        plan = t.plan
        if plan:
            plan.sync_task()

    return JsonResponse({
        "ok": True,
        "imported": len(imported),
        "skipped": skipped,
        "qualifying": qualifying,
        "total_steps": total_steps,
        "total_distance_km": round(total_distance, 2),
        "session_uuids": imported,
        "task": task_json(t),
    })


@api("POST")
def routine_result(request, uuid, routine_uuid):
    """
    Resultado de un circuito terminado (o cortado antes).

    Se guarda UNA SESIÓN POR EJERCICIO, no una sola con todo dentro. Dos
    motivos: la progresión del plan cuenta sesiones por ejercicio, así que
    metiéndolo todo junto los ejercicios del circuito nunca avanzarían; y
    antes se perdían las repeticiones de los ejercicios de cámara, que
    llegaban en el desglose y se tiraban.

    Todas quedan enlazadas al mismo circuito (campo `routine`), así que se
    puede reconstruir la sesión completa cuando haga falta.
    """
    t = get_object_or_404(tasks_qs(), uuid=uuid)
    r = get_object_or_404(Routine.objects.filter(user=_user()), uuid=routine_uuid)
    data = body(request)

    def _num(b, key):
        return int(b[key]) if isinstance(b.get(key), (int, float)) else 0

    entries = []
    for b in data.get("breakdown", []) or []:
        if not isinstance(b, dict):
            continue
        slug = str(b.get("exercise", ""))[:32]
        if slug:
            entries.append({
                "exercise": slug,
                "seconds": _num(b, "seconds"),
                "reps": _num(b, "reps"),
                "sets": _num(b, "sets"),
            })
    if not entries:
        return JsonResponse({"ok": False, "error": "Sin datos que guardar"}, status=400)

    created, total_seconds = [], 0
    for e in entries:
        ctx = _plan_context(e["exercise"])
        created.append(WorkoutSession.objects.create(
            task=t, user=_user(), routine=r, series_id=t.series_id,
            plan=ctx["plan"], target_sets=ctx["target_sets"],
            target_reps=ctx["target_reps"], target_seconds=ctx["target_seconds"],
            exercise=e["exercise"],
            total_reps=e["reps"], total_sets=e["sets"],
            session_duration_seconds=e["seconds"],
        ))
        total_seconds += e["seconds"]

    # finish=false permite guardar y seguir en la misma sesion: la tarea
    # solo se cierra cuando el usuario lo dice.
    if data.get("finish", True):
        t.mark_done()

    return JsonResponse({
        "ok": True,
        "sessions": [
            {
                "exercise": w.exercise, "name": w.exercise_name,
                "reps": w.total_reps, "seconds": w.session_duration_seconds,
                "target": w.target_label, "achievement_pct": w.achievement_pct,
            }
            for w in created
        ],
        "total_seconds": total_seconds,
        "task": task_json(t),
    })


# ─────────────────────────────────────────────────────────────────────
# Planes
# ─────────────────────────────────────────────────────────────────────

def plan_json(p, detail=False):
    head = p.headline

    def _item(it):
        t = it.current_target()
        return {
            "id": it.pk,
            "name": it.display_name,
            "label": it.label,
            "slug": it.exercise.slug if it.exercise else None,
            "progression": it.progression,
            "is_headline": it.is_headline,
            "target_sets": t["sets"],
            "target_reps": t["reps"],
            "target_seconds": t["seconds"],
            "target_weight_kg": t["weight_kg"],
            "target_distance_km": t.get("distance_km"),
            "target_pace_seconds_per_km": t.get("pace_seconds_per_km"),
            "step": it.current_step(),
            "remaining": it.sessions_to_goal(),
            "done": t["done"],
            # Para poder rellenar el formulario de edición sin tener que
            # deshacer la progresión — estos son los valores tal cual se
            # guardaron, no el escalón actual.
            "start_sets": it.start_sets, "start_reps": it.start_reps,
            "start_seconds": it.start_seconds, "start_weight_kg": it.start_weight_kg,
            "goal_sets": it.goal_sets, "goal_reps": it.goal_reps,
            "goal_seconds": it.goal_seconds, "goal_weight_kg": it.goal_weight_kg,
            "start_distance_km": it.start_distance_km,
            "start_pace_seconds_per_km": it.start_pace_seconds_per_km,
            "goal_distance_km": it.goal_distance_km,
            "goal_pace_seconds_per_km": it.goal_pace_seconds_per_km,
            "distance_increment_km": it.distance_increment_km,
            "pace_decrement_seconds": it.pace_decrement_seconds,
            "sessions_per_step": it.sessions_per_step,
            "reps_increment": it.reps_increment,
            "weight_increment_kg": it.weight_increment_kg,
            "rep_range_low": it.rep_range_low,
            "deload_after_failures": it.deload_after_failures,
            "sport_mode": it.sport_mode,
            "youtube_video_id": it.youtube_video_id,
            "youtube_playlist_id": it.youtube_playlist_id,
            "target_minutes": it.target_minutes,
            "target_video_count": it.target_video_count,
        }

    data = {
        "uuid": str(p.uuid),
        "id": p.pk,
        "name": p.name,
        "notes": p.notes,
        "plan_type": p.plan_type,
        "week": p.week_number,
        "weeks": p.weeks,
        "started_on": p.started_on.isoformat(),
        "ends_on": p.ends_on.isoformat(),
        "is_active": p.is_active,
        "closed_at": p.closed_at.isoformat() if p.closed_at else None,
        "is_completed": p.is_completed if p.closed_at else None,
        "reward": p.reward,
        "progress_pct": p.progress_pct(),
        "custom_days": p.custom_days_list(),
        "due_time": p.due_time.strftime("%H:%M") if p.due_time else None,
        "headline": _item(head) if head else None,
    }
    if detail:
        data["items"] = [_item(i) for i in p.items.select_related("exercise")]
        data["schedule"] = head.schedule(60) if head else []
        data["history"] = head.history(12) if head else []
    return data


def plans_qs():
    return Plan.objects.filter(user=_user(), deleted_at__isnull=True)


@api("GET")
def plan_list(request):
    return JsonResponse({"plans": [plan_json(p) for p in plans_qs()]})


@api("GET")
def weekly_review(request):
    """
    Mismo contenido que la revisión semanal de la web: el global y,
    para cada objetivo activo, su ejecución de esta semana y cuánto
    lleva recorrido.
    """
    plans = []
    for p in plans_qs().filter(is_active=True):
        plans.append({
            "uuid": str(p.uuid),
            "id": p.pk,
            "name": p.name,
            "week": p.week_number,
            "weeks": p.weeks,
            "progress_pct": p.progress_pct(),
            "weekly": p.weekly_completion(),
        })
    return JsonResponse({
        "weekly": Occurrence.weekly_completion(_user()),
        "plans": plans,
    })


@api("GET", "PATCH", "DELETE")
def plan_detail(request, uuid):
    p = get_object_or_404(plans_qs(), uuid=uuid)

    if request.method == "GET":
        return JsonResponse({"plan": plan_json(p, detail=True)})

    if request.method == "PATCH":
        error = _apply_plan_fields(p, body(request))
        if error:
            return JsonResponse({"ok": False, "error": error}, status=400)
        p.save()
        p.sync_task()
        return JsonResponse({"ok": True, "plan": plan_json(p, detail=True)})

    # DELETE — borrado suave, igual que en la web.
    p.deleted_at = timezone.now()
    p.save(update_fields=["deleted_at", "updated_at"])
    p.sync_task()
    return JsonResponse({"ok": True})


def _apply_plan_fields(p, data):
    """Comparte lógica entre crear y editar — mismo patrón que _apply_task_fields."""
    if "name" in data:
        name = (data.get("name") or "").strip()[:80]
        if not name:
            return "Falta el nombre."
        p.name = name
    if "notes" in data:
        p.notes = (data.get("notes") or "").strip()
    if "started_on" in data:
        raw = data["started_on"]
        parsed = parse_date(raw) if isinstance(raw, str) else raw
        p.started_on = parsed or p.started_on or timezone.localtime(timezone.now()).date()
    elif not p.pk:
        p.started_on = timezone.localtime(timezone.now()).date()
    if "weeks" in data:
        try:
            p.weeks = max(1, int(data["weeks"]))
        except (TypeError, ValueError):
            p.weeks = 12
    if "is_active" in data:
        p.is_active = bool(data["is_active"])
    if "reward" in data:
        p.reward = (data.get("reward") or "").strip()[:200]
    p.repeat = "custom"
    if "custom_days" in data:
        days = data["custom_days"] or []
        if isinstance(days, list):
            valid = {k for k, _ in Task.WEEKDAYS}
            p.custom_days = ",".join(str(d) for d in days if str(d) in valid) or "0,2,4"
    if "due_time" in data:
        raw = data["due_time"]
        parsed = parse_time(raw) if isinstance(raw, str) else raw
        p.due_time = parsed
    return None


@api("POST")
def plan_create(request):
    data = body(request)
    p = Plan(user=_user())
    # El tipo solo se decide al crear — igual que en la web, cambiarlo
    # después dejaría objetivos huérfanos que ya no encajan.
    valid_types = {k for k, _ in Plan.PLAN_TYPE_CHOICES}
    raw_type = data.get("plan_type")
    p.plan_type = raw_type if raw_type in valid_types else Plan.PLAN_TYPE_SPORT

    error = _apply_plan_fields(p, data)
    if error:
        return JsonResponse({"ok": False, "error": error}, status=400)
    if not p.name:
        return JsonResponse({"ok": False, "error": "Falta el nombre."}, status=400)

    p.save()
    p.sync_task()
    return JsonResponse({"ok": True, "plan": plan_json(p, detail=True)}, status=201)


@api("POST")
def plan_close(request, uuid):
    """
    Cierre de ciclo — mismo mecanismo que la web: guarda el progreso
    final y desactiva el plan, pero no lo borra (se queda para poder
    mirar atrás).
    """
    p = get_object_or_404(plans_qs(), uuid=uuid)
    if not p.closed_at:
        p.final_progress_pct = p.progress_pct()
        p.closed_at = timezone.now()
        p.is_active = False
        p.save(update_fields=["final_progress_pct", "closed_at", "is_active", "updated_at"])
        p.sync_task()
    return JsonResponse({"ok": True, "plan": plan_json(p, detail=True)})


def _apply_video_fields(item, data):
    """Vídeo/playlist/temporizador — compartido entre un objetivo de
    Estudio (siempre) y uno de Deporte con sport_mode='video'."""
    if "youtube_video_id" in data:
        item.youtube_video_id = (data.get("youtube_video_id") or "").strip()[:255]
    if "youtube_playlist_id" in data:
        item.youtube_playlist_id = (data.get("youtube_playlist_id") or "").strip()[:255]
    for field, minimo in (("target_minutes", 1), ("target_video_count", 1)):
        if field in data:
            raw = data[field]
            if raw in (None, "", 0):
                setattr(item, field, None)
            else:
                try:
                    setattr(item, field, max(minimo, int(raw)))
                except (TypeError, ValueError):
                    setattr(item, field, None)


def _apply_plan_item_fields(item, plan, data):
    """
    Qué campos aplican depende de plan.plan_type — mismo reparto que el
    formulario web: Estudio lleva vídeo/playlist/temporizador y se
    enlaza solo a la tarea diaria del plan; Deporte lleva ejercicio y
    progresión (incluida distancia/ritmo para running, y cámara/
    circuito/vídeo para el resto).
    """
    if plan.plan_type == Plan.PLAN_TYPE_STUDY:
        item.exercise = None
        item.series_id = plan.task_series_id
        item.progression = PlanItem.PROG_COMPLETION
        item.is_headline = True
        if "label" in data:
            item.label = (data.get("label") or "").strip()[:80]
        _apply_video_fields(item, data)
        return None

    # Deporte, a partir de aquí.
    if "exercise" in data:
        slug = data.get("exercise") or ""
        item.exercise = Exercise.objects.filter(slug=slug).first() if slug else None
    if "label" in data:
        item.label = (data.get("label") or "").strip()[:80]

    # Cómo se hace el ejercicio — no aplica a running, que siempre se
    # resuelve por Health Connect / a mano, nunca con cámara ni vídeo.
    es_running = item.exercise and item.exercise.mode == Exercise.MODE_DISTANCE
    if es_running:
        item.sport_mode = ""
    elif "sport_mode" in data:
        valid_modes = {k for k, _ in PlanItem.SPORT_MODE_CHOICES}
        raw_mode = data.get("sport_mode") or ""
        item.sport_mode = raw_mode if raw_mode in valid_modes else ""
    if item.sport_mode == PlanItem.SPORT_MODE_VIDEO:
        _apply_video_fields(item, data)

    default_prog = (
        PlanItem.PROG_DISTANCE if item.exercise and item.exercise.mode == Exercise.MODE_DISTANCE
        else PlanItem.PROG_REPS
    )
    valid = {k for k, _ in PlanItem.PROGRESSION_CHOICES}
    prog = data.get("progression", default_prog)
    item.progression = prog if prog in valid else default_prog

    def _int(name, default):
        try:
            return max(0, int(data.get(name) if data.get(name) not in (None, "") else default))
        except (TypeError, ValueError):
            return default

    def _float(name, default):
        try:
            return max(0.0, float(data.get(name) if data.get(name) not in (None, "") else default))
        except (TypeError, ValueError):
            return default

    item.start_sets = _int("start_sets", 3) or 1
    item.start_reps = _int("start_reps", 8)
    item.start_seconds = _int("start_seconds", 40)
    item.start_weight_kg = _float("start_weight_kg", 0)
    item.goal_sets = _int("goal_sets", 0) or None
    item.goal_reps = _int("goal_reps", 0) or None
    item.goal_seconds = _int("goal_seconds", 0) or None
    item.goal_weight_kg = _float("goal_weight_kg", 0) if data.get("goal_weight_kg") else None

    item.start_distance_km = _float("start_distance_km", 1.0) or 1.0
    item.start_pace_seconds_per_km = _int("start_pace_seconds_per_km", 420) or 420
    item.goal_distance_km = _float("goal_distance_km", 0) if data.get("goal_distance_km") else None
    item.goal_pace_seconds_per_km = _int("goal_pace_seconds_per_km", 0) if data.get("goal_pace_seconds_per_km") else None
    item.distance_increment_km = _float("distance_increment_km", 0.5) or 0.5
    item.pace_decrement_seconds = _int("pace_decrement_seconds", 10) or 10

    item.sessions_per_step = _int("sessions_per_step", 2) or 1
    item.reps_increment = _int("reps_increment", 1) or 1
    item.weight_increment_kg = _float("weight_increment_kg", 2.5) or 2.5
    item.rep_range_low = _int("rep_range_low", 6) or 1
    item.deload_after_failures = _int("deload_after_failures", 3)
    if "is_headline" in data:
        item.is_headline = bool(data["is_headline"])

    # Obligatorio de verdad: sin esto, un objetivo se podía guardar
    # "vacío" y al pulsar play la app no sabía qué pantalla enseñar.
    if not item.exercise:
        return "Elige un ejercicio."
    if es_running and not item.goal_distance_km:
        return "Pon una distancia de destino — sin eso el plan no sabría cuándo has llegado."
    if not es_running and not item.sport_mode:
        return "Elige cómo la vas a completar: cámara, circuito o vídeo."
    if item.sport_mode == PlanItem.SPORT_MODE_VIDEO and not (item.youtube_video_id or item.youtube_playlist_id):
        return "Pon un vídeo o una playlist de YouTube."
    return None


@api("POST")
def plan_item_create(request, uuid):
    plan = get_object_or_404(plans_qs(), uuid=uuid)
    if plan.plan_type == Plan.PLAN_TYPE_GENERAL:
        return JsonResponse({"ok": False, "error": "Un plan General no necesita objetivos."}, status=400)
    item = PlanItem(plan=plan)
    error = _apply_plan_item_fields(item, plan, body(request))
    if error:
        return JsonResponse({"ok": False, "error": error}, status=400)
    item.save()
    if item.is_headline:
        plan.items.exclude(pk=item.pk).update(is_headline=False)
    plan.sync_task()
    return JsonResponse({"ok": True, "plan": plan_json(plan, detail=True)}, status=201)


@api("PATCH", "DELETE")
def plan_item_detail(request, uuid, item_id):
    plan = get_object_or_404(plans_qs(), uuid=uuid)
    item = get_object_or_404(PlanItem, pk=item_id, plan=plan)

    if request.method == "DELETE":
        item.delete()
        plan.sync_task()
        return JsonResponse({"ok": True, "plan": plan_json(plan, detail=True)})

    error = _apply_plan_item_fields(item, plan, body(request))
    if error:
        return JsonResponse({"ok": False, "error": error}, status=400)
    item.save()
    if item.is_headline:
        plan.items.exclude(pk=item.pk).update(is_headline=False)
    plan.sync_task()
    return JsonResponse({"ok": True, "plan": plan_json(plan, detail=True)})


def build_plan_draft(*, user, plan_type, weeks, custom_days, prompt):
    """
    El núcleo de "generar plan con IA", compartido por el endpoint JSON
    (`plan_generate`, para la app móvil) y la vista web (`views.plan_ai_form`)
    — así un plan de IA se construye y se valida exactamente igual venga
    de donde venga, en vez de mantener la lógica duplicada en dos sitios.

    No guarda nada: construye Plan/PlanItem SIN GUARDAR y les aplica
    `_apply_plan_fields` / `_apply_plan_item_fields` — las mismas que usa
    la creación manual — así que el borrador ya viene validado y saneado.

    Devuelve `(draft_dict, None)` o `(None, mensaje_de_error)`.
    """
    valid_types = {k for k, _ in Plan.PLAN_TYPE_CHOICES}
    plan_type = plan_type if plan_type in valid_types else Plan.PLAN_TYPE_SPORT

    try:
        weeks = max(1, int(weeks or 12))
    except (TypeError, ValueError):
        weeks = 12

    valid_days = {k for k, _ in Task.WEEKDAYS}
    days = [str(d) for d in (custom_days or []) if str(d) in valid_days]
    custom_days = days or ["0", "2", "4"]
    sessions_per_week = max(1, len(custom_days))

    try:
        raw = ai.generate_plan_draft(
            prompt=prompt or "", plan_type=plan_type,
            weeks=weeks, sessions_per_week=sessions_per_week,
        )
    except ai.PlanAIError as e:
        return None, str(e)

    plan_fields = {
        "name": (raw.get("plan") or {}).get("name") or "",
        "notes": (raw.get("plan") or {}).get("notes") or "",
        "weeks": weeks,
        "custom_days": [int(d) for d in custom_days],
        "started_on": timezone.localtime(timezone.now()).date().isoformat(),
        "is_active": True,
    }
    draft_plan = Plan(user=user, plan_type=plan_type)
    error = _apply_plan_fields(draft_plan, plan_fields)
    if error:
        return None, f"La IA devolvió un plan inválido: {error}"

    items_out = []
    if plan_type != Plan.PLAN_TYPE_GENERAL:
        for raw_item in (raw.get("items") or []):
            if not isinstance(raw_item, dict):
                continue
            if plan_type == Plan.PLAN_TYPE_STUDY:
                item_fields = {
                    "label": (raw_item.get("label") or "").strip()[:80],
                    "target_minutes": raw_item.get("target_minutes") or None,
                }
                exercise = None
            else:
                exercise = Exercise.objects.filter(slug=raw_item.get("exercise_slug") or "").first()
                item_fields = dict(raw_item)
                item_fields.pop("exercise_slug", None)
                item_fields["exercise"] = exercise.slug if exercise else ""
                item_fields["sport_mode"] = PlanItem.SPORT_MODE_CIRCUIT
                ai.apply_pacing(item_fields, exercise=exercise, sessions_per_week=sessions_per_week)

            draft_item = PlanItem(plan=draft_plan)
            item_error = _apply_plan_item_fields(draft_item, draft_plan, item_fields)
            if item_error:
                continue  # se descarta el objetivo inválido en vez de tirar todo el plan
            items_out.append({
                "fields": item_fields,
                "preview": {
                    "display_name": draft_item.display_name,
                    "is_headline": bool(draft_item.is_headline),
                    "progression": draft_item.progression,
                    "is_timed": bool(exercise and exercise.mode == Exercise.MODE_TIMED),
                    "is_running": bool(exercise and exercise.mode == Exercise.MODE_DISTANCE),
                    "exercise_name": exercise.name if exercise else "",
                    "weekly": draft_item.weekly_schedule(weeks, sessions_per_week),
                },
            })

        # Exactamente una medida principal — si la IA no marcó ninguna (o
        # marcó varias), se decide aquí en vez de dejarlo a medias.
        headline_idxs = [i for i, it in enumerate(items_out) if it["fields"].get("is_headline")]
        if items_out and not headline_idxs:
            items_out[0]["fields"]["is_headline"] = True
            items_out[0]["preview"]["is_headline"] = True
        elif len(headline_idxs) > 1:
            for i in headline_idxs[1:]:
                items_out[i]["fields"]["is_headline"] = False
                items_out[i]["preview"]["is_headline"] = False

        if not items_out:
            return None, "La IA no propuso ningún objetivo válido. Prueba a describir el objetivo de otra forma."

    return {"plan_type": plan_type, "plan_fields": plan_fields, "items": items_out}, None


@api("POST")
def plan_generate(request):
    """
    Genera un BORRADOR de plan con IA a partir de un prompt en texto
    libre — no guarda nada. El usuario lo revisa en la app y, si le vale,
    lo confirma llamando a los mismos `plan_create` / `plan_item_create`
    de siempre con los campos de `draft.plan_fields` / `draft.items[].fields`.
    """
    data = body(request)
    draft, error = build_plan_draft(
        user=_user(), plan_type=data.get("plan_type"), weeks=data.get("weeks"),
        custom_days=data.get("custom_days"), prompt=data.get("prompt"),
    )
    if error:
        return JsonResponse({"ok": False, "error": error}, status=502)
    return JsonResponse({"ok": True, "draft": draft})


@api("GET")
def plan_session(request, uuid, plan_uuid):
    """
    La sesión de hoy según el plan: sus ejercicios con el objetivo que
    toca. No hay nada que elegir — el plan ya lo decidió.
    """
    task = get_object_or_404(tasks_qs(), uuid=uuid)
    plan = get_object_or_404(plans_qs(), uuid=plan_uuid)
    return JsonResponse({
        "plan": plan_json(plan),
        "task": task_json(task),
        "items": plan.session_items(),
    })


@api("POST")
def plan_session_save(request, uuid, plan_uuid):
    """Guarda la sesión del plan: una entrada por ejercicio, con el
    objetivo vigente. Al terminar la tarea queda hecha y el plan avanza."""
    task = get_object_or_404(tasks_qs(), uuid=uuid)
    plan = get_object_or_404(plans_qs(), uuid=plan_uuid)
    data = body(request)

    targets = {
        it.exercise.slug: it.current_target()
        for it in plan.items.select_related("exercise") if it.exercise
    }

    def _num(b, key):
        return int(b[key]) if isinstance(b.get(key), (int, float)) else 0

    created = []
    for b in data.get("breakdown", []) or []:
        if not isinstance(b, dict):
            continue
        slug = str(b.get("exercise", ""))[:32]
        if not slug:
            continue
        t = targets.get(slug, {})
        created.append(WorkoutSession.objects.create(
            task=task, user=_user(), plan=plan, series_id=task.series_id,
            exercise=slug,
            total_reps=_num(b, "reps"), total_sets=_num(b, "sets"),
            session_duration_seconds=_num(b, "seconds"),
            target_sets=t.get("sets"), target_reps=t.get("reps"),
            target_seconds=t.get("seconds"),
        ))

    if not created:
        return JsonResponse({"ok": False, "error": "Sin datos que guardar"}, status=400)

    if data.get("finish", True):
        task.mark_done()

    return JsonResponse({
        "ok": True,
        "sessions": [
            {
                "exercise": w.exercise, "name": w.exercise_name,
                "reps": w.total_reps, "seconds": w.session_duration_seconds,
                "target": w.target_label, "achievement_pct": w.achievement_pct,
            }
            for w in created
        ],
        "task": task_json(task),
    })
