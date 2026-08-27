import json

from django.contrib import messages
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

import datetime as _dt
import uuid as _uuid

from django.utils import timezone

from . import ai, api
from .models import (
    CourseQuiz, Exercise, Occurrence, Plan, PlanItem, Routine, RoutineItem, SavedVideo, Task,
    TimerSession, WarmupStatus, WorkoutSession,
)
from .utils import get_current_user, read_mobile_release, resolve_plan_target
from urllib.parse import quote


# Vídeos fijos de calentamiento/enfriamiento — obligatorios en toda
# sesión de Deporte (ver _require_warmup, task_warmup y task_cooldown).
# Cambiar el ID aquí para usar otro vídeo, sin tocar nada de lógica.
WARMUP_VIDEO_ID = "1YY0xyCgITc"
COOLDOWN_VIDEO_ID = "r5QG2Lq1oUo"


def _require_warmup(request, task):
    """
    Punto de entrada común a task_workout, routine_play y plan_session
    (las tres formas de empezar a entrenar): si la tarea es de Deporte
    y no se ha calentado hace poco (WarmupStatus.FRESH_WINDOW), corta
    el paso y manda al vídeo de calentamiento, con ?next= para volver
    exactamente a donde se iba. Devuelve None si se puede seguir tal cual.
    """
    if task.category != Task.CATEGORY_SPORT:
        return None
    if task.subcategory == Task.SUBCATEGORY_RUNNING:
        # Running no se cuenta con la cámara ni con un circuito: la
        # sesión ya queda validada por datos reales (distancia/tiempo,
        # Health Connect...), así que no hace falta el vídeo.
        return None
    if WarmupStatus.is_fresh(get_current_user()):
        return None
    warmup_url = reverse("tasks:task_warmup", args=[task.pk])
    return redirect(f"{warmup_url}?next={quote(request.get_full_path())}")


def _read_category(request, default=Task.CATEGORY_GENERAL):
    """Lee la categoría del POST/GET, validando contra choices."""
    raw = request.POST.get("category", default) or default
    valid = {key for key, _ in Task.CATEGORY_CHOICES}
    return raw if raw in valid else default


def _read_subcategory(request, default=""):
    """Lee la subcategoría (deporte o enfoque, según la categoría)."""
    raw = request.POST.get("subcategory", default) or default
    valid = {key for key, _ in Task.SUBCATEGORY_CHOICES}
    return raw if raw in valid else default


def _read_language_name(request):
    """Idioma de una tarea suelta con subcategory=Idiomas (Task.language_name)."""
    return request.POST.get("language_name", "").strip()[:40]


def _read_level(request):
    """Nivel MCER de una tarea suelta con subcategory=Idiomas (Task.level)."""
    raw = request.POST.get("level", "")
    valid = {k for k, _ in Task.CEFR_LEVEL_CHOICES}
    return raw if raw in valid else ""


def _read_target_minutes(request):
    """
    Objetivo en minutos — un solo campo en el modelo (Task.target_minutes)
    sirve para dos cosas distintas según cuál aplique: minutos del
    temporizador de Enfoque, o minutos vistos de un vídeo/playlist. En
    el formulario son dos inputs separados (para no chocar cuando los
    dos son visibles a la vez, con category=work + vídeo puesto), pero
    aquí se funden en el campo que de verdad toca.
    """
    has_video = bool(request.POST.get("youtube_video_id", "").strip()) \
        or bool(request.POST.get("youtube_playlist_id", "").strip())
    field = "video_target_minutes" if has_video else "target_minutes"
    raw = request.POST.get(field, "").strip()
    if not raw:
        return None
    try:
        return max(1, int(raw))
    except ValueError:
        return None


def _read_youtube_video_id(request):
    """
    Enlace de YouTube pegado tal cual — la normalización a un ID limpio
    la hace Task.save(), no hace falta duplicarla aquí.
    """
    return request.POST.get("youtube_video_id", "").strip()[:255]


def _read_youtube_playlist_id(request):
    return request.POST.get("youtube_playlist_id", "").strip()[:255]


def _read_target_video_count(request):
    """Cuántos vídeos de la playlist hay que ver. Vacío = sin objetivo por cuenta."""
    raw = request.POST.get("target_video_count", "").strip()
    if not raw:
        return None
    try:
        return max(1, int(raw))
    except ValueError:
        return None


def _read_sport_mode(request):
    """Cómo se completa una tarea de Deporte: cámara, circuito o vídeo."""
    raw = request.POST.get("sport_mode", "").strip()
    valid = {k for k, _ in Task.SPORT_MODE_CHOICES}
    return raw if raw in valid else ""


def _read_target_steps(request):
    raw = request.POST.get("target_steps", "").strip()
    if not raw:
        return None
    try:
        return max(1, int(raw))
    except ValueError:
        return None


def _read_target_distance_km(request):
    raw = request.POST.get("target_distance_km", "").strip().replace(",", ".")
    if not raw:
        return None
    try:
        return max(0.1, float(raw))
    except ValueError:
        return None


def _read_max_pace(request):
    """
    Ritmo máximo. El formulario ya no pide "6:30" a mano — eso no dice
    nada a quien no corre — sino que ofrece un desplegable con opciones
    en lenguaje llano (paseo tranquilo, correr rápido…) que ya llevan el
    número por dentro. Aquí solo se valida que sea uno de los que existen.
    """
    raw = request.POST.get("max_pace_seconds_per_km", "").strip()
    if not raw:
        return None
    try:
        val = int(raw)
    except ValueError:
        return None
    return val if val in Task.PACE_PRESET_SECONDS else None


def _read_has_local_video(request):
    """El formulario eligió 'archivo de mi dispositivo' en vez de YouTube."""
    return bool(request.POST.get("has_local_video"))


def _read_client_uuid(request):
    """
    UUID generado en el propio navegador (crypto.randomUUID()) ANTES de
    guardar la tarea — solo así el selector de archivo local puede
    guardar el archivo con la clave correcta desde el primer momento,
    sin esperar a que el servidor invente un id que el JS no conocería
    todavía. Si no llega uno válido (formularios viejos, o simplemente
    porque no se eligió vídeo local), Task.save() genera el suyo como
    siempre — esto es un añadido, no un requisito.
    """
    raw = request.POST.get("client_uuid", "").strip()
    if not raw:
        return None
    try:
        return _uuid.UUID(raw)
    except ValueError:
        return None


def task_list(request):
    # Se comprueba en cada visita si alguna tarea con hora límite ya
    # venció sin completarse, y se marca sola como "no hecha".
    # (No usamos cron: en el hosting gratuito no está disponible, y al
    # ser una app de un solo usuario, comprobarlo al abrir la página
    # es suficiente.)
    Task.expire_overdue()
    Plan.auto_close_expired(user=get_current_user())
    Plan.sync_all_tasks(user=get_current_user())

    # Filtro opcional por categoría (?cat=sport, ?cat=study, …)
    cat = request.GET.get("cat") or ""
    valid_cats = {key for key, _ in Task.CATEGORY_CHOICES}
    active_category = cat if cat in valid_cats else ""

    base_qs = Task.objects.filter(user=get_current_user())
    if active_category:
        base_qs = base_qs.filter(category=active_category)

    # for_today evita que la tarea de mañana (generada al resolver la de
    # hoy) aparezca ya en la lista y se pueda marcar dos veces.
    pending_tasks = Task.for_today(base_qs.filter(is_done=False))
    completed_tasks = Task.completed_today(base_qs)

    # Conteos por categoría para los chips de filtro
    counts = dict(
        Task.objects.filter(user=get_current_user())
        .values_list("category").annotate(n=Count("id")).values_list("category", "n")
    )
    category_counts = [
        {"key": key, "label": label, "count": counts.get(key, 0)}
        for key, label in Task.CATEGORY_CHOICES
    ]

    return render(request, "tasks/task_list.html", {
        "pending_tasks": pending_tasks,
        "completed_tasks": completed_tasks,
        "category_choices": Task.CATEGORY_CHOICES,
        "active_category": active_category,
        "category_counts": category_counts,
        "total_task_count": sum(counts.values()),
        "weekly": Occurrence.weekly_completion(get_current_user()),
    })


def task_create(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        due_time = request.POST.get("due_time") or None
        if not title:
            messages.error(request, "Ponle un título a la tarea.")
        elif not due_time:
            # Sin hora no hay a qué hora sonar el aviso ni cuándo darla
            # por no hecha sola al final del día (ver Task.expire_overdue
            # y notifications.js, en la app móvil). El HTML ya la pide
            # con `required`, pero eso no protege envíos que se lo salten.
            messages.error(
                request,
                "Ponle una hora — la notificación y el aviso de «no hecha» al final del día la necesitan.",
            )
        else:
            client_uuid = _read_client_uuid(request)
            task = Task(
                title=title,
                notes=request.POST.get("notes", "").strip(),
                category=_read_category(request),
                subcategory=_read_subcategory(request),
                language_name=_read_language_name(request),
                level=_read_level(request),
                target_minutes=_read_target_minutes(request),
                youtube_video_id=_read_youtube_video_id(request),
                youtube_playlist_id=_read_youtube_playlist_id(request),
                target_video_count=_read_target_video_count(request),
                has_local_video=_read_has_local_video(request),
                sport_mode=_read_sport_mode(request),
                target_steps=_read_target_steps(request),
                target_distance_km=_read_target_distance_km(request),
                max_pace_seconds_per_km=_read_max_pace(request),
                due_date=request.POST.get("due_date") or None,
                due_time=due_time,
                repeat=request.POST.get("repeat", Task.REPEAT_NONE),
                interval=request.POST.get("interval") or 1,
                custom_days=",".join(request.POST.getlist("custom_days")),
                is_important=bool(request.POST.get("is_important")),
                avoid_question=request.POST.get("avoid_question", "").strip()[:120],
                avoid_success_label=request.POST.get("avoid_success_label", "").strip()[:32],
                avoid_fail_label=request.POST.get("avoid_fail_label", "").strip()[:32],
                user=get_current_user(),
            )
            if client_uuid:
                task.uuid = client_uuid
            task.save()
            messages.success(request, "Tarea creada.")
            return redirect(reverse("tasks:task_list"))

    initial_title = request.GET.get("title", "")
    return render(request, "tasks/task_form.html", {
        "repeat_choices": Task.REPEAT_CHOICES,
        "weekdays": Task.WEEKDAYS,
        "category_choices": Task.CATEGORY_CHOICES,
        "sport_subcategory_choices": Task.SPORT_SUBCATEGORY_CHOICES,
        "focus_subcategory_choices": Task.FOCUS_SUBCATEGORY_CHOICES,
        "study_subcategory_choices": Task.STUDY_SUBCATEGORY_CHOICES,
        "study_subcategory_values": [v for v, _ in Task.STUDY_SUBCATEGORY_CHOICES],
        "cefr_level_choices": Task.CEFR_LEVEL_CHOICES,
        "pace_presets": Task.PACE_PRESETS,
        "initial_title": initial_title,
    })


def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    if request.method == "POST":
        task.title = request.POST.get("title", task.title).strip()
        task.notes = request.POST.get("notes", "").strip()
        task.category = _read_category(request, default=task.category)
        task.subcategory = _read_subcategory(request, default=task.subcategory)
        task.language_name = _read_language_name(request)
        task.level = _read_level(request)
        task.target_minutes = _read_target_minutes(request)
        task.youtube_video_id = _read_youtube_video_id(request)
        task.youtube_playlist_id = _read_youtube_playlist_id(request)
        task.target_video_count = _read_target_video_count(request)
        task.has_local_video = _read_has_local_video(request)
        task.sport_mode = _read_sport_mode(request)
        task.target_steps = _read_target_steps(request)
        task.target_distance_km = _read_target_distance_km(request)
        task.max_pace_seconds_per_km = _read_max_pace(request)
        task.due_date = request.POST.get("due_date") or None
        task.due_time = request.POST.get("due_time") or None
        task.repeat = request.POST.get("repeat", Task.REPEAT_NONE)
        task.interval = request.POST.get("interval") or 1
        task.custom_days = ",".join(request.POST.getlist("custom_days"))
        task.is_important = bool(request.POST.get("is_important"))
        task.avoid_question = request.POST.get("avoid_question", "").strip()[:120]
        task.avoid_success_label = request.POST.get("avoid_success_label", "").strip()[:32]
        task.avoid_fail_label = request.POST.get("avoid_fail_label", "").strip()[:32]
        if not task.due_time:
            messages.error(
                request,
                "Ponle una hora — la notificación y el aviso de «no hecha» al final del día la necesitan.",
            )
        else:
            task.save()
            messages.success(request, "Tarea actualizada.")
            return redirect(reverse("tasks:task_list"))
    return render(request, "tasks/task_form.html", {
        "task": task,
        "repeat_choices": Task.REPEAT_CHOICES,
        "weekdays": Task.WEEKDAYS,
        "category_choices": Task.CATEGORY_CHOICES,
        "sport_subcategory_choices": Task.SPORT_SUBCATEGORY_CHOICES,
        "focus_subcategory_choices": Task.FOCUS_SUBCATEGORY_CHOICES,
        "study_subcategory_choices": Task.STUDY_SUBCATEGORY_CHOICES,
        "study_subcategory_values": [v for v, _ in Task.STUDY_SUBCATEGORY_CHOICES],
        "cefr_level_choices": Task.CEFR_LEVEL_CHOICES,
        "pace_presets": Task.PACE_PRESETS,
    })


@require_POST
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    task.delete()
    messages.success(request, "Tarea eliminada.")
    return redirect(reverse("tasks:task_list"))


@require_POST
def task_mark_done(request, pk):
    get_object_or_404(Task, pk=pk, user=get_current_user()).mark_done()
    return redirect(reverse("tasks:task_list"))


@require_POST
def task_mark_not_done(request, pk):
    get_object_or_404(Task, pk=pk, user=get_current_user()).mark_not_done()
    return redirect(reverse("tasks:task_list"))


@require_POST
def task_mark_failed(request, pk):
    """Antitareas: "he caído hoy" — ver Task.mark_failed()."""
    get_object_or_404(Task, pk=pk, user=get_current_user()).mark_failed()
    return redirect(reverse("tasks:task_list"))


@require_POST
def task_reopen(request, pk):
    """Deshacer: devuelve la tarea a pendiente y revierte lo que provocó
    marcarla (la ocurrencia del día y la instancia futura), para que las
    estadísticas vuelvan a estar como antes. Ver Task.reopen()."""
    get_object_or_404(Task, pk=pk, user=get_current_user()).reopen()
    messages.success(request, "Tarea devuelta a pendientes.")
    return redirect(reverse("tasks:task_list"))


def task_workout(request, pk):
    """
    Página de entreno para una tarea. En dos pasos:
    1. Sin ?exercise= ni ?video= en la URL: muestra el catálogo de
       ejercicios activos para elegir cuál tocar hoy — filtrado por la
       subcategoría de la tarea (tren superior / tren inferior /
       running) si la tiene. Para tren superior/inferior, además se
       ofrece "seguir un vídeo" como alternativa: se elige AQUÍ, cada
       vez, no queda fijado en la tarea — la misma tarea que se repite
       puede ir un día con vídeo y otro con circuito.
    2. Con ?exercise=<slug>: como antes (cámara / manual / sin contador).
       Con ?video=<id>: va directo al vídeo, sin pasar por lo demás.
    """
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    gate = _require_warmup(request, task)
    if gate:
        return gate
    exercise_slug = request.GET.get("exercise")
    video_id = request.GET.get("video")

    # Un vídeo elegido en el selector manda por encima de todo: ni plan,
    # ni ejercicio, ni circuito — es una tarea que se resuelve viéndolo.
    if video_id:
        return render(request, "tasks/task_video.html", {
            "task": task, "video_id": video_id,
            "playlist_id": "", "target_minutes": None, "target_video_count": None, "has_local_video": False,
        })

    # Si la tarea la generó un plan, no hay nada que elegir: el plan ya
    # decidió qué ejercicios y con qué objetivo. Se va directo a la
    # sesión, que es lo que hace que esto sea simple de usar.
    plan = task.plan
    if plan and not exercise_slug and plan.items.filter(exercise__isnull=False).exists():
        return redirect(reverse("tasks:plan_session", args=[task.pk, plan.pk]))

    # "timed" normalmente solo vive dentro de un circuito (cuenta atrás a
    # secas) — pero plancha y plancha lateral, al llevar cámara propia
    # comprobando la postura, también se pueden entrenar sueltas para
    # una sola tarea, igual que dominadas o sentadillas. El resto de
    # "timed" (bicicleta…) se queda fuera del selector individual.
    exercises_qs = Exercise.objects.filter(is_active=True).exclude(
        Q(mode=Exercise.MODE_TIMED) & ~Q(counter_key__in=POSTURE_COUNTERS)
    )
    routines_qs = Routine.objects.filter(user=get_current_user())
    if task.subcategory:
        exercises_qs = exercises_qs.filter(body_area=task.subcategory)
        routines_qs = routines_qs.filter(subcategory=task.subcategory)

    videos_qs = SavedVideo.objects.none()
    if task.subcategory in (Task.SUBCATEGORY_LOWER_BODY, Task.SUBCATEGORY_UPPER_BODY):
        videos_qs = SavedVideo.objects.filter(
            user=get_current_user(), scope=task.subcategory, deleted_at__isnull=True,
        )

    if not exercise_slug:
        return render(request, "tasks/task_workout_select.html", {
            "task": task, "exercises": exercises_qs, "routines": routines_qs, "videos": videos_qs,
        })

    exercise = get_object_or_404(Exercise, slug=exercise_slug, is_active=True)

    if exercise.mode == Exercise.MODE_DISTANCE:
        return render(request, "tasks/task_workout_manual.html", {
            "task": task, "exercise": exercise,
        })

    # Contadores implementados en workout.js: dominadas (y variantes),
    # fondos, flexiones, sentadillas, abdominales, crunch, elevación de
    # piernas, doble crunch y tijeretas cuentan repeticiones (mode="pose");
    # plancha y plancha lateral se aguantan y llevan la cámara para
    # comprobar la postura (mode="timed", ver POSTURE_COUNTERS).
    # Cualquier otra combinación (o un ejercicio sin cámara) cae aquí
    # como "no soportado".
    is_pose_supported = exercise.mode == Exercise.MODE_POSE and exercise.counter_key in COUNTERS
    is_posture_supported = exercise.mode == Exercise.MODE_TIMED and exercise.counter_key in POSTURE_COUNTERS
    if not (is_pose_supported or is_posture_supported):
        return render(request, "tasks/task_workout_select.html", {
            "task": task, "exercises": exercises_qs, "routines": routines_qs, "videos": videos_qs,
            "unsupported": exercise,
        })

    return render(request, "tasks/task_workout.html", {
        "task": task, "exercise": exercise,
        "target": resolve_plan_target(exercise.slug),
    })


@require_POST
def task_workout_save(request, pk):
    """
    Recibe (por fetch/AJAX, en JSON) las estadísticas ya calculadas en
    el navegador al terminar la sesión, las guarda, y marca la tarea
    como hecha. No se recibe ni se guarda ningún vídeo — solo números.
    """
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    exercise_slug = request.GET.get("exercise", "pullup")
    exercise = Exercise.objects.filter(slug=exercise_slug).first()
    exercise_value = exercise.slug if exercise else WorkoutSession.EXERCISE_PULLUP
    exercise_label = exercise.name.lower() if exercise else "dominadas"

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    total_reps = int(data.get("total_reps", 0))
    rep_durations = data.get("rep_durations", [])
    if not isinstance(rep_durations, list):
        rep_durations = []
    rep_durations = [float(d) for d in rep_durations if isinstance(d, (int, float))]

    raw_sets = data.get("sets", [])
    clean_sets = []
    if isinstance(raw_sets, list):
        for s in raw_sets:
            if not isinstance(s, dict):
                continue
            s_reps = int(s.get("reps", 0))
            s_durations = [float(d) for d in s.get("durations", []) if isinstance(d, (int, float))]
            clean_sets.append({"reps": s_reps, "durations": s_durations})
    total_sets = int(data.get("total_sets", len(clean_sets)))

    avg_rep_seconds = round(sum(rep_durations) / len(rep_durations), 2) if rep_durations else None

    # Si hay un plan activo siguiendo este ejercicio, manda su objetivo
    # (aunque esta tarea en concreto no la generara el plan). Antes esto
    # solo pasaba en la app móvil — entrenar desde la web no contaba
    # para el plan.
    ctx = resolve_plan_target(exercise_value)

    ws = WorkoutSession.objects.create(
        task=task,
        user=get_current_user(),
        series_id=task.series_id,
        exercise=exercise_value,
        plan=ctx["plan"],
        target_sets=ctx["target_sets"],
        target_reps=ctx["target_reps"],
        target_seconds=ctx["target_seconds"],
        total_reps=total_reps,
        total_sets=total_sets,
        sets=clean_sets,
        session_duration_seconds=int(data.get("session_duration_seconds", 0)),
        avg_rep_seconds=avg_rep_seconds,
        rest_alerts_triggered=int(data.get("rest_alerts_triggered", 0)),
        rep_durations=rep_durations,
    )

    # Un solo ejercicio con objetivo: la tarea solo se da por completada
    # si se llegó a él. Si se quedó corta, se queda pendiente con el
    # porcentaje ya guardado en la sesión, para poder retomarla el mismo
    # día. Sin objetivo (entreno libre), se completa como siempre.
    resumen = f"Sesión guardada: {total_reps} {exercise_label} en {total_sets} serie(s)"
    if avg_rep_seconds:
        resumen += f", ritmo medio {avg_rep_seconds}s/rep."
    else:
        resumen += "."

    if ws.target_met:
        # La tarea no se marca hecha aquí — falta el enfriamiento
        # obligatorio (ver task_cooldown), que es quien la cierra de verdad.
        redirect_url = reverse("tasks:task_cooldown", args=[task.pk])
    else:
        resumen += f" Te has quedado en el {ws.achievement_pct}% del objetivo — la tarea sigue pendiente."
        redirect_url = reverse("tasks:task_list")
    messages.success(request, resumen)
    return JsonResponse({"ok": True, "redirect_url": redirect_url})


@require_POST
def task_workout_save_manual(request, pk):
    """
    Guarda una sesión escrita a mano (running: cinta, reloj, Samsung
    Health…). A diferencia de task_workout_save, esto es un <form> normal
    (no fetch/JSON) — se valida, se guarda y se redirige, sin JS de por
    medio.
    """
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    exercise_slug = request.GET.get("exercise", "running")
    exercise = get_object_or_404(Exercise, slug=exercise_slug, mode=Exercise.MODE_DISTANCE)

    def _to_float(raw):
        try:
            return float(str(raw).replace(",", "."))
        except (TypeError, ValueError):
            return None

    def _to_int(raw):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    distance_km = _to_float(request.POST.get("distance_km"))
    duration_minutes = _to_float(request.POST.get("duration_minutes"))
    steps = _to_int(request.POST.get("steps"))

    if not distance_km and not duration_minutes:
        messages.error(request, "Pon al menos la distancia o la duración para guardar la sesión.")
        return redirect(f"{reverse('tasks:task_workout', args=[task.pk])}?exercise={exercise.slug}")

    session_duration_seconds = int(round(duration_minutes * 60)) if duration_minutes else 0
    avg_rep_seconds = None
    if distance_km and duration_minutes:
        # "ritmo" en min/km, reutilizando avg_rep_seconds (en segundos) para no
        # añadir otro campo solo para esto.
        avg_rep_seconds = round((duration_minutes * 60) / distance_km, 2)

    WorkoutSession.objects.create(
        task=task,
        user=get_current_user(),
        series_id=task.series_id,
        exercise=exercise.slug,
        session_duration_seconds=session_duration_seconds,
        avg_rep_seconds=avg_rep_seconds,
        distance_km=distance_km,
        steps=steps,
    )

    bits = []
    if distance_km:
        bits.append(f"{distance_km}km")
    if duration_minutes:
        bits.append(f"{duration_minutes:.0f} min")
    if steps:
        bits.append(f"{steps} pasos")
    # A diferencia del resto de Deporte, running no pasa por el
    # enfriamiento obligatorio: la sesión ya viene de un dato real
    # (distancia/tiempo, Health Connect...), no hace falta el vídeo.
    task.mark_done()
    messages.success(request, "Sesión de running guardada: " + ", ".join(bits) + ".")
    return redirect(reverse("tasks:task_list"))


def task_warmup(request, pk):
    """
    Calentamiento obligatorio antes de entrenar (ver _require_warmup):
    un vídeo fijo que hay que ver entero — el botón de continuar
    permanece bloqueado hasta el evento ENDED de YouTube (ver
    tasks/task_warmup.html). Al terminar, se apunta la hora
    (WarmupStatus) y se vuelve a donde se iba (?next=), que ya no lo
    volverá a pedir mientras siga "fresco".
    """
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    next_url = request.GET.get("next") or reverse("tasks:task_workout", args=[task.pk])
    if request.method == "POST":
        WarmupStatus.mark_done(get_current_user())
        return redirect(next_url)
    return render(request, "tasks/task_warmup.html", {
        "task": task, "next": next_url, "video_id": WARMUP_VIDEO_ID,
    })


def task_cooldown(request, pk):
    """
    Enfriamiento obligatorio al terminar de entrenar: mismo mecanismo
    que task_warmup pero al revés. Se llega aquí DESPUÉS de guardar ya
    los números de la sesión (task_workout_save, .._save_manual,
    routine_save, plan_session_save, task_video_save) — hasta que no se
    ve el vídeo entero, la tarea no se marca hecha de verdad.
    """
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    if request.method == "POST":
        task.mark_done()
        messages.success(request, "Sesión completada.")
        return redirect(reverse("tasks:task_list"))
    return render(request, "tasks/task_cooldown.html", {
        "task": task, "video_id": COOLDOWN_VIDEO_ID,
    })


# ------------------------------------------------------------- enfoque

def task_focus(request, pk):
    """
    Pantalla del temporizador de una tarea de Enfoque (leer, estudiar,
    estirar…). El cronómetro es JS puro en la plantilla — aquí solo se
    enseña el objetivo, si lo hay.

    Solo para el subtipo Estudio: además del temporizador, se ofrece
    seguir un vídeo — se elige aquí, cada vez, igual que en tren
    superior/inferior. Con ?video=<id> se va directo al vídeo; sin él
    (y sin ?mode=timer) se enseña primero el selector.
    """
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    video_id = request.GET.get("video")
    if video_id:
        # Mismo contexto completo que task_video: la plantilla necesita
        # SIEMPRE estas claves, aunque sea None/"" — si falta alguna, el
        # JS que arma con {{ target_minutes|default_if_none:"null" }}
        # se queda con una asignación vacía y ni siquiera arranca.
        return render(request, "tasks/task_video.html", {
            "task": task, "video_id": video_id,
            "playlist_id": "", "target_minutes": None, "target_video_count": None, "has_local_video": False,
        })

    if task.subcategory == Task.SUBCATEGORY_STUDY_SESSION and request.GET.get("mode") != "timer":
        videos_qs = SavedVideo.objects.filter(
            user=get_current_user(), scope=SavedVideo.SCOPE_STUDY, deleted_at__isnull=True,
        )
        return render(request, "tasks/task_focus_mode.html", {"task": task, "videos": videos_qs})

    return render(request, "tasks/task_focus.html", {"task": task})


@require_POST
def task_focus_save(request, pk):
    """
    Recibe los minutos ya contados en el navegador (fetch/JSON) y
    guarda la sesión. Mismo criterio que task_workout_save: si había
    objetivo y no se llegó, la tarea se queda pendiente con el
    porcentaje guardado, para poder retomarla el mismo día.
    """
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    minutes = max(0, int(data.get("minutes", 0)))

    ts = TimerSession.objects.create(
        task=task,
        user=get_current_user(),
        series_id=task.series_id,
        subcategory=task.subcategory,
        source=TimerSession.SOURCE_MANUAL,
        minutes=minutes,
        target_minutes=task.target_minutes,
    )

    if ts.target_met:
        task.mark_done()

    resumen = f"Sesión guardada: {minutes} min"
    resumen += "." if ts.target_met else f" — {ts.achievement_pct}% del objetivo. La tarea sigue pendiente."
    messages.success(request, resumen)
    return JsonResponse({"ok": True, "redirect_url": reverse("tasks:task_list")})


# --------------------------------------------------------------- vídeo

# -------------------------------------------------------- vídeos guardados

@require_POST
def saved_video_create(request):
    """
    Guarda un vídeo nuevo desde el selector de tren superior/inferior o
    de estudio, y va derecho a reproducirlo — un paso menos que guardar
    y luego tener que ir a buscarlo en la lista.
    """
    scope = request.POST.get("scope", "")
    valid_scopes = {key for key, _ in SavedVideo.SCOPE_CHOICES}
    if scope not in valid_scopes:
        messages.error(request, "Tipo de vídeo no válido.")
        return redirect(reverse("tasks:task_list"))

    raw = request.POST.get("youtube_video_id", "").strip()
    if not raw:
        messages.error(request, "Pega un enlace de YouTube.")
        return redirect(request.POST.get("next") or reverse("tasks:task_list"))

    sv = SavedVideo.objects.create(
        user=get_current_user(), scope=scope,
        title=request.POST.get("title", "").strip()[:120],
        youtube_video_id=raw,
    )

    task_pk = request.POST.get("task_pk")
    entry_url = request.POST.get("entry_url") or reverse("tasks:task_workout", args=[task_pk])
    sep = "&" if "?" in entry_url else "?"
    return redirect(f"{entry_url}{sep}video={sv.youtube_video_id}")


@require_POST
def saved_video_delete(request, uuid):
    """Borrado suave, para poder limpiar la lista sin romper el historial."""
    sv = get_object_or_404(SavedVideo, uuid=uuid, user=get_current_user())
    sv.deleted_at = timezone.now()
    sv.save(update_fields=["deleted_at"])
    messages.success(request, "Vídeo quitado de la lista.")
    return redirect(request.POST.get("next") or reverse("tasks:task_list"))


def task_video(request, pk):
    """
    Pantalla del vídeo de una tarea. El vídeo puede venir fijado en la
    propia tarea (task.youtube_video_id) o elegido al vuelo desde el
    selector de tren superior/inferior/estudio (?video=) — task_workout
    y task_focus redirigen aquí pasándolo. El embed y la detección de
    "terminó" son JS puro (IFrame Player API de YouTube).

    task.youtube_playlist_id / target_minutes / target_video_count solo
    aplican al vídeo fijado en la tarea, no al elegido al vuelo (ese
    siempre es un vídeo suelto, sin objetivo por cuenta ni por minutos).

    Un curso de idioma (Plan.STUDY_SUBTYPE_LANGUAGE) asigna UN vídeo por
    día, que suele durar mucho menos que el objetivo diario en minutos
    — sin más, la tarea se marcaría hecha en cuanto acabara ese primer
    vídeo corto, sin llegar ni de lejos al objetivo. `course_queue` lleva
    los siguientes vídeos del temario para que task_video.html los
    encadene solo, en la misma sesión, hasta llenar el objetivo (ver
    Plan.upcoming_course_queue).
    """
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    override_video_id = request.GET.get("video")
    video_id = override_video_id or task.youtube_video_id
    plan = None if override_video_id else task.plan
    is_language_session = bool(
        plan and plan.plan_type == Plan.PLAN_TYPE_STUDY and plan.study_subtype == Plan.STUDY_SUBTYPE_LANGUAGE
    )
    course_queue = plan.upcoming_course_queue() if is_language_session else []
    return render(request, "tasks/task_video.html", {
        "task": task,
        "video_id": video_id,
        "playlist_id": "" if override_video_id else task.youtube_playlist_id,
        "target_minutes": None if override_video_id else task.target_minutes,
        "target_video_count": None if override_video_id else task.target_video_count,
        "playlist_start_index": None if override_video_id else task.playlist_start_index,
        # Un vídeo elegido al vuelo siempre es de YouTube, suelto — el
        # "solo local, sin YouTube" solo puede venir de la propia tarea.
        "has_local_video": False if override_video_id else task.has_local_video,
        "course_queue_json": json.dumps(course_queue),
    })


@require_POST
def task_video_save(request, pk):
    """
    El vídeo llegó al objetivo en minutos, o al final (evento ENDED en
    el navegador) -> la tarea se marca hecha directamente. No hay
    objetivo que comparar contra un mínimo para dejarla pendiente (a
    diferencia de Enfoque): aquí target_minutes solo decide CUÁNDO
    cortar, no si la tarea vale o no — ver task_video.html.

    `minutes` son los minutos reales vistos, contados en el navegador
    con la IFrame API de YouTube (no un dato de confianza del cliente
    sin más: solo cuenta mientras el vídeo está de verdad reproduciéndose).
    Se guardan en la Occurrence del día para que salgan en resultados.

    Si esto era un vídeo de un curso de idioma con Plan.quiz_every_n_videos
    puesto, y justo tocaba test de repaso, se redirige al test en vez de
    a la lista de tareas — ver api.maybe_trigger_quiz. La tarea ya está
    hecha de todas formas: el test es aparte y nunca bloquea nada.
    """
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, TypeError):
        data = {}
    raw_minutes = data.get("minutes")
    minutes_watched = max(0, int(raw_minutes)) if isinstance(raw_minutes, (int, float)) else None
    # Cuántos vídeos del temario se completaron ENTEROS en esta sesión —
    # una sesión de idioma puede encadenar varios vídeos cortos seguidos
    # hasta llenar el objetivo diario en minutos (ver task_video.html);
    # sin dato (cliente viejo, o tarea que no es de idioma) se asume 1,
    # ver Plan.mark_current_module_watched.
    raw_videos = data.get("videos_watched")
    videos_watched = max(0, int(raw_videos)) if isinstance(raw_videos, (int, float)) else None
    plan = task.plan

    # Un vídeo de Deporte (seguir una rutina en YouTube) no se marca
    # hecho aquí: falta el enfriamiento obligatorio (task_cooldown), que
    # es quien la cierra de verdad. El resto (Estudio, idiomas…) sigue
    # exactamente como antes.
    if task.category == Task.CATEGORY_SPORT:
        return JsonResponse({"ok": True, "redirect_url": reverse("tasks:task_cooldown", args=[task.pk])})

    task.mark_done(minutes_watched=minutes_watched)
    messages.success(request, "Vídeo visto — tarea completada.")

    redirect_url = reverse("tasks:task_list")
    if plan and plan.plan_type == Plan.PLAN_TYPE_STUDY and plan.study_subtype == Plan.STUDY_SUBTYPE_LANGUAGE:
        plan.mark_current_module_watched(count=videos_watched)
        quiz = api.maybe_trigger_quiz(plan)
        if quiz:
            redirect_url = reverse("tasks:quiz_take", args=[quiz.uuid])
    return JsonResponse({"ok": True, "redirect_url": redirect_url})


def _save_routine(request, routine=None):
    """Crea o actualiza una Routine a partir del formulario del
    constructor de circuitos. Compartido por routine_create/routine_edit."""
    name = request.POST.get("name", "").strip() or "Circuito sin nombre"

    subcategory = request.POST.get("subcategory", "")
    valid_sub = {key for key, _ in Task.SUBCATEGORY_CHOICES}
    if subcategory not in valid_sub:
        subcategory = ""

    try:
        work = max(5, int(request.POST.get("default_work_seconds", 40)))
    except (TypeError, ValueError):
        work = 40
    try:
        rest = max(0, int(request.POST.get("default_rest_seconds", 20)))
    except (TypeError, ValueError):
        rest = 20

    raw_items = request.POST.get("items", "")
    exercise_ids = [int(x) for x in raw_items.split(",") if x.strip().isdigit()]
    next_url = request.POST.get("next") or reverse("tasks:task_list")

    if not exercise_ids:
        messages.error(request, "Elige al menos un ejercicio para el circuito.")
        back = reverse("tasks:routine_edit", args=[routine.pk]) if routine else reverse("tasks:routine_create")
        return redirect(f"{back}?next={next_url}")

    if routine is None:
        routine = Routine.objects.create(
            user=get_current_user(), name=name, subcategory=subcategory,
            default_work_seconds=work, default_rest_seconds=rest,
        )
    else:
        routine.name = name
        routine.subcategory = subcategory
        routine.default_work_seconds = work
        routine.default_rest_seconds = rest
        routine.save()
        routine.items.all().delete()

    # Se admite cualquier ejercicio activo, no solo los cronometrados: un
    # circuito de tren superior (dominadas, fondos) es tan válido como
    # uno de abdominales — cada uno se reproduce luego con lo que le
    # toque (cámara, cronómetro, o cronómetro con cámara comprobando la
    # postura). Esto solo evita que alguien cuele por POST un id de
    # ejercicio que no existe o está desactivado.
    valid_exercise_ids = set(
        Exercise.objects.filter(id__in=exercise_ids, is_active=True).values_list("id", flat=True)
    )
    order = 0
    for eid in exercise_ids:
        if eid not in valid_exercise_ids:
            continue
        RoutineItem.objects.create(routine=routine, exercise_id=eid, order=order)
        order += 1

    messages.success(request, f"Circuito «{routine.name}» guardado con {order} ejercicio(s).")
    return redirect(next_url)


def routine_create(request):
    if request.method == "POST":
        return _save_routine(request)
    # Cualquier ejercicio activo vale para un circuito, no solo los
    # cronometrados (ver _save_routine) — cada uno se reproduce luego
    # con lo suyo.
    exercises = Exercise.objects.filter(is_active=True)
    return render(request, "tasks/routine_form.html", {
        "exercises": exercises,
        "subcategory_choices": Task.SPORT_SUBCATEGORY_CHOICES,
        "initial_subcategory": request.GET.get("subcategory", ""),
        "next_url": request.GET.get("next", ""),
    })


def routine_edit(request, pk):
    routine = get_object_or_404(Routine, pk=pk, user=get_current_user())
    if request.method == "POST":
        return _save_routine(request, routine=routine)
    exercises = Exercise.objects.filter(is_active=True)
    return render(request, "tasks/routine_form.html", {
        "routine": routine,
        "exercises": exercises,
        "subcategory_choices": Task.SPORT_SUBCATEGORY_CHOICES,
        "initial_subcategory": routine.subcategory,
        "next_url": request.GET.get("next", ""),
        "selected_items": list(routine.items.select_related("exercise")),
    })


@require_POST
def routine_delete(request, pk):
    routine = get_object_or_404(Routine, pk=pk, user=get_current_user())
    routine.delete()
    messages.success(request, "Circuito eliminado.")
    return redirect(request.POST.get("next") or reverse("tasks:task_list"))


def routine_play(request, pk, routine_pk):
    """
    Reproductor del circuito: encadena todos los RoutineItem de la
    rutina, cada uno con lo que le toca — cronómetro, cámara contando
    reps, o cronómetro con cámara comprobando la postura (plancha) —,
    ver static/js/circuit.js. `mode`/`counter_key`/`target_*` van en
    items_data igual que en la API (ver api._routine_item_json), así
    que el objetivo de un ejercicio de cámara sube solo si hay un plan
    activo siguiéndolo.
    """
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    gate = _require_warmup(request, task)
    if gate:
        return gate
    routine = get_object_or_404(Routine, pk=routine_pk, user=get_current_user())
    items = list(routine.items.select_related("exercise"))

    if not items:
        messages.error(request, "Este circuito todavía no tiene ejercicios.")
        return redirect(reverse("tasks:task_workout", args=[task.pk]))

    items_data = []
    for it in items:
        t = it.resolved_target()
        items_data.append({
            "slug": it.exercise.slug,
            "name": it.exercise.name,
            "mode": it.exercise.mode,
            "counter_key": it.exercise.counter_key,
            "work": t["seconds"],
            "rest": it.effective_rest_seconds,
            "target_sets": t["sets"],
            "target_reps": t["reps"],
            "target_source": t["source"],
            "plan_name": t["plan_name"],
        })
    return render(request, "tasks/routine_play.html", {
        "task": task, "routine": routine, "items": items, "items_json": json.dumps(items_data),
    })


@require_POST
def routine_save(request, pk, routine_pk):
    """
    Guarda el resultado del circuito al terminar (o al cortarlo antes de
    tiempo): UNA WorkoutSession POR EJERCICIO, no una combinada.

    Antes se guardaba una única sesión con exercise="ab-circuit" y el
    desglose metido en `sets`. Eso perdía la trazabilidad por ejercicio:
    si algún día sigues un plan sobre "plancha" (subir el tiempo cada
    semana), esa sesión combinada nunca contaría, porque
    PlanItem busca WorkoutSession.exercise="plank", no "ab-circuit".
    Guardando una por ejercicio, cualquier plan que siga alguno de ellos
    avanza solo — igual que ya hacía la app móvil.

    La tarea del día se completa siempre que termines el circuito,
    lleguen o no todos los ejercicios a su objetivo: aquí lo que importa
    es que has entrenado, no que cada ejercicio individual esté a tope.
    El % de cada uno se guarda igualmente, para las estadísticas.
    """
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    routine = get_object_or_404(Routine, pk=routine_pk, user=get_current_user())

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    raw_breakdown = data.get("breakdown", [])
    entries = []
    total_seconds = 0
    if isinstance(raw_breakdown, list):
        for b in raw_breakdown:
            if not isinstance(b, dict):
                continue
            slug = str(b.get("exercise", ""))[:32]
            seconds = int(b.get("seconds", 0)) if isinstance(b.get("seconds"), (int, float)) else 0
            reps = int(b.get("reps", 0)) if isinstance(b.get("reps"), (int, float)) else 0
            sets = int(b.get("sets", 0)) if isinstance(b.get("sets"), (int, float)) else 0
            if not slug:
                continue
            entries.append({"exercise": slug, "seconds": seconds, "reps": reps, "sets": sets})
            total_seconds += seconds

    if not entries:
        return JsonResponse({"ok": False, "error": "Sin datos que guardar"}, status=400)

    created = []
    for e in entries:
        ctx = resolve_plan_target(e["exercise"])
        created.append(WorkoutSession.objects.create(
            task=task, user=get_current_user(), routine=routine, series_id=task.series_id,
            plan=ctx["plan"], target_sets=ctx["target_sets"],
            target_reps=ctx["target_reps"], target_seconds=ctx["target_seconds"],
            exercise=e["exercise"],
            total_reps=e["reps"], total_sets=e["sets"],
            session_duration_seconds=e["seconds"],
        ))

    cortas = [w for w in created if not w.target_met]
    resumen = f"Circuito «{routine.name}» completado: {len(created)} ejercicio(s), {total_seconds}s."
    if cortas:
        resumen += " " + ", ".join(f"{w.exercise_name} al {w.achievement_pct}%" for w in cortas) + "."
    messages.success(request, resumen)
    # La tarea se marca hecha en task_cooldown — falta el enfriamiento
    # obligatorio.
    return JsonResponse({"ok": True, "redirect_url": reverse("tasks:task_cooldown", args=[task.pk])})


def stats_list(request):
    summary = {}
    for occ in Occurrence.objects.filter(user=get_current_user()).order_by("recorded_at"):
        s = summary.setdefault(occ.series_id, {
            "title": occ.title, "done": 0, "not_done": 0, "series_id": occ.series_id,
        })
        s["title"] = occ.title
        if occ.result == Occurrence.RESULT_DONE:
            s["done"] += 1
        else:
            s["not_done"] += 1

    series_list = list(summary.values())
    for s in series_list:
        total = s["done"] + s["not_done"]
        s["total"] = total
        s["success_rate"] = round((s["done"] / total) * 100) if total else 0
        streaks = Occurrence.streak_stats(s["series_id"])
        s["current_streak"] = streaks["current_streak"]
        s["max_streak"] = streaks["max_streak"]
    series_list.sort(key=lambda s: s["total"], reverse=True)

    return render(request, "tasks/stats_list.html", {
        "series_list": series_list,
        "weekly": Occurrence.weekly_completion(get_current_user()),
    })


def stats_detail(request, series_id):
    occurrences = Occurrence.objects.filter(
        series_id=series_id, user=get_current_user()
    ).order_by("-recorded_at")
    if not occurrences.exists():
        messages.error(request, "No hay estadísticas para esa tarea.")
        return redirect(reverse("tasks:stats_list"))

    title = occurrences.first().title
    done_count = occurrences.filter(result=Occurrence.RESULT_DONE).count()
    not_done_count = occurrences.filter(result=Occurrence.RESULT_NOT_DONE).count()
    total = done_count + not_done_count
    success_rate = round((done_count / total) * 100) if total else 0
    streaks = Occurrence.streak_stats(series_id)

    return render(request, "tasks/stats_detail.html", {
        "title": title,
        "series_id": series_id,
        "occurrences": occurrences,
        "done_count": done_count,
        "not_done_count": not_done_count,
        "success_rate": success_rate,
        "current_streak": streaks["current_streak"],
        "max_streak": streaks["max_streak"],
    })


# ─────────────────────────────────────────────────────────────────────
# Planes de progresión
# ─────────────────────────────────────────────────────────────────────

# Contadores que existen de verdad en workout.js.
COUNTERS = {"pullup", "dip", "pushup", "squat", "crunch", "legraise", "situp", "doublecrunch", "scissor", "archerpullup", "inclinepushup", "dumbbellcurl"}

# Ejercicios "timed" (se aguantan, no se cuentan en repeticiones) que
# workout.js sabe seguir con cámara comprobando la postura — plancha,
# plancha lateral, silla en pared, kneehold en barra y pino. Ver
# task_workout: a estos, a diferencia del resto de "timed" (bicicleta…),
# sí se les deja entrar en el entreno individual de una tarea con cámara
# encendida, no solo dentro de un circuito.
POSTURE_COUNTERS = {"plank", "sideplank", "wallsit", "kneeholdbar", "handstand"}


def _plans_qs():
    return Plan.objects.filter(user=get_current_user(), deleted_at__isnull=True)


def plan_list(request):
    """Los planes, con su medida principal y cuánto llevas."""
    plans = []
    for p in _plans_qs().filter(closed_at__isnull=True):
        head = p.headline
        plans.append({
            "plan": p,
            "headline": head,
            "target": head.current_target() if head else None,
            "remaining": head.sessions_to_goal() if head else None,
            "progress": p.progress_pct(),
        })
    closed_plans = [
        {"plan": p, "progress": p.final_progress_pct}
        for p in _plans_qs().filter(closed_at__isnull=False).order_by("-closed_at")
    ]
    return render(request, "tasks/plan_list.html", {"plans": plans, "closed_plans": closed_plans})


def weekly_review(request):
    """
    La revisión semanal del 12 Week Year: cómo ha ido la semana en
    conjunto y en cada objetivo activo, en una sola pantalla — en vez
    de tener que entrar plan a plan para hacerse una idea de conjunto.
    """
    plans = []
    for p in _plans_qs().filter(is_active=True):
        plans.append({
            "plan": p,
            "weekly": p.weekly_completion(),
            "progress": p.progress_pct(),
        })
    return render(request, "tasks/weekly_review.html", {
        "weekly": Occurrence.weekly_completion(get_current_user()),
        "plans": plans,
    })


def plan_detail(request, pk):
    """
    La pantalla del plan: dónde estás, qué te toca hoy, el camino que
    queda y lo que ya hiciste.
    """
    plan = get_object_or_404(_plans_qs(), pk=pk)

    def _pack(item):
        # La tabla tiene que llegar hasta el destino. Con un número fijo
        # se cortaba antes de tiempo — un objetivo de 4x12 con 20 kg son
        # 35 escalones — y no se veía el final, que es lo que da sentido
        # a todo. El tope es solo una red de seguridad.
        remaining = item.sessions_to_goal()
        rows = 60
        if remaining is not None:
            rows = min(120, item.current_step() + remaining // max(1, item.sessions_per_step) + 2)
        return {
            "item": item,
            "target": item.current_target(),
            "step": item.current_step(),
            "remaining": remaining,
            "schedule": item.schedule(rows),
            "history": item.history(12),
            # Si el entrenador ha bajado un escalón conviene decirlo: si
            # no, parece que la app se ha equivocado.
            "deloaded": item.successes_and_streak()[1] >= item.deload_after_failures > 0,
        }

    # Estudio · Idiomas no tiene PlanItem — el temario es la lista de
    # CourseModule, así que la pantalla se arma distinto: en vez de la
    # medida principal + objetivos, se enseña el progreso del curso y
    # qué vídeo toca ahora.
    is_language = plan.plan_type == Plan.PLAN_TYPE_STUDY and plan.study_subtype == Plan.STUDY_SUBTYPE_LANGUAGE
    # Estudio · Hábito simple: el vídeo/playlist/temporizador se edita
    # desde "Editar plan" (ver views.plan_form), no con un botón aparte
    # de "+ Añadir objetivo" — ese solo tiene sentido en Deporte, donde
    # puede haber varios ejercicios.
    is_study_general = plan.plan_type == Plan.PLAN_TYPE_STUDY and not is_language
    course_progress = plan.course_progress() if is_language else None

    head = plan.headline
    return render(request, "tasks/plan_detail.html", {
        "plan": plan,
        "headline": _pack(head) if head else None,
        "supports": [_pack(i) for i in plan.support_items],
        "progress": plan.progress_pct(),
        "is_language": is_language,
        "is_study_general": is_study_general,
        "course_progress": course_progress,
        "quiz_streaks": plan.quiz_streak_stats() if is_language and plan.quiz_every_n_videos else None,
    })


# ------------------------------------------------- tests de repaso (idiomas)

def _quizzes_qs():
    return CourseQuiz.objects.filter(plan__user=get_current_user())


def quiz_take(request, quiz_uuid):
    """
    Pantalla del test de repaso: preguntas de opción múltiple sobre los
    últimos vídeos vistos de un curso de idioma (ver
    api.maybe_trigger_quiz). NO bloquea nada — el vídeo que lo disparó
    ya se dio por visto antes de llegar aquí; esto es aparte, con su
    propia racha (ver plan_detail.html).
    """
    quiz = get_object_or_404(_quizzes_qs(), uuid=quiz_uuid)
    if quiz.answered_at:
        return redirect(reverse("tasks:quiz_result", args=[quiz.uuid]))

    if request.method == "POST":
        selected = []
        for i in range(len(quiz.questions)):
            raw = request.POST.get(f"q{i}")
            try:
                selected.append(int(raw))
            except (TypeError, ValueError):
                selected.append(-1)
        quiz.answer(selected)
        return redirect(reverse("tasks:quiz_result", args=[quiz.uuid]))

    return render(request, "tasks/quiz_take.html", {"quiz": quiz, "plan": quiz.plan})


def quiz_result(request, quiz_uuid):
    """
    Corrección del test: se arma `review` aquí (no en la plantilla) para
    no necesitar un filtro a medida solo para mirar `quiz.answers[i]` —
    cada opción ya lleva consigo si era la correcta y si fue la elegida.
    """
    quiz = get_object_or_404(_quizzes_qs(), uuid=quiz_uuid)
    if not quiz.answered_at:
        return redirect(reverse("tasks:quiz_take", args=[quiz.uuid]))

    answers = quiz.answers or []
    review = []
    for i, q in enumerate(quiz.questions):
        chosen = answers[i] if i < len(answers) else None
        review.append({
            "question": q.get("question", ""),
            "options": [
                {
                    "text": opt,
                    "is_correct": idx == q.get("correct_index"),
                    "is_chosen": idx == chosen,
                }
                for idx, opt in enumerate(q.get("options") or [])
            ],
        })

    return render(request, "tasks/quiz_result.html", {
        "quiz": quiz, "plan": quiz.plan, "streaks": quiz.plan.quiz_streak_stats(), "review": review,
    })


def plan_ai_form(request):
    """
    Crear un plan de Deporte generándolo automáticamente en vez de
    rellenar el formulario objetivo a objetivo — 100% determinista, sin
    IA de por medio (ver docstring de `api.build_plan_draft`): tú eliges
    nivel físico, foco corporal, equipamiento, semanas y días, y la app
    elige los ejercicios del catálogo que tocan para ese nivel/foco y
    calcula la progresión con matemáticas fijas, no con un modelo de
    lenguaje. Dos pasos, sin guardar nada hasta el final:

      1. El usuario rellena el cuestionario. Al enviarlo se genera el
         borrador (`api.build_plan_draft`, compartida con el endpoint de
         la app móvil) y se enseña para revisar.
      2. El usuario revisa el borrador — puede tocar los números — y lo
         confirma, o pide "generar otra vez" con los mismos filtros.

    Solo Deporte: Estudio y General no pasan por aquí — "Estudio ·
    Idiomas" asigna cursos del catálogo sin IA por su propio camino (ver
    `views.plan_form` → `plan_language_confirm`), y General no tiene
    ningún catálogo del que elegir, así que no hay nada que autogenerar
    — ambos se crean a mano («+ Nuevo plan a mano»).

    El borrador vive en la sesión entre los dos pasos, para que tocar un
    número y confirmar no obligue a recalcular nada.
    """
    step = request.POST.get("step")

    if request.method == "POST" and step in ("generar", "regenerar"):
        weeks = request.POST.get("weeks")
        custom_days = request.POST.getlist("custom_days")

        # Cuestionario — nivel físico, foco corporal, equipamiento, tope
        # de lastre. Con esto la app elige el catálogo (ver
        # `ai._select_sport_exercises`) y los números de partida/meta
        # (ver `ai.default_item_fields`); no hace falta nada más.
        fitness_level = request.POST.get("fitness_level", "")
        focus_area = request.POST.get("focus_area", "")
        no_bar_equipment = request.POST.get("no_bar_equipment") == "on"
        max_load_kg = request.POST.get("max_load_kg", "").strip()
        # Selector manual de ejercicios (ver plan_ai_form.html) — siempre
        # visible, da igual nivel/foco: si el usuario marca algo aquí,
        # sustituye del todo a la elección automática por nivel/zona.
        selected_exercises = request.POST.getlist("exercises")
        # El orden de los checkboxes en el HTML es fijo (agrupados por
        # zona corporal), así que NO refleja el orden real en que se han
        # ido marcando — exercises_order sí lo lleva (lo mantiene el JS del
        # propio formulario, actualizado con cada clic). Se reordena
        # selected_exercises con eso: se filtra por si acaso a lo que sigue
        # marcado de verdad (por si un ejercicio se desactivó al cambiar de
        # foco corporal) y se añade al final cualquier marcado que faltara
        # ahí (JS desactivado, etc.), para no perder ninguna selección
        # aunque en ese caso el orden no sea exacto.
        exercises_order_raw = request.POST.get("exercises_order", "")
        if exercises_order_raw:
            checked = set(selected_exercises)
            ordered = list(dict.fromkeys(
                s for s in exercises_order_raw.split(",") if s in checked
            ))
            missing = [s for s in selected_exercises if s not in ordered]
            selected_exercises = ordered + missing

        draft, error = api.build_plan_draft(
            user=get_current_user(), weeks=weeks, custom_days=custom_days,
            fitness_level=fitness_level, focus_area=focus_area,
            no_bar_equipment=no_bar_equipment, max_load_kg=max_load_kg,
            selected_exercises=selected_exercises,
        )
        if error:
            messages.error(request, error)
            return render(request, "tasks/plan_ai_form.html", {
                "fitness_level_choices": ai.FITNESS_LEVEL_CHOICES,
                "focus_area_choices": ai.FOCUS_AREA_CHOICES,
                "exercise_choices": ai.all_exercise_choices(),
                "weekdays": Task.WEEKDAYS,
                "selected_days": custom_days or ["0", "2", "4"],
                "weeks": weeks or 12,
                "fitness_level": fitness_level,
                "focus_area": focus_area,
                "no_bar_equipment": no_bar_equipment,
                "max_load_kg": max_load_kg,
                "selected_exercises": selected_exercises,
            })
        request.session["plan_ai_draft"] = draft
        return render(request, "tasks/plan_ai_preview.html", {
            "draft": draft,
            "fitness_level": fitness_level, "focus_area": focus_area,
            "no_bar_equipment": no_bar_equipment, "max_load_kg": max_load_kg,
        })

    if request.method == "POST" and step == "confirmar":
        draft = request.session.get("plan_ai_draft")
        if not draft:
            messages.error(request, "El borrador ha caducado — genera el plan otra vez.")
            return redirect(reverse("tasks:plan_ai_create"))

        # Igual que en la creación manual: sin hora no hay a qué hora
        # avisar ni cuándo cerrar el día solo (ver Task.expire_overdue).
        # Es una decisión del usuario, no algo que la generación
        # automática pueda adivinar — así que se pide aquí, en la vista
        # previa, antes de guardar nada.
        due_time = request.POST.get("due_time") or None
        if not due_time:
            messages.error(request, "Ponle una hora — la notificación y el cierre automático del día la necesitan.")
            return render(request, "tasks/plan_ai_preview.html", {"draft": draft})

        plan_data = {
            "name": request.POST.get("name", "").strip(),
            "notes": request.POST.get("notes", "").strip(),
            "weeks": draft["plan_fields"].get("weeks"),
            "custom_days": draft["plan_fields"].get("custom_days"),
            "started_on": draft["plan_fields"].get("started_on"),
            "reward": request.POST.get("reward", "").strip(),
            "due_time": due_time,
            "is_active": True,
        }

        plan = Plan(user=get_current_user(), plan_type=draft["plan_type"])
        error = api._apply_plan_fields(plan, plan_data)
        if error:
            messages.error(request, error)
            return redirect(reverse("tasks:plan_ai_create"))
        plan.save()

        for idx, item in enumerate(draft.get("items") or []):
            prefix = f"items-{idx}-"
            item_data = dict(item["fields"])
            # Solo estos números son editables en la vista previa — el
            # resto (ejercicio, modo, incrementos ya calculados a partir
            # de las tablas por nivel...) se queda tal como lo propuso la
            # generación automática.
            item_data["is_headline"] = bool(request.POST.get(prefix + "is_headline"))
            for key in (
                "label", "start_sets", "start_reps", "start_seconds", "start_weight_kg",
                "goal_reps", "goal_seconds", "goal_weight_kg", "start_distance_km",
                "start_pace_seconds_per_km", "goal_distance_km", "goal_pace_seconds_per_km",
                "target_minutes",
            ):
                field_name = prefix + key
                if field_name not in request.POST:
                    continue
                raw = request.POST.get(field_name, "").strip()
                item_data[key] = raw if (raw != "" or key == "label") else None

            plan_item = PlanItem(plan=plan)
            item_error = api._apply_plan_item_fields(plan_item, plan, item_data)
            if item_error:
                continue  # se descarta en vez de tirar el plan entero
            plan_item.save()
            if plan_item.is_headline:
                plan.items.exclude(pk=plan_item.pk).update(is_headline=False)

        plan.sync_task()
        request.session.pop("plan_ai_draft", None)
        messages.success(request, f"Plan «{plan.name}» creado automáticamente.")
        return redirect(reverse("tasks:plan_detail", args=[plan.pk]))

    # GET, o "volver" desde la vista previa sin confirmar.
    return render(request, "tasks/plan_ai_form.html", {
        "fitness_level_choices": ai.FITNESS_LEVEL_CHOICES,
        "focus_area_choices": ai.FOCUS_AREA_CHOICES,
        "exercise_choices": ai.all_exercise_choices(),
        "weekdays": Task.WEEKDAYS,
        "selected_days": ["0", "2", "4"],
        "weeks": 12,
        "fitness_level": "",
        "focus_area": "",
        "no_bar_equipment": False,
        # Precargado con un valor por defecto razonable (chaleco lastrado
        # doméstico típico — mismo número que `ai._DEFAULT_MAX_LOAD_KG`)
        # ya que el campo es obligatorio: así el usuario ve un número con
        # sentido en vez de una casilla vacía, y solo tiene que cambiarlo
        # a 0 si de verdad no tiene nada de peso extra.
        "max_load_kg": 20,
        "selected_exercises": [],
    })


def plan_form(request, pk=None):
    """Crear o editar un plan. Los objetivos se editan uno a uno."""
    plan = get_object_or_404(_plans_qs(), pk=pk) if pk else None

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        due_time = request.POST.get("due_time") or None
        if not name:
            messages.error(request, "Ponle un nombre al plan.")
        elif not due_time:
            # Igual que en la tarea suelta: sin hora no hay a qué hora
            # avisar ni cuándo cerrar el día solo (ver Task.expire_overdue
            # — la tarea del plan hereda esta hora en Plan.sync_task()).
            messages.error(
                request,
                "Ponle una hora — la notificación y el cierre automático del día la necesitan.",
            )
        else:
            if plan is None:
                plan = Plan(user=get_current_user())
                # El tipo solo se decide al crear — cambiarlo después
                # dejaría objetivos huérfanos que ya no encajan (un
                # objetivo de ejercicio en un plan que ahora es Estudio
                # no significa nada). El subtipo de Estudio (Idiomas) es
                # la misma decisión un escalón más abajo: cambiarlo
                # después dejaría un temario de vídeos (CourseModule)
                # huérfano igual que pasaría con los objetivos.
                raw_type = request.POST.get("plan_type", "")
                valid_types = {k for k, _ in Plan.PLAN_TYPE_CHOICES}
                plan.plan_type = raw_type if raw_type in valid_types else Plan.PLAN_TYPE_SPORT
                if plan.plan_type == Plan.PLAN_TYPE_STUDY:
                    raw_subtype = request.POST.get("study_subtype", "")
                    valid_subtypes = {k for k, _ in Plan.STUDY_SUBTYPE_CHOICES}
                    plan.study_subtype = raw_subtype if raw_subtype in valid_subtypes else Plan.STUDY_SUBTYPE_GENERAL

            # Idioma + nivel son metadata editable en cualquier momento
            # (a diferencia del subtipo) — no cambian ningún CourseModule
            # ya creado, solo el contexto que se enseña y lo que usará la
            # próxima asignación de cursos del catálogo.
            is_language = plan.plan_type == Plan.PLAN_TYPE_STUDY and plan.study_subtype == Plan.STUDY_SUBTYPE_LANGUAGE
            # Estudio · Hábito simple: el resto de Estudio que no es un
            # curso de idioma — lleva su vídeo/playlist/temporizador
            # propio en vez de un temario (ver más abajo).
            is_study_general = plan.plan_type == Plan.PLAN_TYPE_STUDY and not is_language
            if is_language:
                api._apply_language_plan_fields(plan, {
                    "language_name": request.POST.get("language_name", ""),
                    "level_from": request.POST.get("level_from", ""),
                    "level_to": request.POST.get("level_to", ""),
                    # Checkboxes: puede venir mas de un idioma ya sabido.
                    "known_languages": ", ".join(request.POST.getlist("known_languages")),
                    "language_daily_minutes": request.POST.get("language_daily_minutes", ""),
                    "quiz_every_n_videos": request.POST.get("quiz_every_n_videos", ""),
                })

            # known_languages y language_daily_minutes son obligatorios en
            # un plan de idiomas: sin idioma ya sabido no hay con qué
            # comparar al elegir cursos del catálogo, y sin minutos/día no
            # hay objetivo que corte el vídeo (ver task_video.html —
            # target_minutes sale de aquí). El HTML ya los pide con
            # `required`, pero el de minutos es en verdad un campo oculto
            # que rellena JS — el navegador no lo valida solo — así que el
            # mínimo se repite aquí en el servidor.
            if is_language and not (plan.known_languages and plan.language_daily_minutes):
                messages.error(
                    request,
                    "Un plan de idiomas necesita el idioma que ya sabes y los minutos de vídeo al día.",
                )
            else:
                plan.name = name[:80]
                plan.notes = request.POST.get("notes", "").strip()
                raw_started_on = request.POST.get("started_on", "").strip()
                if raw_started_on:
                    try:
                        plan.started_on = _dt.date.fromisoformat(raw_started_on)
                    except ValueError:
                        plan.started_on = plan.started_on or _dt.date.today()
                else:
                    plan.started_on = plan.started_on or _dt.date.today()
                # Semanas: campo oculto para planes de Idiomas (ver
                # language-fields en plan_form.html -- ahí el ritmo real
                # lo decide lo que se cumple de verdad, no el calendario,
                # ver Plan.auto_close_expired). Si no viene en el POST
                # (input deshabilitado por el toggle) se deja tal cual
                # estaba -- 12 si es un plan nuevo (default del modelo),
                # o lo que ya tuviera si se está editando -- en vez de
                # resetearlo a 12 cada vez que se guarda el plan.
                raw_weeks = request.POST.get("weeks")
                if raw_weeks:
                    try:
                        plan.weeks = max(1, int(raw_weeks))
                    except (TypeError, ValueError):
                        pass
                plan.is_active = bool(request.POST.get("is_active"))
                plan.reward = request.POST.get("reward", "").strip()[:200]
                plan.repeat = request.POST.get("repeat", "custom")
                plan.custom_days = ",".join(request.POST.getlist("custom_days")) or "0,2,4"
                plan.due_time = due_time
                try:
                    plan.interval = max(1, int(request.POST.get("interval", 1)))
                except (TypeError, ValueError):
                    plan.interval = 1

                # Idioma, al CREAR: en vez de guardar ya, se asignan los
                # cursos del catálogo (sin IA, ver api.build_language_plan_draft)
                # y se enseña un paso de revisión antes de guardar nada de
                # verdad — igual que el resto de la app deja revisar un
                # borrador antes de confirmar. Al EDITAR un plan de
                # idiomas ya creado no se toca el temario (mismo criterio
                # de siempre: idioma/nivel son editables, el CourseModule
                # ya generado no se regenera solo).
                if is_language and plan.pk is None:
                    draft, error = api.build_language_plan_draft(
                        user=get_current_user(), weeks=plan.weeks, custom_days=plan.custom_days_list(),
                        language=plan.language_name, level_from=plan.level_from, level_to=plan.level_to,
                        known_languages=plan.known_languages, quiz_every_n_videos=plan.quiz_every_n_videos,
                        language_daily_minutes=plan.language_daily_minutes,
                    )
                    if error:
                        messages.error(request, error)
                    else:
                        draft["plan_fields"]["name"] = plan.name
                        draft["plan_fields"]["notes"] = plan.notes
                        draft["due_time"] = due_time
                        draft["reward"] = plan.reward
                        request.session["plan_language_draft"] = draft
                        return redirect(reverse("tasks:plan_language_confirm"))
                else:
                    plan.save()
                    # El plan crea y mantiene su propia tarea: el usuario
                    # no tiene que crear nada a mano ni saber qué es un
                    # circuito.
                    plan.sync_task()

                    # Estudio · Hábito simple: el vídeo/playlist/temporizador
                    # de la tarea diaria se rellena aquí mismo, en el mismo
                    # paso — así el plan sale ya con su tarea lista para
                    # comprobar, en vez de dejar al usuario un plan "vacío"
                    # que solo se completa si además recuerda ir a "+ Añadir
                    # objetivo" (ver plan_item_form, que sigue existiendo
                    # para poder cambiarlo más tarde).
                    if is_study_general:
                        item = plan.items.filter(is_headline=True).first()
                        if item is None:
                            item = PlanItem(plan=plan, is_headline=True, progression=PlanItem.PROG_COMPLETION)
                        item.exercise = None
                        item.series_id = plan.task_series_id
                        item.progression = PlanItem.PROG_COMPLETION
                        item.is_headline = True
                        item.youtube_video_id = request.POST.get("youtube_video_id", "").strip()[:255]
                        item.youtube_playlist_id = request.POST.get("youtube_playlist_id", "").strip()[:255]
                        raw_minutes = request.POST.get("target_minutes", "").strip()
                        try:
                            item.target_minutes = max(1, int(raw_minutes)) if raw_minutes else None
                        except (TypeError, ValueError):
                            item.target_minutes = None
                        raw_count = request.POST.get("target_video_count", "").strip()
                        try:
                            item.target_video_count = max(1, int(raw_count)) if raw_count else None
                        except (TypeError, ValueError):
                            item.target_video_count = None
                        # Con playlist, uno de los dos es obligatorio: sin
                        # ninguno, el seguimiento de progreso
                        # (Plan._study_playlist_progress) se quedaría
                        # siempre en el primer vídeo y no avanzaría nunca.
                        # Un hábito sin vídeo ni playlist (temporizador
                        # manual, tipo Enfoque) no necesita esto.
                        if item.youtube_playlist_id and not (item.target_minutes or item.target_video_count):
                            messages.error(
                                request,
                                "Con una playlist, pon minutos al día o número de vídeos al día — "
                                "hace falta uno de los dos.",
                            )
                            return redirect(reverse("tasks:plan_edit", args=[plan.pk]))
                        item.save()
                        # Playlist con seguimiento de progreso: se refresca
                        # la caché de vídeos justo al guardar (nunca desde
                        # sync_task, que se llama en cada carga de la lista
                        # de tareas y sería demasiado caro/lento llamar ahí
                        # a la API de YouTube).
                        item.sync_playlist_videos()
                        # La tarea ya se creó/actualizó arriba sin el vídeo
                        # (no existía el objetivo todavía) — se sincroniza
                        # otra vez para que recoja lo que se acaba de poner.
                        plan.sync_task()

                    messages.success(request, f"Plan «{plan.name}» guardado.")
                    return redirect(reverse("tasks:plan_detail", args=[plan.pk]))

    # Si esto era una creación (sin pk) y se quedó a medias por el error
    # de idiomas de arriba, `plan` es ya una instancia sin guardar — no
    # se le pasa tal cual a la plantilla, o se vería como "editar" un
    # plan que en realidad no existe (radios bloqueados, tipo fijado...).
    # Mismo criterio que ya tenía el error de "falta el nombre".
    display_plan = plan if pk else None
    # Para poder rellenar el vídeo/playlist/temporizador de un plan de
    # Estudio · Hábito simple ya creado (editar reutiliza este mismo
    # formulario, ver arriba).
    study_headline = (
        display_plan.headline
        if display_plan and display_plan.plan_type == Plan.PLAN_TYPE_STUDY
        and display_plan.study_subtype != Plan.STUDY_SUBTYPE_LANGUAGE
        else None
    )
    # Desplegables de idioma: solo los que ya tienen curso verificado en
    # el catalogo (ver api.catalog_language_options) -- si el plan que
    # se edita quedo con un idioma que luego se desactivo/desaparecio
    # del catalogo, se anade igual para no perder el valor guardado.
    language_choices = api.catalog_language_options()
    if display_plan and display_plan.language_name and display_plan.language_name not in language_choices:
        language_choices = language_choices + [display_plan.language_name]
    native_language_choices = api.catalog_native_language_options()
    known_languages_selected = [
        s.strip() for s in (display_plan.known_languages.split(",") if display_plan and display_plan.known_languages else [])
        if s.strip()
    ]
    for lang in known_languages_selected:
        if lang not in native_language_choices:
            native_language_choices.append(lang)

    return render(request, "tasks/plan_form.html", {
        "plan": display_plan,
        "weekdays": Task.WEEKDAYS,
        "selected_days": display_plan.custom_days_list() if display_plan else ["0", "2", "4"],
        "plan_type_choices": Plan.PLAN_TYPE_CHOICES,
        "study_subtype_choices": Plan.STUDY_SUBTYPE_CHOICES,
        "cefr_level_choices": Plan.CEFR_LEVEL_CHOICES,
        "study_headline": study_headline,
        "language_choices": language_choices,
        "native_language_choices": native_language_choices,
        "known_languages_selected": known_languages_selected,
    })


def plan_language_confirm(request):
    """
    Paso 2 de crear un plan de Estudio · Idiomas a mano (paso 1:
    `plan_form`, que ya validó el idioma/nivel/minutos y armó el
    borrador vía `api.build_language_plan_draft`).

    Revisa qué cursos del catálogo se han asignado — sin IA, ver
    docstring de `api.build_language_plan_draft` — y confirma. Nada se
    guarda hasta el POST: si algún nivel pedido todavía no tiene curso
    verificado se avisa (`missing_levels`) pero no bloquea, el resto del
    temario se guarda igual.
    """
    draft = request.session.get("plan_language_draft")
    if not draft:
        messages.error(request, "Los datos del plan han caducado — vuelve a rellenarlo.")
        return redirect(reverse("tasks:plan_create"))

    if request.method == "POST":
        due_time = request.POST.get("due_time") or draft.get("due_time")
        if not due_time:
            messages.error(request, "Ponle una hora — la notificación y el cierre automático del día la necesitan.")
            return render(request, "tasks/plan_language_confirm.html", {"draft": draft})

        # Se expande el catálogo elegido (vídeo a vídeo, vía YouTube)
        # solo ahora que el usuario confirma de verdad — así no se gasta
        # cuota de la API de YouTube en un borrador que a lo mejor se
        # descarta (mismo criterio de siempre, ver expand_language_selection).
        course_modules, error = api.expand_language_selection(draft.get("selected") or [])
        if error:
            messages.error(request, error)
            return redirect(reverse("tasks:plan_create"))

        plan_data = dict(draft["plan_fields"])
        plan_data["name"] = request.POST.get("name", "").strip()[:80] or plan_data.get("name")
        plan_data["notes"] = request.POST.get("notes", "").strip()
        plan_data["reward"] = request.POST.get("reward", "").strip()[:200]
        plan_data["due_time"] = due_time
        plan_data["is_active"] = True

        plan = Plan(user=get_current_user(), plan_type=Plan.PLAN_TYPE_STUDY)
        error = api._apply_plan_fields(plan, plan_data)
        if not error:
            api._apply_language_plan_fields(plan, plan_data)
        if error:
            messages.error(request, error)
            return redirect(reverse("tasks:plan_create"))
        plan.save()

        for module in course_modules:
            module.plan = plan
            module.save()

        plan.sync_task()
        request.session.pop("plan_language_draft", None)
        messages.success(request, f"Plan «{plan.name}» creado.")
        return redirect(reverse("tasks:plan_detail", args=[plan.pk]))

    return render(request, "tasks/plan_language_confirm.html", {"draft": draft})


@require_POST
def plan_language_retry(request, pk):
    """
    Red de seguridad para un plan de idioma que se quedó sin temario —
    ej. porque al confirmar falló la llamada a YouTube, o porque el
    catálogo no tenía nada para ese nivel en su momento y desde entonces
    se han añadido cursos nuevos con `add_course_playlist`. Sin esto, un
    plan así se queda atascado para siempre («este curso todavía no
    tiene vídeos» en plan_detail.html, sin ninguna forma de arreglarlo
    salvo borrar el plan y volver a crearlo desde cero).

    Reutiliza el idioma/nivel/idiomas ya guardados en el propio plan —
    no hace falta volver a pedirlos — y AÑADE los módulos nuevos que
    encuentre sin tocar los que ya hubiera.
    """
    plan = get_object_or_404(_plans_qs(), pk=pk)
    is_language = plan.plan_type == Plan.PLAN_TYPE_STUDY and plan.study_subtype == Plan.STUDY_SUBTYPE_LANGUAGE
    if not is_language:
        return redirect(reverse("tasks:plan_detail", args=[plan.pk]))

    if plan.course_modules.exists():
        messages.info(request, "Este curso ya tiene vídeos asignados.")
        return redirect(reverse("tasks:plan_detail", args=[plan.pk]))

    draft, error = api.build_language_plan_draft(
        user=get_current_user(), weeks=plan.weeks, custom_days=plan.custom_days_list(),
        language=plan.language_name, level_from=plan.level_from, level_to=plan.level_to,
        known_languages=plan.known_languages, quiz_every_n_videos=plan.quiz_every_n_videos,
        language_daily_minutes=plan.language_daily_minutes,
    )
    if error:
        messages.error(request, error)
        return redirect(reverse("tasks:plan_detail", args=[plan.pk]))

    course_modules, error = api.expand_language_selection(draft.get("selected") or [])
    if error:
        messages.error(request, error)
        return redirect(reverse("tasks:plan_detail", args=[plan.pk]))

    for module in course_modules:
        module.plan = plan
        module.save()
    plan.sync_task()
    messages.success(request, "Vídeos asignados — ya puedes empezar el curso.")
    return redirect(reverse("tasks:plan_detail", args=[plan.pk]))


@require_POST
def plan_delete(request, pk):
    plan = get_object_or_404(_plans_qs(), pk=pk)
    plan.deleted_at = timezone.now()
    plan.save(update_fields=["deleted_at", "updated_at"])
    plan.sync_task()          # retira la tarea pendiente
    messages.success(request, "Plan eliminado.")
    return redirect(reverse("tasks:task_list"))


def _plan_summary_items(plan):
    """Un resumen ligero por objetivo: cuántas veces se cumplió, en qué
    escalón se quedó. Sin la tabla de progresión entera — esto es un
    vistazo hacia atrás, no una pantalla de trabajo."""
    items = []
    for item in plan.items.select_related("exercise").all():
        successes, _ = item.successes_and_streak()
        items.append({
            "item": item,
            "successes": successes,
            "step": item.current_step(),
            "target": item.current_target(),
        })
    return items


def plan_close(request, pk):
    """
    Cierre de ciclo: distinto de borrar. GET enseña el resumen (llevas
    cumplidos tantos escalones, tal racha…) con un botón para
    confirmar; POST cierra de verdad — dos pasos porque cerrar no se
    deshace con un "deshacer" fácil como sí lo tiene marcar una tarea.

    Una vez cerrado, el plan deja de generar tareas y sale de la lista
    de activos, pero se queda en "Planes cerrados" para poder mirar
    atrás — no es lo mismo que eliminar.
    """
    plan = get_object_or_404(_plans_qs(), pk=pk)

    if request.method == "POST" and not plan.closed_at:
        plan.final_progress_pct = plan.progress_pct()
        plan.closed_at = timezone.now()
        plan.is_active = False
        plan.save(update_fields=["final_progress_pct", "closed_at", "is_active", "updated_at"])
        plan.sync_task()  # retira la tarea pendiente, como al pausar

    return render(request, "tasks/plan_close.html", {
        "plan": plan,
        "progress": plan.final_progress_pct if plan.closed_at else plan.progress_pct(),
        "items": _plan_summary_items(plan),
    })


def plan_item_form(request, plan_pk, pk=None):
    """
    Un objetivo dentro del plan.

    El formulario enseña solo lo que aplica a cada tipo de progresión:
    no tiene sentido pedir "rango de repeticiones" en algo de
    cumplimiento, ni "peso" en una plancha.
    """
    plan = get_object_or_404(_plans_qs(), pk=plan_pk)
    item = get_object_or_404(PlanItem, pk=pk, plan=plan) if pk else None

    if plan.plan_type == Plan.PLAN_TYPE_GENERAL:
        # General no tiene nada que configurar — se creó solo al crear
        # el plan. Si alguien llega aquí de todos modos (enlace viejo,
        # yendo hacia atrás en el navegador), se le devuelve sin líos.
        messages.info(request, "Un plan General no necesita objetivos — la propia tarea diaria ya lo es.")
        return redirect(reverse("tasks:plan_detail", args=[plan.pk]))

    if request.method == "POST":
        if item is None:
            item = PlanItem(plan=plan)

        def _int(name, default):
            try:
                return max(0, int(request.POST.get(name) or default))
            except (TypeError, ValueError):
                return default

        def _float(name, default):
            try:
                return max(0.0, float((request.POST.get(name) or default)))
            except (TypeError, ValueError):
                return default

        if plan.plan_type == Plan.PLAN_TYPE_STUDY:
            # El objetivo ES el vídeo/playlist/temporizador — apunta a
            # la propia tarea diaria del plan, no a un ejercicio.
            item.exercise = None
            item.series_id = plan.task_series_id
            item.label = request.POST.get("label", "").strip()[:80]
            item.progression = PlanItem.PROG_COMPLETION
            item.is_headline = True
            item.youtube_video_id = request.POST.get("youtube_video_id", "").strip()[:255]
            item.youtube_playlist_id = request.POST.get("youtube_playlist_id", "").strip()[:255]
            raw_minutes = request.POST.get("target_minutes", "").strip()
            item.target_minutes = max(1, _int("target_minutes", 0)) if raw_minutes else None
            raw_count = request.POST.get("target_video_count", "").strip()
            item.target_video_count = max(1, _int("target_video_count", 0)) if raw_count else None
            # Con playlist, uno de los dos es obligatorio: sin ninguno, el
            # seguimiento de progreso (Plan._study_playlist_progress) se
            # quedaría siempre en el primer vídeo y no avanzaría nunca. Un
            # hábito sin vídeo ni playlist (temporizador manual, tipo
            # Enfoque) no necesita esto.
            if item.youtube_playlist_id and not (item.target_minutes or item.target_video_count):
                messages.error(
                    request,
                    "Con una playlist, pon minutos al día o número de vídeos al día — "
                    "hace falta uno de los dos.",
                )
                return redirect(request.path)
            item.save()
            # Se refresca la caché de vídeos justo al guardar (nunca desde
            # sync_task, que se llama en cada carga de la lista de tareas
            # y sería demasiado caro/lento llamar ahí a la API de YouTube).
            item.sync_playlist_videos()
            plan.sync_task()
            messages.success(request, "Objetivo guardado.")
            return redirect(reverse("tasks:plan_detail", args=[plan.pk]))

        # plan_type == Deporte, a partir de aquí.
        slug = request.POST.get("exercise") or ""
        item.exercise = Exercise.objects.filter(slug=slug).first() if slug else None
        item.label = request.POST.get("label", "").strip()[:80]

        # Cómo se hace el ejercicio — no aplica a running.
        es_running = item.exercise and item.exercise.mode == Exercise.MODE_DISTANCE
        if es_running:
            item.sport_mode = ""
        else:
            valid_modes = {k for k, _ in PlanItem.SPORT_MODE_CHOICES}
            raw_mode = request.POST.get("sport_mode", "")
            item.sport_mode = raw_mode if raw_mode in valid_modes else ""
        if item.sport_mode == PlanItem.SPORT_MODE_VIDEO:
            item.youtube_video_id = request.POST.get("youtube_video_id", "").strip()[:255]
            item.youtube_playlist_id = request.POST.get("youtube_playlist_id", "").strip()[:255]
            raw_minutes = request.POST.get("target_minutes", "").strip()
            item.target_minutes = max(1, int(raw_minutes or 0)) if raw_minutes else None
            raw_count = request.POST.get("target_video_count", "").strip()
            item.target_video_count = max(1, int(raw_count or 0)) if raw_count else None

        valid = {k for k, _ in PlanItem.PROGRESSION_CHOICES}
        default_prog = (
            PlanItem.PROG_DISTANCE if item.exercise and item.exercise.mode == Exercise.MODE_DISTANCE
            else PlanItem.PROG_REPS
        )
        prog = request.POST.get("progression", default_prog)
        item.progression = prog if prog in valid else default_prog

        item.start_sets = _int("start_sets", 3) or 1
        item.start_reps = _int("start_reps", 8)
        item.start_seconds = _int("start_seconds", 40)
        item.start_weight_kg = _float("start_weight_kg", 0)

        item.goal_sets = _int("goal_sets", 0) or None
        item.goal_reps = _int("goal_reps", 0) or None
        item.goal_seconds = _int("goal_seconds", 0) or None
        gw = request.POST.get("goal_weight_kg")
        item.goal_weight_kg = _float("goal_weight_kg", 0) if gw else None

        # Running: distancia en km (decimales, por eso _float) y ritmo
        # en segundos por km (entero, viene del mismo desplegable de
        # presets que ya usa una tarea suelta de running).
        item.start_distance_km = _float("start_distance_km", 1.0) or 1.0
        item.start_pace_seconds_per_km = _int("start_pace_seconds_per_km", 420) or 420
        gd = request.POST.get("goal_distance_km")
        item.goal_distance_km = _float("goal_distance_km", 0) if gd else None
        gp = request.POST.get("goal_pace_seconds_per_km")
        item.goal_pace_seconds_per_km = _int("goal_pace_seconds_per_km", 0) if gp else None
        item.distance_increment_km = _float("distance_increment_km", 0.5) or 0.5
        item.pace_decrement_seconds = _int("pace_decrement_seconds", 10) or 10

        item.sessions_per_step = _int("sessions_per_step", 2) or 1
        item.reps_increment = _int("reps_increment", 1) or 1
        item.weight_increment_kg = _float("weight_increment_kg", 2.5) or 2.5
        item.rep_range_low = _int("rep_range_low", 6) or 1
        item.deload_after_failures = _int("deload_after_failures", 3)
        item.is_headline = bool(request.POST.get("is_headline"))

        # Obligatorio de verdad: sin esto, un objetivo se puede guardar
        # "vacío" y al pulsar play la app no sabe qué pantalla enseñar
        # (cae en un comportamiento antiguo que confunde más que ayuda).
        error = None
        if not item.exercise:
            error = "Elige un ejercicio."
        elif es_running and not item.goal_distance_km:
            error = "Pon una distancia de destino — sin eso el plan no sabría cuándo has llegado."
        elif not es_running and not item.sport_mode:
            error = "Elige cómo la vas a completar: cámara, circuito o vídeo."
        elif item.sport_mode == PlanItem.SPORT_MODE_VIDEO and not (item.youtube_video_id or item.youtube_playlist_id):
            error = "Pon un vídeo o una playlist de YouTube."

        if error:
            return render(request, "tasks/plan_item_form.html", {
                "plan": plan, "item": item, "error": error,
                "exercises": Exercise.objects.filter(is_active=True),
                "progressions": PlanItem.PROGRESSION_CHOICES,
                "pace_presets": Task.PACE_PRESETS,
                "sessions_per_week": max(1, len(plan.custom_days_list())),
            })

        item.save()

        # Solo puede haber una medida principal.
        if item.is_headline:
            plan.items.exclude(pk=item.pk).update(is_headline=False)

        plan.sync_task()
        messages.success(request, "Objetivo guardado.")
        return redirect(reverse("tasks:plan_detail", args=[plan.pk]))

    return render(request, "tasks/plan_item_form.html", {
        "plan": plan,
        "item": item,
        "exercises": Exercise.objects.filter(is_active=True),
        "progressions": PlanItem.PROGRESSION_CHOICES,
        "pace_presets": Task.PACE_PRESETS,
        # Para poder calcular el ritmo de progresión a partir de "en
        # cuántas semanas quiero llegar" en vez de que el usuario tenga
        # que hacer la cuenta él mismo de cuánto subir cada escalón.
        "sessions_per_week": max(1, len(plan.custom_days_list())),
    })


@require_POST
def plan_item_delete(request, plan_pk, pk):
    plan = get_object_or_404(_plans_qs(), pk=plan_pk)
    get_object_or_404(PlanItem, pk=pk, plan=plan).delete()
    messages.success(request, "Objetivo eliminado.")
    return redirect(reverse("tasks:plan_detail", args=[plan.pk]))


def plan_session(request, pk, plan_pk):
    """
    La sesión de hoy según el plan: sus ejercicios, en orden, cada uno
    con el objetivo que toca. Sin elegir nada — el plan ya lo decidió.
    """
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    gate = _require_warmup(request, task)
    if gate:
        return gate
    plan = get_object_or_404(_plans_qs(), pk=plan_pk)
    items = plan.session_items()
    if not items:
        messages.error(request, "Este plan todavía no tiene ejercicios que entrenar.")
        return redirect(reverse("tasks:plan_detail", args=[plan.pk]))
    return render(request, "tasks/plan_session.html", {
        "task": task, "plan": plan, "items": items,
        "items_json": json.dumps(items),
    })


@require_POST
def plan_session_save(request, pk, plan_pk):
    """
    Guarda la sesión del plan: una entrada por ejercicio, con el objetivo
    que estaba vigente. Al terminar, la tarea queda hecha y el plan
    avanza solo.
    """
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    plan = get_object_or_404(_plans_qs(), pk=plan_pk)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    targets = {}
    for it in plan.items.select_related("exercise"):
        if it.exercise:
            targets[it.exercise.slug] = it.current_target()

    created = 0
    for b in data.get("breakdown", []) or []:
        if not isinstance(b, dict):
            continue
        slug = str(b.get("exercise", ""))[:32]
        if not slug:
            continue
        t = targets.get(slug, {})
        num = lambda k: int(b[k]) if isinstance(b.get(k), (int, float)) else 0
        WorkoutSession.objects.create(
            task=task, user=get_current_user(), plan=plan, series_id=task.series_id,
            exercise=slug,
            total_reps=num("reps"), total_sets=num("sets"),
            session_duration_seconds=num("seconds"),
            target_sets=t.get("sets"), target_reps=t.get("reps"),
            target_seconds=t.get("seconds"),
        )
        created += 1

    if not created:
        return JsonResponse({"ok": False, "error": "Sin datos que guardar"}, status=400)

    messages.success(request, f"Sesión de «{plan.name}» guardada.")
    # La tarea se marca hecha en task_cooldown — falta el enfriamiento
    # obligatorio.
    return JsonResponse({"ok": True, "redirect_url": reverse("tasks:task_cooldown", args=[task.pk])})


# ---------------------------------------------------- app móvil: updates

def mobile_apk_download(request):
    """
    Sirve el último APK publicado a mano en mobile_releases/ (ver
    utils.read_mobile_release y el README, sección "Actualizaciones de
    la app móvil"). La app móvil llega aquí abriendo esta URL en el
    navegador del sistema (no vía fetch), después de ver en /api/meta/
    que hay una versión más reciente que la suya.

    Sigue detrás del candado Basic Auth de siempre — BasicAuthMiddleware
    envuelve toda la app, y aquí no se hace ninguna excepción a
    propósito (se decidió así conscientemente en vez de dejarla pública).
    """
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    release = read_mobile_release()
    if not release:
        raise Http404("Todavía no hay ninguna build de la app publicada.")
    apk_path = release["apk_path"]
    response = FileResponse(
        open(apk_path, "rb"),
        content_type="application/vnd.android.package-archive",
    )
    response["Content-Disposition"] = f'attachment; filename="{apk_path.name}"'
    return response
