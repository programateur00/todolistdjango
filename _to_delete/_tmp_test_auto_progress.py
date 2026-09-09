import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "todoapp.settings")
os.environ["DJANGO_TEST_DB"] = ":memory:"
django.setup()
from django.test.utils import setup_test_environment
from django.test.runner import DiscoverRunner

runner = DiscoverRunner()
old_config = runner.setup_databases()

from django.contrib.auth import get_user_model
from tasks.models import Task, TimerSession, WorkoutSession
from django.utils import timezone
import uuid

User = get_user_model()
u = User.objects.create(username="tester")

# --- caso 1: Lectura con extension (pc_usage) ---
sid = uuid.uuid4()
t = Task.objects.create(
    title="Leer PDF", category=Task.CATEGORY_WORK, subcategory=Task.SUBCATEGORY_READING,
    watch_keyword="pdf", target_minutes=30, user=u, series_id=sid,
)
assert t.workout_kind == "auto", t.workout_kind
print("sin sesiones:", t.auto_progress)
assert t.auto_progress["pct"] == 0

TimerSession.objects.create(task=t, user=u, series_id=sid, subcategory=t.subcategory,
                             source=TimerSession.SOURCE_PC_USAGE, minutes=12, target_minutes=30)
print("con 12 min:", t.auto_progress)
assert t.auto_progress == {"pct": 40, "label": "12/30 min"}, t.auto_progress

TimerSession.objects.create(task=t, user=u, series_id=sid, subcategory=t.subcategory,
                             source=TimerSession.SOURCE_PC_USAGE, minutes=25, target_minutes=30)
print("con 12+25 min (pasado el objetivo):", t.auto_progress)
assert t.auto_progress["pct"] == 100, t.auto_progress

# --- caso 2: Udemy ---
sid2 = uuid.uuid4()
t2 = Task.objects.create(
    title="Curso Django", category=Task.CATEGORY_STUDY, subcategory=Task.SUBCATEGORY_UDEMY,
    target_minutes=60, user=u, series_id=sid2,
)
assert t2.workout_kind == "auto"
TimerSession.objects.create(task=t2, user=u, series_id=sid2, subcategory=t2.subcategory,
                             source=TimerSession.SOURCE_PC_USAGE, minutes=15, target_minutes=60)
print("udemy 15/60:", t2.auto_progress)
assert t2.auto_progress == {"pct": 25, "label": "15/60 min"}

# --- caso 3: Running por distancia + ritmo ---
sid3 = uuid.uuid4()
t3 = Task.objects.create(
    title="Correr 5k", category=Task.CATEGORY_SPORT, subcategory=Task.SUBCATEGORY_RUNNING,
    target_distance_km=5.0, max_pace_seconds_per_km=360, user=u, series_id=sid3,
)
assert t3.workout_kind == "distance"
print("running sin sesiones:", t3.auto_progress)
assert t3.auto_progress["pct"] == 0

WorkoutSession.objects.create(task=t3, user=u, series_id=sid3, exercise="running",
                               distance_km=2.0, session_duration_seconds=2*300)  # 5:00/km, cumple
print("running 2km a buen ritmo:", t3.auto_progress)
assert t3.auto_progress == {"pct": 40, "label": "2.0/5 km"}, t3.auto_progress

WorkoutSession.objects.create(task=t3, user=u, series_id=sid3, exercise="running",
                               distance_km=3.0, session_duration_seconds=3*450)  # 7:30/km, NO cumple ritmo
print("+3km caminando (no cumple ritmo, no debe sumar):", t3.auto_progress)
assert t3.auto_progress == {"pct": 40, "label": "2.0/5 km"}, t3.auto_progress

WorkoutSession.objects.create(task=t3, user=u, series_id=sid3, exercise="running",
                               distance_km=3.0, session_duration_seconds=3*300)  # 5:00/km, cumple
print("+3km a buen ritmo (deberia llegar a 100, recortado):", t3.auto_progress)
assert t3.auto_progress["pct"] == 100, t3.auto_progress

# --- caso 4: Running por pasos ---
sid4 = uuid.uuid4()
t4 = Task.objects.create(
    title="Andar 8000 pasos", category=Task.CATEGORY_SPORT, subcategory=Task.SUBCATEGORY_RUNNING,
    target_steps=8000, user=u, series_id=sid4,
)
WorkoutSession.objects.create(task=t4, user=u, series_id=sid4, exercise="running", steps=3000)
WorkoutSession.objects.create(task=t4, user=u, series_id=sid4, exercise="running", steps=1000)
print("pasos 3000+1000/8000:", t4.auto_progress)
assert t4.auto_progress == {"pct": 50, "label": "4000/8000 pasos"}, t4.auto_progress

# --- caso 5: tarea normal (no auto/distance) -> None ---
t5 = Task.objects.create(title="Tarea normal", category=Task.CATEGORY_GENERAL, user=u)
assert t5.auto_progress is None

# --- caso 6: auto sin target_minutes -> None (nada que dibujar) ---
t6 = Task.objects.create(
    title="Enfoque libre", category=Task.CATEGORY_WORK, subcategory=Task.SUBCATEGORY_READING,
    watch_keyword="", user=u, series_id=uuid.uuid4(),
)
assert t6.workout_kind == "focus"
assert t6.auto_progress is None

# --- caso 7: tarea ya hecha -> None (no tiene sentido seguir mostrando barra) ---
t.refresh_from_db()
t.is_done = True
t.save()
assert t.auto_progress is None

print("ALL OK")
runner.teardown_databases(old_config)
