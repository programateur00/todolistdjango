"""
Regresión: un plan de Estudio con curso de Udemy al 100% se tiene que cerrar.

Antes, el 100% llegaba a la barra del objetivo (PlanItem.course_progress_pct)
por la vía "pasiva" de la extensión (pestaña de Udemy abierta, sin sesión de
tiempo en marcha), pero el cierre solo se disparaba por la vía de la tarea
(`course-complete`), que exige una sesión contando. Resultado: barra al 100%,
plan abierto y tareas diarias que seguían saliendo.
"""
import io
import json
from datetime import time, timedelta

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Plan, PlanItem, Task, TimerSession
from .utils import get_current_user


class UdemyPlanClosureTests(TestCase):
    def setUp(self):
        self.user = get_current_user()
        self.plan = Plan.objects.create(
            name="Terminar Excel", user=self.user, plan_type=Plan.PLAN_TYPE_STUDY,
            study_subtype=Plan.STUDY_SUBTYPE_GENERAL, weeks=12, reward="unas zapatillas",
            repeat="daily", due_time=time(23, 59),
        )
        self.item = PlanItem.objects.create(
            plan=self.plan, is_headline=True, progression=PlanItem.PROG_COMPLETION,
            watch_keyword="Excel", target_minutes=30,
        )
        self.task = self.plan.sync_task()

    # ---- helpers
    def _item_progress(self, pct, done=None, total=None):
        body = {"pct": pct}
        if done is not None:
            body.update(done=done, total=total)
        return self.client.post(
            reverse("api:plan_item_course_progress_save", args=[self.item.pk]),
            data=json.dumps(body), content_type="application/json",
        )

    def _task_progress(self, task, pct):
        return self.client.post(
            reverse("api:course_progress_save", args=[task.uuid]),
            data=json.dumps({"pct": pct}), content_type="application/json",
        )

    def _focus(self, task, minutes):
        return self.client.post(
            reverse("api:focus_save", args=[task.uuid]),
            data=json.dumps({"minutes": minutes, "source": "pc_usage", "app_package": "udemy.com"}),
            content_type="application/json",
        )

    def assertPlanClosed(self):
        self.plan.refresh_from_db()
        self.assertIsNotNone(self.plan.closed_at)
        self.assertFalse(self.plan.is_active)
        # Cerrado = ya no sale ninguna tarea pendiente más del plan.
        self.assertFalse(Task.objects.filter(series_id=self.plan.task_series_id, is_done=False).exists())

    def assertPlanOpen(self):
        self.plan.refresh_from_db()
        self.assertIsNone(self.plan.closed_at)
        self.assertTrue(self.plan.is_active)

    # ---- llegando justo a 100%
    def test_item_progress_exactly_100_closes_plan(self):
        """Vía pasiva (sin sesión): la que dejaba el plan atascado."""
        r = self._item_progress(100, done=40, total=40)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["plan_closed"])
        self.assertPlanClosed()

    def test_task_progress_exactly_100_closes_plan(self):
        r = self._task_progress(self.task, 100)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertPlanClosed()

    def test_99_does_not_close(self):
        self._item_progress(99, done=39, total=40)
        self._task_progress(self.task, 99)
        self.assertPlanOpen()

    # ---- pasándose del objetivo
    def test_progress_over_100_is_clamped_and_closes(self):
        r = self._item_progress(105)
        self.assertEqual(r.json()["pct"], 100)
        self.assertPlanClosed()

    def test_watching_more_than_daily_target_then_100_closes(self):
        """Pasarse de los 30 min del día y acabar el curso."""
        self._focus(self.task, 50)  # el tope diario recorta a 30
        self.assertEqual(sum(TimerSession.objects.filter(task=self.task).values_list("minutes", flat=True)), 30)
        self._item_progress(100)
        self.assertPlanClosed()

    # ---- por vídeo (sesión contando) y por temporizador (tarea ya hecha)
    def test_video_session_then_course_complete_action_closes(self):
        """Vía con sesión en marcha (course-complete de la tarea de hoy)."""
        self._focus(self.task, 20)
        r = self.client.post(reverse("api:task_mark", args=[self.task.uuid, "course-complete"]))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertPlanClosed()

    def test_timer_goal_done_today_then_course_finished_extra_closes(self):
        """Hoy ya cumpliste el objetivo del día (nace la tarea de mañana) y
        luego terminas el curso viendo vídeos extra: tiene que cerrarse."""
        self._focus(self.task, 30)
        self.task.mark_done()
        tomorrow = Task.objects.filter(series_id=self.plan.task_series_id, is_done=False)
        self.assertEqual(tomorrow.count(), 1)  # la de mañana ya existe
        self._item_progress(100, done=40, total=40)
        self.assertPlanClosed()

    def test_closing_twice_is_idempotent(self):
        self._item_progress(100)
        self.plan.refresh_from_db()
        first = self.plan.closed_at
        r = self._item_progress(100)
        self.assertFalse(r.json()["plan_closed"])
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.closed_at, first)

    # ---- red de seguridad: planes que YA estaban atascados
    def test_stuck_plan_at_100_closes_on_next_sweep(self):
        PlanItem.objects.filter(pk=self.item.pk).update(course_progress_pct=100)
        self.assertPlanOpen()
        Plan.auto_close_expired(user=self.user)
        self.assertPlanClosed()

    def test_management_command_closes_stuck_plans(self):
        PlanItem.objects.filter(pk=self.item.pk).update(course_progress_pct=100)
        out = io.StringIO()
        call_command("cerrar_planes_udemy_atascados", "--dry-run", stdout=out)
        self.assertPlanOpen()
        call_command("cerrar_planes_udemy_atascados", stdout=out)
        self.assertPlanClosed()

    # ---- otros tipos de plan no se tocan
    def test_sport_plan_is_not_closed_by_udemy_logic(self):
        sport = Plan.objects.create(
            name="Calistenia", user=self.user, plan_type=Plan.PLAN_TYPE_SPORT, weeks=4,
            started_on=timezone.localtime(timezone.now()).date(), repeat="daily",
        )
        Plan.auto_close_expired(user=self.user)
        sport.refresh_from_db()
        self.assertIsNone(sport.closed_at)

    def test_web_plan_is_not_a_udemy_course(self):
        ilerna = Plan.objects.create(
            name="Clases", user=self.user, plan_type=Plan.PLAN_TYPE_STUDY,
            study_subtype=Plan.STUDY_SUBTYPE_GENERAL, weeks=12, repeat="daily",
        )
        it = PlanItem.objects.create(
            plan=ilerna, is_headline=True, progression=PlanItem.PROG_COMPLETION,
            watch_keyword="Redes", watch_site=PlanItem.SITE_WEB, course_progress_pct=100,
        )
        Plan.auto_close_expired(user=self.user)
        ilerna.refresh_from_db()
        self.assertIsNone(ilerna.closed_at)
