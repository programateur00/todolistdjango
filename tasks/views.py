import json

from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Exercise, Occurrence, Task, WorkoutSession
from .utils import get_current_user


def _read_category(request, default=Task.CATEGORY_GENERAL):
    """Lee la categoría del POST/GET, validando contra choices."""
    raw = request.POST.get("category", default) or default
    valid = {key for key, _ in Task.CATEGORY_CHOICES}
    return raw if raw in valid else default


def _read_subcategory(request, default=""):
    """Lee la subcategoría (solo tiene sentido si category=sport)."""
    raw = request.POST.get("subcategory", default) or default
    valid = {key for key, _ in Task.SUBCATEGORY_CHOICES}
    return raw if raw in valid else default


def task_list(request):
    # Se comprueba en cada visita si alguna tarea con hora límite ya
    # venció sin completarse, y se marca sola como "no hecha".
    # (No usamos cron: en el hosting gratuito no está disponible, y al
    # ser una app de un solo usuario, comprobarlo al abrir la página
    # es suficiente.)
    Task.expire_overdue()

    # Filtro opcional por categoría (?cat=sport, ?cat=study, …)
    cat = request.GET.get("cat") or ""
    valid_cats = {key for key, _ in Task.CATEGORY_CHOICES}
    active_category = cat if cat in valid_cats else ""

    base_qs = Task.objects.filter(user=get_current_user())
    if active_category:
        base_qs = base_qs.filter(category=active_category)

    pending_tasks = base_qs.filter(is_done=False)
    completed_tasks = base_qs.filter(is_done=True)

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
    })


def task_create(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        if title:
            Task.objects.create(
                title=title,
                notes=request.POST.get("notes", "").strip(),
                category=_read_category(request),
                subcategory=_read_subcategory(request),
                due_date=request.POST.get("due_date") or None,
                due_time=request.POST.get("due_time") or None,
                repeat=request.POST.get("repeat", Task.REPEAT_NONE),
                interval=request.POST.get("interval") or 1,
                custom_days=",".join(request.POST.getlist("custom_days")),
                is_important=bool(request.POST.get("is_important")),
                user=get_current_user(),
            )
            messages.success(request, "Tarea creada.")
        return redirect(reverse("tasks:task_list"))

    initial_title = request.GET.get("title", "")
    return render(request, "tasks/task_form.html", {
        "repeat_choices": Task.REPEAT_CHOICES,
        "weekdays": Task.WEEKDAYS,
        "category_choices": Task.CATEGORY_CHOICES,
        "subcategory_choices": Task.SUBCATEGORY_CHOICES,
        "initial_title": initial_title,
    })


def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    if request.method == "POST":
        task.title = request.POST.get("title", task.title).strip()
        task.notes = request.POST.get("notes", "").strip()
        task.category = _read_category(request, default=task.category)
        task.subcategory = _read_subcategory(request, default=task.subcategory)
        task.due_date = request.POST.get("due_date") or None
        task.due_time = request.POST.get("due_time") or None
        task.repeat = request.POST.get("repeat", Task.REPEAT_NONE)
        task.interval = request.POST.get("interval") or 1
        task.custom_days = ",".join(request.POST.getlist("custom_days"))
        task.is_important = bool(request.POST.get("is_important"))
        task.save()
        messages.success(request, "Tarea actualizada.")
        return redirect(reverse("tasks:task_list"))
    return render(request, "tasks/task_form.html", {
        "task": task,
        "repeat_choices": Task.REPEAT_CHOICES,
        "weekdays": Task.WEEKDAYS,
        "category_choices": Task.CATEGORY_CHOICES,
        "subcategory_choices": Task.SUBCATEGORY_CHOICES,
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


def task_workout(request, pk):
    """
    Página de entreno para una tarea. En dos pasos:
    1. Sin ?exercise= en la URL: muestra el catálogo de ejercicios activos
       para elegir cuál tocar hoy — filtrado por la subcategoría de la
       tarea (tren superior / tren inferior / running) si la tiene. Las
       tareas sin subcategoría (o antiguas, de antes de que existiera)
       ven el catálogo entero, para no dejar a nadie sin opciones.
    2. Con ?exercise=<slug>:
       - mode="pose" con contador ya construido (de momento solo
         dominadas) -> cámara con MediaPipe.
       - mode="distance" (running) -> formulario manual (cinta, reloj,
         Samsung Health…), no hay cámara para esto.
       - cualquier otro caso (ej. abdominales/sentadillas, que están en
         el catálogo pero aún no tienen contador) -> vuelve al selector
         con un aviso, en vez de romper.
    """
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    exercise_slug = request.GET.get("exercise")

    exercises_qs = Exercise.objects.filter(is_active=True)
    if task.subcategory:
        exercises_qs = exercises_qs.filter(body_area=task.subcategory)

    if not exercise_slug:
        return render(request, "tasks/task_workout_select.html", {
            "task": task, "exercises": exercises_qs,
        })

    exercise = get_object_or_404(Exercise, slug=exercise_slug, is_active=True)

    if exercise.mode == Exercise.MODE_DISTANCE:
        return render(request, "tasks/task_workout_manual.html", {
            "task": task, "exercise": exercise,
        })

    # De momento el único contador que existe en workout.js es el de
    # dominadas. Cuando se añada uno nuevo, esta comprobación es lo único
    # que hay que ampliar (o quitar del todo si ya cubre todos los modos).
    if exercise.mode != Exercise.MODE_POSE or exercise.counter_key != "pullup":
        return render(request, "tasks/task_workout_select.html", {
            "task": task, "exercises": exercises_qs, "unsupported": exercise,
        })

    return render(request, "tasks/task_workout.html", {"task": task, "exercise": exercise})


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

    WorkoutSession.objects.create(
        task=task,
        user=get_current_user(),
        series_id=task.series_id,
        exercise=exercise_value,
        total_reps=total_reps,
        total_sets=total_sets,
        sets=clean_sets,
        session_duration_seconds=int(data.get("session_duration_seconds", 0)),
        avg_rep_seconds=avg_rep_seconds,
        rest_alerts_triggered=int(data.get("rest_alerts_triggered", 0)),
        rep_durations=rep_durations,
    )

    task.mark_done()

    messages.success(
        request,
        f"Sesión guardada: {total_reps} {exercise_label} en {total_sets} serie(s)"
        + (f", ritmo medio {avg_rep_seconds}s/rep." if avg_rep_seconds else "."),
    )
    return JsonResponse({"ok": True, "redirect_url": reverse("tasks:task_list")})


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

    task.mark_done()

    bits = []
    if distance_km:
        bits.append(f"{distance_km}km")
    if duration_minutes:
        bits.append(f"{duration_minutes:.0f} min")
    if steps:
        bits.append(f"{steps} pasos")
    messages.success(request, "Sesión de running guardada: " + ", ".join(bits) + ".")
    return redirect(reverse("tasks:task_list"))


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

    return render(request, "tasks/stats_list.html", {"series_list": series_list})


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
