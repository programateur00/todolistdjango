import datetime
from django.utils import timezone
from tasks.models import Plan, Task, WorkoutSession, Exercise

AYER = datetime.date(2026, 9, 30)
KM = 10.44
APLICAR = False  # primero ejecútalo así (solo muestra datos); luego cámbialo a True

# 1) Localiza el plan de andar (el que tiene un objetivo de distancia)
planes = []
for p in Plan.objects.filter(plan_type="sport", is_active=True, deleted_at__isnull=True):
    if any(i.exercise and i.exercise.mode == Exercise.MODE_DISTANCE for i in p.items.select_related("exercise")):
        planes.append(p)
print("PLANES CON ANDAR/CORRER:", [(p.pk, p.name) for p in planes])
if len(planes) != 1:
    raise SystemExit("Hay 0 o varios planes: dime cuál es y fija PLAN_PK a mano.")
p = planes[0]
serie = p.task_series_id

# 2) Estado del plan y de sus tareas
for i in p.items.select_related("exercise"):
    print("OBJETIVO:", i.exercise.slug if i.exercise else None, "| progresion:", i.progression,
          "| escalon:", i.current_step(), "| objetivo actual:", i.current_target(),
          "| incremento km:", i.distance_increment_km, "| sesiones/escalon:", i.sessions_per_step)
for t in Task.objects.filter(series_id=serie).order_by("-due_date")[:4]:
    print("TAREA:", t.pk, t.due_date, "hecha:", t.is_done, "caducada:", t.expired, "| subcat:", repr(t.subcategory),
          "| km obj:", t.target_distance_km, "| ritmo max s/km:", t.max_pace_seconds_per_km, "| pasos obj:", t.target_steps)
for s in WorkoutSession.objects.filter(user=p.user, recorded_at__gte=timezone.now() - datetime.timedelta(days=4)).order_by("recorded_at"):
    if s.distance_km or s.steps:
        print("SESION:", s.pk, timezone.localtime(s.recorded_at), "km:", s.distance_km, "dur_s:", s.session_duration_seconds,
              "pasos:", s.steps, "fuente:", s.source, "| serie_ok:", s.series_id == serie, "| borrada:", s.deleted_at)

ayer_t = Task.objects.filter(series_id=serie, due_date=AYER).order_by("-pk").first()
if ayer_t is None:
    raise SystemExit("No hay tarea del 30/09 en esta serie.")

# 3) Marcar ayer como hecha con 10,44 km
if APLICAR:
    if ayer_t.is_done:
        ayer_t.reopen()  # deshace "caducada"; borra la de hoy, que se regenera al marcar
    ayer_t.workout_sessions.filter(distance_km__isnull=True, steps__isnull=True, session_duration_seconds=0).delete()
    ws = WorkoutSession.objects.create(
        task=ayer_t, plan=p, user=p.user, series_id=serie, exercise="running",
        distance_km=KM, session_duration_seconds=0, source=WorkoutSession.SOURCE_MANUAL,
        external_id="manual-2026-09-30",
        target_distance_km=ayer_t.target_distance_km, target_pace_seconds_per_km=ayer_t.max_pace_seconds_per_km,
    )
    WorkoutSession.objects.filter(pk=ws.pk).update(
        recorded_at=timezone.make_aware(datetime.datetime(2026, 9, 30, 20, 0)))
    ayer_t.mark_done()
    p.sync_task()
    print("HECHO. Tarea de hoy:", p.task.due_date, "km obj:", p.task.target_distance_km, "ritmo:", p.task.max_pace_seconds_per_km,
          "subcat:", repr(p.task.subcategory))
else:
    print("(modo solo lectura: no se ha cambiado nada)")
