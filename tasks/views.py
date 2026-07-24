import json

from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Occurrence, Task, WorkoutSession


def _read_category(request, default=Task.CATEGORY_GENERAL):
    """Lee la categoría del POST/GET, validando contra choices."""
    raw = request.POST.get("category", default) or default
    valid = {key for key, _ in Task.CATEGORY_CHOICES}
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

    base_qs = Task.objects.all()
    if active_category:
        base_qs = base_qs.filter(category=active_category)

    pending_tasks = base_qs.filter(is_done=False)
    completed_tasks = base_qs.filter(is_done=True)

    # Conteos por categoría para los chips de filtro
    counts = dict(
        Task.objects.values_list("category").annotate(n=Count("id")).values_list("category", "n")
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
                due_date=request.POST.get("due_date") or None,
                due_time=request.POST.get("due_time") or None,
                repeat=request.POST.get("repeat", Task.REPEAT_NONE),
                interval=request.POST.get("interval") or 1,
                custom_days=",".join(request.POST.getlist("custom_days")),
                is_important=bool(request.POST.get("is_important")),
            )
            messages.success(request, "Tarea creada.")
        return redirect(reverse("tasks:task_list"))

    initial_title = request.GET.get("title", "")
    return render(request, "tasks/task_form.html", {
        "repeat_choices": Task.REPEAT_CHOICES,
        "weekdays": Task.WEEKDAYS,
        "category_choices": Task.CATEGORY_CHOICES,
        "initial_title": initial_title,
    })


def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if request.method == "POST":
        task.title = request.POST.get("title", task.title).strip()
        task.notes = request.POST.get("notes", "").strip()
        task.category = _read_category(request, default=task.category)
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
    })


@require_POST
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    task.delete()
    messages.success(request, "Tarea eliminada.")
    return redirect(reverse("tasks:task_list"))


@require_POST
def task_mark_done(request, pk):
    get_object_or_404(Task, pk=pk).mark_done()
    return redirect(reverse("tasks:task_list"))


@require_POST
def task_mark_not_done(request, pk):
    get_object_or_404(Task, pk=pk).mark_not_done()
    return redirect(reverse("tasks:task_list"))


def task_workout(request, pk):
    """Página con la cámara para grabar (en el navegador) una sesión
    de ejercicio y contar dominadas con MediaPipe."""
    task = get_object_or_404(Task, pk=pk)
    return render(request, "tasks/task_workout.html", {"task": task})


@require_POST
def task_workout_save(request, pk):
    """
    Recibe (por fetch/AJAX, en JSON) las estadísticas ya calculadas en
    el navegador al terminar la sesión, las guarda, y marca la tarea
    como hecha. No se recibe ni se guarda ningún vídeo — solo números.
    """
    task = get_object_or_404(Task, pk=pk)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    total_reps = int(data.get("total_reps", 0))
    rep_durations = data.get("rep_durations", [])
    if not isinstance(rep_durations, list):
        rep_durations = []
    rep_durations = [float(d) for d in rep_durations if isinstance(d, (int, float))]

    avg_rep_seconds = round(sum(rep_durations) / len(rep_durations), 2) if rep_durations else None

    WorkoutSession.objects.create(
        task=task,
        series_id=task.series_id,
        exercise=WorkoutSession.EXERCISE_PULLUP,
        total_reps=total_reps,
        session_duration_seconds=int(data.get("session_duration_seconds", 0)),
        avg_rep_seconds=avg_rep_seconds,
        rest_alerts_triggered=int(data.get("rest_alerts_triggered", 0)),
        rep_durations=rep_durations,
    )

    task.mark_done()

    messages.success(
        request,
        f"Sesión guardada: {total_reps} dominadas"
        + (f", ritmo medio {avg_rep_seconds}s/rep." if avg_rep_seconds else "."),
    )
    return JsonResponse({"ok": True, "redirect_url": reverse("tasks:task_list")})


def stats_list(request):
    summary = {}
    for occ in Occurrence.objects.all().order_by("recorded_at"):
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
    occurrences = Occurrence.objects.filter(series_id=series_id).order_by("-recorded_at")
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
