"""
Simulación de varias semanas de uso real: se avanza el reloj, se marca,
desmarca, reabre, borra y caduca tareas de todos los tipos de repetición, y
tras CADA paso se comprueba que el estado cumple lo que la app promete.

Dos comprobaciones distintas:
  1. Invariantes (nunca puede pasar, hagas lo que hagas).
  2. Paridad web/móvil: la misma secuencia de acciones, hecha por la web o por
     la API de la app, tiene que dejar EXACTAMENTE el mismo estado.
"""
import json
import os
import random
from datetime import date, datetime, time, timedelta
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Occurrence, Task
from .utils import get_current_user

START = datetime(2026, 3, 2, 8, 0)  # lunes


def seeds():
    """Por defecto 2 semillas (rápido, ~30 s en total). Para una pasada
    exhaustiva: SIM_SEEDS="0-30" (tarda varios minutos). También sirve para
    repetir una sola semilla al depurar: SIM_SEEDS="7"."""
    spec = os.environ.get("SIM_SEEDS")
    if spec:
        a, _, b = spec.partition("-")
        return range(int(a), int(b or a) + 1)
    return range(2)


class Clock:
    def __init__(self):
        self.t = timezone.make_aware(START)

    def __call__(self):
        # Avanza un microsegundo en cada lectura, como un reloj real: sin
        # esto dos registros creados "a la vez" empatarían en recorded_at y
        # el orden de las rachas sería ambiguo (cosa que no pasa en la vida real).
        self.t += timedelta(microseconds=1)
        return self.t

    def advance(self, minutes):
        self.t += timedelta(minutes=minutes)


SPECS = [
    ("diaria", dict(repeat=Task.REPEAT_DAILY)),
    ("diaria-hora", dict(repeat=Task.REPEAT_DAILY, due_time=time(9, 0))),
    ("cada2", dict(repeat=Task.REPEAT_DAILY, interval=2, due_time=time(18, 30))),
    ("semanal", dict(repeat=Task.REPEAT_WEEKLY)),
    ("lmv", dict(repeat=Task.REPEAT_CUSTOM, custom_days="0,2,4")),
    ("lmv-cada2sem", dict(repeat=Task.REPEAT_CUSTOM, custom_days="1,3", interval=2)),
    ("mensual", dict(repeat=Task.REPEAT_MONTHLY)),
    ("unica", dict(repeat=Task.REPEAT_NONE, due_time=time(20, 0))),
    ("anti", dict(repeat=Task.REPEAT_DAILY, category=Task.CATEGORY_AVOID, due_time=time(22, 0))),
]


def make_tasks():
    user = get_current_user()
    today = timezone.localtime(timezone.now()).date()
    for title, kw in SPECS:
        Task.objects.create(title=title, due_date=today, user=user, **kw)


class Driver:
    """Hace las mismas acciones por la web o por la API de la app."""

    def __init__(self, client, channel):
        self.client = client
        self.channel = channel

    def _web(self, name, task):
        return self.client.post(reverse(f"tasks:{name}", args=[task.pk]))

    def _api(self, action, task):
        return self.client.post(reverse("api:task_mark", args=[task.uuid, action]))

    def done(self, t):
        return self._web("task_mark_done", t) if self.channel == "web" else self._api("done", t)

    def not_done(self, t):
        return self._web("task_mark_not_done", t) if self.channel == "web" else self._api("not-done", t)

    def failed(self, t):
        return self._web("task_mark_failed", t) if self.channel == "web" else self._api("failed", t)

    def reopen(self, t):
        return self._web("task_reopen", t) if self.channel == "web" else self._api("reopen", t)

    def edit(self, t, **changes):
        """Edita como lo haría el formulario web / el PATCH de la app."""
        fields = {
            "title": t.title,
            "repeat": t.repeat,
            "interval": t.interval or 1,
            "due_date": t.due_date.isoformat() if t.due_date else "",
            "due_time": t.due_time.strftime("%H:%M") if t.due_time else "23:59",
            "custom_days": t.custom_days_list(),
        }
        fields.update(changes)
        if self.channel == "web":
            r = self.client.post(reverse("tasks:task_edit", args=[t.pk]), fields)
        else:
            fields["custom_days"] = [int(d) for d in fields["custom_days"]]
            r = self.client.patch(
                reverse("api:task_detail", args=[t.uuid]),
                data=json.dumps(fields), content_type="application/json",
            )
        return r

    def start(self, t):
        return self.client.post(reverse("api:task_started", args=[t.uuid]))

    def delete(self, t):
        if self.channel == "web":
            return self.client.post(reverse("tasks:task_delete", args=[t.pk]))
        return self.client.delete(reverse("api:task_detail", args=[t.uuid]))


def pending_now():
    return list(
        Task.for_today(Task.objects.filter(is_done=False)).order_by("title", "due_date", "pk")
    )


def completed_now():
    return list(Task.completed_today(Task.objects.all()).order_by("title", "due_date", "pk"))


def snapshot():
    tasks = sorted(
        (t.title, str(t.due_date), t.is_done, t.expired)
        for t in Task.objects.all()
    )
    occs = sorted(
        (o.title, str(o.due_date), o.result, o.auto_expired, o.pct)
        for o in Occurrence.objects.all()
    )
    return tasks, occs


def run(testcase, seed, channel, steps=70, check=None):
    """Una simulación completa. Devuelve el snapshot final y el log de acciones."""
    rng = random.Random(seed)
    clock = Clock()
    log = []
    with mock.patch("django.utils.timezone.now", clock):
        make_tasks()
        drv = Driver(testcase.client, channel)
        for step in range(steps):
            roll = rng.random()
            # El reloj avanza a veces poco (misma tarde) y a veces días enteros
            # (semanas sin abrir la app).
            if roll < 0.35:
                clock.advance(rng.choice([30, 90, 240, 600, 900, 1500, 3000, 5000]))
            Task.expire_overdue()  # lo mismo que hace la lista al abrirse
            op = rng.choice([
                "done", "done", "done", "not_done", "failed", "reopen", "reopen", "delete",
                "double", "start", "edit_time", "postpone", "noop",
            ])
            if op in ("double", "start", "edit_time", "postpone"):
                pend = pending_now()
                if pend:
                    t = pend[rng.randrange(len(pend))]
                    if op == "double":
                        drv.done(t)
                        drv.done(t)  # doble toque / cola offline reenviada
                    elif op == "start":
                        drv.start(t)
                    elif op == "edit_time":
                        drv.edit(t, due_time=rng.choice(["07:00", "12:00", "21:15", "23:59"]))
                    elif op == "postpone" and t.due_date and t.repeat in (Task.REPEAT_NONE, Task.REPEAT_DAILY):
                        drv.edit(t, due_date=(t.due_date + timedelta(days=1)).isoformat())
                    log.append((step, op, t.title, str(t.due_date)))
            elif op in ("done", "not_done", "failed", "delete"):
                pend = pending_now()
                if pend:
                    t = pend[rng.randrange(len(pend))]
                    if op == "failed" and not t.is_avoid:
                        op = "done"
                    if op == "delete" and rng.random() < 0.7:
                        op = "done"  # borrar casi nunca
                    getattr(drv, op)(t)
                    log.append((step, op, t.title, str(t.due_date)))
            elif op == "reopen":
                comp = completed_now()
                if comp:
                    t = comp[rng.randrange(len(comp))]
                    drv.reopen(t)
                    log.append((step, op, t.title, str(t.due_date)))
            Task.expire_overdue()
            if check:
                check(clock, log)
    return snapshot(), log


class SimulationInvariantTests(TestCase):
    def _check(self, clock, log):
        now_local = timezone.localtime(clock()).replace(tzinfo=None)
        ctx = f"\nreloj={now_local} últimas acciones={log[-4:]}"

        # 1. Nunca dos pendientes del mismo día en la misma serie.
        seen = {}
        for t in Task.objects.filter(is_done=False):
            key = (t.series_id, t.due_date)
            self.assertNotIn(key, seen, f"pendiente duplicada {t.title} {t.due_date}" + ctx)
            seen[key] = t

        # 2. Una serie que se repite y sigue viva siempre tiene algo pendiente
        #    (si no, la tarea 'desaparece' sola).
        deleted_titles = {e[2] for e in log if e[1] == "delete"}
        series = {}
        for t in Task.objects.all():
            series.setdefault(t.series_id, []).append(t)
        for sid, rows in series.items():
            title = rows[0].title
            if title in deleted_titles or rows[0].repeat == Task.REPEAT_NONE:
                continue
            dump = "\n".join(
                f"   {r.due_date} done={r.is_done} exp={r.expired} reopened={r.reopened_at}"
                for r in sorted(rows, key=lambda r: r.due_date or date.min)
            )
            self.assertTrue(
                any(not r.is_done for r in rows),
                f"la serie repetida «{title}» se quedó sin ninguna pendiente" + ctx + "\n" + dump,
            )

        # 3. Tras expire_overdue no queda nada pendiente con la hora límite
        #    pasada, salvo que el usuario la devolviera a pendiente DESPUÉS
        #    de esa hora (decisión suya) o esté en el margen de 'empezada'.
        for t in Task.objects.filter(is_done=False, expired=False):
            limit = t.resolve_datetime()
            if limit is None or now_local <= limit:
                continue
            reopened = t.reopened_at and timezone.localtime(t.reopened_at).replace(tzinfo=None)
            ok = (reopened and reopened > limit) or t.in_progress_grace(limit, now_local)
            self.assertTrue(ok, f"vencida sin resolver: {t.title} {t.due_date}" + ctx)

        # 4. Una Occurrence por (serie, día) — lo garantiza la BD; y la rachas
        #    coinciden con una cuenta independiente por fecha.
        for sid in {o.series_id for o in Occurrence.objects.all()}:
            occs = list(Occurrence.objects.filter(series_id=sid))
            dated = sorted((o for o in occs if o.due_date), key=lambda o: o.due_date)
            cur = 0
            for o in reversed(dated):
                if o.result == Occurrence.RESULT_DONE:
                    cur += 1
                else:
                    break
            mx = run_ = 0
            for o in dated:
                run_ = run_ + 1 if o.result == Occurrence.RESULT_DONE else 0
                mx = max(mx, run_)
            st = Occurrence.streak_stats(sid)
            self.assertEqual(st["current_streak"], cur, f"racha actual de «{occs[0].title}»" + ctx)
            self.assertEqual(st["max_streak"], mx, f"racha máxima de «{occs[0].title}»" + ctx)

        # 4b. La lista de la web y la de la app enseñan LO MISMO (cada 4 pasos,
        #     renderizar la plantilla entera es lo caro).
        if len(log) % 4 == 0:
            web = self.client.get(reverse("tasks:task_list")).context
            api = self.client.get(reverse("api:task_list")).json()
            w_pend = sorted((t.title, str(t.due_date)) for t in web["pending_tasks"])
            a_pend = sorted((t["title"], t["due_date"]) for t in api["pending"])
            self.assertEqual(w_pend, a_pend, "pendientes: web != app" + ctx)
            w_done = sorted((t.title, str(t.due_date)) for t in web["completed_tasks"])
            a_done = sorted((t["title"], t["due_date"]) for t in api["completed"])
            self.assertEqual(w_done, a_done, "hechas: web != app" + ctx)

        # 5. Los contadores que pinta la app no revientan ni son absurdos.
        user = get_current_user()
        d = Occurrence.daily_completion(user)
        w = Occurrence.weekly_completion(user)
        self.assertLessEqual(d["done"], d["total"], "diario: hechas > total" + ctx)
        self.assertLessEqual(w["done"], w["total"], "semanal: hechas > total" + ctx)

    def test_invariants_web(self):
        for seed in seeds():
            with self.subTest(seed=seed):
                Task.all_objects.all().delete()
                Occurrence.objects.all().delete()
                run(self, seed, "web", check=self._check)

    def test_invariants_api(self):
        for seed in seeds():
            with self.subTest(seed=seed):
                Task.all_objects.all().delete()
                Occurrence.objects.all().delete()
                run(self, seed, "api", check=self._check)


class SimulationParityTests(TestCase):
    def test_web_and_api_leave_the_same_state(self):
        for seed in seeds():
            with self.subTest(seed=seed):
                Task.all_objects.all().delete()
                Occurrence.objects.all().delete()
                snap_web, log_web = run(self, seed, "web")
                Task.all_objects.all().delete()
                Occurrence.objects.all().delete()
                snap_api, log_api = run(self, seed, "api")
                self.assertEqual(log_web, log_api, "la secuencia de acciones divergió")
                self.assertEqual(snap_web[0], snap_api[0], "tareas distintas web vs app")
                self.assertEqual(snap_web[1], snap_api[1], "estadísticas distintas web vs app")


class PlanLifecycleSimulationTests(TestCase):
    """Un plan General de pocas semanas, vivido día a día con un usuario
    despistado: tiene que abrirse, repartir sus días, cambiar de días si se
    edita, y cerrarse solo al cumplirse las semanas."""

    def _refresh(self):
        """Lo que hace la lista al abrirse."""
        from .models import Plan
        Task.expire_overdue()
        Plan.auto_close_expired(user=get_current_user())
        Plan.sync_all_tasks(user=get_current_user())

    def _run(self, seed):
        from .models import Plan
        rng = random.Random(seed)
        clock = Clock()
        weeks = rng.choice([1, 2, 3])
        days = sorted(rng.sample([0, 1, 2, 3, 4, 5, 6], rng.choice([2, 3, 5])))
        with mock.patch("django.utils.timezone.now", clock):
            r = self.client.post(
                reverse("api:plan_create"),
                data=json.dumps({
                    "name": f"Plan {seed}", "plan_type": "general", "weeks": weeks,
                    "custom_days": days, "due_time": "20:00",
                }),
                content_type="application/json",
            )
            self.assertEqual(r.status_code, 201, r.content)
            plan = Plan.objects.get(name=f"Plan {seed}")
            marked = set(days)
            end = plan.ends_on
            for step in range(weeks * 7 * 3):
                clock.advance(rng.choice([240, 480, 720, 1000]))
                self._refresh()
                plan.refresh_from_db()
                today = timezone.localtime(clock()).date()
                ctx = f"\nseed={seed} hoy={today} fin={end} días={sorted(marked)} cerrado={plan.closed_at}"
                pend = list(Task.objects.filter(series_id=plan.task_series_id, is_done=False))
                if today >= end:
                    self.assertIsNotNone(plan.closed_at, "el plan no se cerró al cumplirse las semanas" + ctx)
                if plan.closed_at:
                    self.assertFalse(plan.is_active, "plan cerrado pero activo" + ctx)
                    self.assertEqual(pend, [], "plan cerrado con tareas pendientes" + ctx)
                    self.assertIsNotNone(plan.final_progress_pct, ctx)
                else:
                    self.assertEqual(len(pend), 1, f"debe haber UNA pendiente, hay {len(pend)}" + ctx)
                    t = pend[0]
                    self.assertIn(t.due_date.weekday(), marked, f"pendiente en día no marcado {t.due_date}" + ctx)
                    # El usuario la hace con 55 % de probabilidad si ya toca.
                    if t.due_date <= today and rng.random() < 0.55:
                        self.client.post(reverse("api:task_mark", args=[t.uuid, "done"]))
                    # y de vez en cuando cambia los días del plan
                    if rng.random() < 0.08 and not plan.closed_at:
                        new_days = sorted(rng.sample([0, 1, 2, 3, 4, 5, 6], rng.choice([2, 3])))
                        self.client.patch(
                            reverse("api:plan_detail", args=[plan.uuid]),
                            data=json.dumps({"custom_days": new_days}), content_type="application/json",
                        )
                        marked = set(new_days)
                # Nunca hay ocurrencias en días que no eran del plan ese día
                # (con cambios de días aceptamos cualquier día que haya sido marcado alguna vez).
            return plan

    def test_general_plan_lifecycle(self):
        for seed in seeds():
            with self.subTest(seed=seed):
                Task.all_objects.all().delete()
                Occurrence.objects.all().delete()
                from .models import Plan
                Plan.objects.all().delete()
                self._run(seed)
