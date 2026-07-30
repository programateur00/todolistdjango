import json

from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

import datetime as _dt

from django.utils import timezone

from .models import (
    Exercise, Occurrence, Plan, PlanItem, Routine, RoutineItem, Task, WorkoutSession,
)
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
                avoid_question=request.POST.get("avoid_question", "").strip()[:120],
                avoid_success_label=request.POST.get("avoid_success_label", "").strip()[:32],
                avoid_fail_label=request.POST.get("avoid_fail_label", "").strip()[:32],
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
        task.avoid_question = request.POST.get("avoid_question", "").strip()[:120]
        task.avoid_success_label = request.POST.get("avoid_success_label", "").strip()[:32]
        task.avoid_fail_label = request.POST.get("avoid_fail_label", "").strip()[:32]
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
    1. Sin ?exercise= en la URL: muestra el catálogo de ejercicios activos
       para elegir cuál tocar hoy — filtrado por la subcategoría de la
       tarea (tren superior / tren inferior / running) si la tiene. Las
       tareas sin subcategoría (o antiguas, de antes de que existiera)
       ven el catálogo entero, para no dejar a nadie sin opciones. Los
       ejercicios mode="timed" (plancha, crunch…) NO salen aquí sueltos:
       solo tienen sentido dentro de un circuito (Routine), así que se
       ofrecen aparte, como circuitos completos.
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

    # Si la tarea la generó un plan, no hay nada que elegir: el plan ya
    # decidió qué ejercicios y con qué objetivo. Se va directo a la
    # sesión, que es lo que hace que esto sea simple de usar.
    plan = task.plan
    if plan and not exercise_slug and plan.items.filter(exercise__isnull=False).exists():
        return redirect(reverse("tasks:plan_session", args=[task.pk, plan.pk]))

    exercises_qs = Exercise.objects.filter(is_active=True).exclude(mode=Exercise.MODE_TIMED)
    routines_qs = Routine.objects.filter(user=get_current_user())
    if task.subcategory:
        exercises_qs = exercises_qs.filter(body_area=task.subcategory)
        routines_qs = routines_qs.filter(subcategory=task.subcategory)

    if not exercise_slug:
        return render(request, "tasks/task_workout_select.html", {
            "task": task, "exercises": exercises_qs, "routines": routines_qs,
        })

    exercise = get_object_or_404(Exercise, slug=exercise_slug, is_active=True)

    if exercise.mode == Exercise.MODE_DISTANCE:
        return render(request, "tasks/task_workout_manual.html", {
            "task": task, "exercise": exercise,
        })

    # Contadores implementados en workout.js. Un ejercicio con mode=pose
    # pero sin contador (sentadillas, abdominales) está en el catálogo
    # pero todavía no se puede contar con la cámara.
    if exercise.mode != Exercise.MODE_POSE or exercise.counter_key not in COUNTERS:
        return render(request, "tasks/task_workout_select.html", {
            "task": task, "exercises": exercises_qs, "routines": routines_qs, "unsupported": exercise,
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

    # Solo se aceptan ejercicios mode="timed" reales — evita que alguien
    # cuele por POST un id de ejercicio que no toca aquí.
    valid_exercise_ids = set(
        Exercise.objects.filter(id__in=exercise_ids, mode=Exercise.MODE_TIMED).values_list("id", flat=True)
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
    exercises = Exercise.objects.filter(
        mode=Exercise.MODE_TIMED, is_active=True
    ).exclude(slug="ab-circuit")
    return render(request, "tasks/routine_form.html", {
        "exercises": exercises,
        "subcategory_choices": Task.SUBCATEGORY_CHOICES,
        "initial_subcategory": request.GET.get("subcategory", ""),
        "next_url": request.GET.get("next", ""),
    })


def routine_edit(request, pk):
    routine = get_object_or_404(Routine, pk=pk, user=get_current_user())
    if request.method == "POST":
        return _save_routine(request, routine=routine)
    exercises = Exercise.objects.filter(
        mode=Exercise.MODE_TIMED, is_active=True
    ).exclude(slug="ab-circuit")
    return render(request, "tasks/routine_form.html", {
        "routine": routine,
        "exercises": exercises,
        "subcategory_choices": Task.SUBCATEGORY_CHOICES,
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
    """Reproductor del circuito: cronómetro por ejercicio + descanso,
    encadenando todos los RoutineItem de la rutina. No usa cámara ni
    MediaPipe — es solo temporizador (ver static/js/circuit.js)."""
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    routine = get_object_or_404(Routine, pk=routine_pk, user=get_current_user())
    items = list(routine.items.select_related("exercise"))

    if not items:
        messages.error(request, "Este circuito todavía no tiene ejercicios.")
        return redirect(reverse("tasks:task_workout", args=[task.pk]))

    items_data = [
        {
            "slug": it.exercise.slug,
            "name": it.exercise.name,
            "work": it.effective_work_seconds,
            "rest": it.effective_rest_seconds,
        }
        for it in items
    ]
    return render(request, "tasks/routine_play.html", {
        "task": task, "routine": routine, "items": items, "items_json": json.dumps(items_data),
    })


@require_POST
def routine_save(request, pk, routine_pk):
    """Guarda el resultado del circuito al terminar (o al cortarlo antes
    de tiempo). Un único WorkoutSession con el desglose por ejercicio en
    `sets`, igual que ya se hace con las series de dominadas."""
    task = get_object_or_404(Task, pk=pk, user=get_current_user())
    routine = get_object_or_404(Routine, pk=routine_pk, user=get_current_user())

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    raw_breakdown = data.get("breakdown", [])
    breakdown = []
    total_seconds = 0
    if isinstance(raw_breakdown, list):
        for b in raw_breakdown:
            if not isinstance(b, dict):
                continue
            slug = str(b.get("exercise", ""))[:32]
            seconds = int(b.get("seconds", 0)) if isinstance(b.get("seconds"), (int, float)) else 0
            breakdown.append({"exercise": slug, "seconds": seconds})
            total_seconds += seconds

    if not breakdown:
        return JsonResponse({"ok": False, "error": "Sin datos que guardar"}, status=400)

    WorkoutSession.objects.create(
        task=task,
        user=get_current_user(),
        routine=routine,
        exercise="ab-circuit",
        session_duration_seconds=total_seconds,
        sets=breakdown,
        total_sets=len(breakdown),
    )
    task.mark_done()

    messages.success(
        request,
        f"Circuito «{routine.name}» completado: {len(breakdown)} ejercicio(s), {total_seconds}s.",
    )
    return JsonResponse({"ok": True, "redirect_url": reverse("tasks:task_list")})


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


# ─────────────────────────────────────────────────────────────────────
# Planes de progresión
# ─────────────────────────────────────────────────────────────────────

# Contadores que existen de verdad en workout.js.
COUNTERS = {"pullup", "dip"}


def _plans_qs():
    return Plan.objects.filter(user=get_current_user(), deleted_at__isnull=True)


def plan_list(request):
    """Los planes, con su medida principal y cuánto llevas."""
    plans = []
    for p in _plans_qs():
        head = p.headline
        plans.append({
            "plan": p,
            "headline": head,
            "target": head.current_target() if head else None,
            "remaining": head.sessions_to_goal() if head else None,
            "progress": p.progress_pct(),
        })
    return render(request, "tasks/plan_list.html", {"plans": plans})


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

    head = plan.headline
    return render(request, "tasks/plan_detail.html", {
        "plan": plan,
        "headline": _pack(head) if head else None,
        "supports": [_pack(i) for i in plan.support_items],
        "progress": plan.progress_pct(),
    })


def plan_form(request, pk=None):
    """Crear o editar un plan. Los objetivos se editan uno a uno."""
    plan = get_object_or_404(_plans_qs(), pk=pk) if pk else None

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if not name:
            messages.error(request, "Ponle un nombre al plan.")
        else:
            if plan is None:
                plan = Plan(user=get_current_user())
            plan.name = name[:80]
            plan.notes = request.POST.get("notes", "").strip()
            plan.started_on = request.POST.get("started_on") or plan.started_on or _dt.date.today()
            try:
                plan.weeks = max(1, int(request.POST.get("weeks", 12)))
            except (TypeError, ValueError):
                plan.weeks = 12
            plan.is_active = bool(request.POST.get("is_active"))
            plan.repeat = request.POST.get("repeat", "custom")
            plan.custom_days = ",".join(request.POST.getlist("custom_days")) or "0,2,4"
            plan.due_time = request.POST.get("due_time") or None
            try:
                plan.interval = max(1, int(request.POST.get("interval", 1)))
            except (TypeError, ValueError):
                plan.interval = 1
            plan.save()
            # El plan crea y mantiene su propia tarea: el usuario no tiene
            # que crear nada a mano ni saber qué es un circuito.
            plan.sync_task()
            messages.success(request, f"Plan «{plan.name}» guardado.")
            return redirect(reverse("tasks:plan_detail", args=[plan.pk]))

    return render(request, "tasks/plan_form.html", {
        "plan": plan,
        "weekdays": Task.WEEKDAYS,
        "selected_days": plan.custom_days_list() if plan else ["0", "2", "4"],
    })


@require_POST
def plan_delete(request, pk):
    plan = get_object_or_404(_plans_qs(), pk=pk)
    plan.deleted_at = timezone.now()
    plan.save(update_fields=["deleted_at", "updated_at"])
    plan.sync_task()          # retira la tarea pendiente
    messages.success(request, "Plan eliminado.")
    return redirect(reverse("tasks:plan_list"))


def plan_item_form(request, plan_pk, pk=None):
    """
    Un objetivo dentro del plan.

    El formulario enseña solo lo que aplica a cada tipo de progresión:
    no tiene sentido pedir "rango de repeticiones" en algo de
    cumplimiento, ni "peso" en una plancha.
    """
    plan = get_object_or_404(_plans_qs(), pk=plan_pk)
    item = get_object_or_404(PlanItem, pk=pk, plan=plan) if pk else None

    if request.method == "POST":
        if item is None:
            item = PlanItem(plan=plan)

        slug = request.POST.get("exercise") or ""
        item.exercise = Exercise.objects.filter(slug=slug).first() if slug else None
        item.label = request.POST.get("label", "").strip()[:80]

        valid = {k for k, _ in PlanItem.PROGRESSION_CHOICES}
        prog = request.POST.get("progression", PlanItem.PROG_REPS)
        item.progression = prog if prog in valid else PlanItem.PROG_REPS

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

        item.start_sets = _int("start_sets", 3) or 1
        item.start_reps = _int("start_reps", 8)
        item.start_seconds = _int("start_seconds", 40)
        item.start_weight_kg = _float("start_weight_kg", 0)

        item.goal_sets = _int("goal_sets", 0) or None
        item.goal_reps = _int("goal_reps", 0) or None
        item.goal_seconds = _int("goal_seconds", 0) or None
        gw = request.POST.get("goal_weight_kg")
        item.goal_weight_kg = _float("goal_weight_kg", 0) if gw else None

        item.sessions_per_step = _int("sessions_per_step", 2) or 1
        item.reps_increment = _int("reps_increment", 1) or 1
        item.weight_increment_kg = _float("weight_increment_kg", 2.5) or 2.5
        item.rep_range_low = _int("rep_range_low", 6) or 1
        item.deload_after_failures = _int("deload_after_failures", 3)
        item.is_headline = bool(request.POST.get("is_headline"))

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

    task.mark_done()
    messages.success(request, f"Sesión de «{plan.name}» guardada.")
    return JsonResponse({"ok": True, "redirect_url": reverse("tasks:task_list")})
