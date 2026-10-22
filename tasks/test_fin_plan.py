"""
Regresión: aviso de fin de plan.

Un plan que no llega al umbral (70%) se cerraba SIN decir nada: la tarea
simplemente no volvía a salir y el usuario se enteraba al día siguiente. Ahora:
  - la última sesión lo dice en la tarjeta (`plan_last_session`),
  - un cierre que el usuario no ha visto sale en `plans_closed_unseen`
    hasta que abre la pantalla de cierre (`closure-seen`).
"""
import datetime as dt
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Plan, Task
from .utils import get_current_user


def _plan(started_on=None, weeks=1):
    return Plan.objects.create(
        user=get_current_user(), name="Calistenia", plan_type=Plan.PLAN_TYPE_GENERAL,
        started_on=started_on or timezone.localtime(timezone.now()).date(), weeks=weeks,
        repeat="custom", custom_days="0,1,2,3,4,5,6", due_time=None,  # sin hora: que no caduque según la hora a la que se ejecute el test
    )


class ClosedUnseenTests(TestCase):
    def _closed(self, pct):
        plan = _plan()
        with mock.patch.object(Plan, "progress_pct", lambda self: pct):
            self.client.post(reverse("api:plan_close", args=[plan.uuid]))
        Plan.objects.filter(pk=plan.pk).update(closure_seen_at=None)  # como un cierre automático
        return plan

    def _unseen(self):
        return self.client.get(reverse("api:task_list")).json()["plans_closed_unseen"]

    def test_silent_close_below_threshold_is_announced_until_seen(self):
        plan = self._closed(55)
        got = self._unseen()
        self.assertEqual([p["uuid"] for p in got], [str(plan.uuid)])
        self.assertFalse(got[0]["is_completed"])
        self.assertEqual(got[0]["final_progress_pct"], 55)
        self.assertEqual(got[0]["threshold"], 70)
        self.client.post(reverse("api:plan_closure_seen", args=[plan.uuid]))
        self.assertEqual(self._unseen(), [])

    def test_closing_it_yourself_is_not_announced(self):
        plan = _plan()
        self.client.post(reverse("api:plan_close", args=[plan.uuid]))
        self.assertEqual(self._unseen(), [])

    def test_web_list_flashes_the_result_once(self):
        self._closed(55)
        r = self.client.get(reverse("tasks:task_list"), follow=True)
        self.assertContains(r, "sin llegar al 70%")
        r = self.client.get(reverse("tasks:task_list"), follow=True)
        self.assertNotContains(r, "sin llegar al 70%")

    def test_auto_close_without_user_closing_leaves_it_unseen(self):
        plan = _plan(started_on=timezone.localtime(timezone.now()).date() - dt.timedelta(weeks=2), weeks=1)
        Plan.auto_close_expired(user=plan.user)
        plan.refresh_from_db()
        self.assertIsNotNone(plan.closed_at)
        self.assertIsNone(plan.closure_seen_at)


class LastSessionNoticeTests(TestCase):
    def _task(self, plan):
        plan.sync_task()
        return Task.objects.get(series_id=plan.task_series_id, is_done=False)

    def test_last_task_before_the_end_date_carries_the_notice(self):
        today = timezone.localtime(timezone.now()).date()
        plan = _plan(started_on=today - dt.timedelta(days=6), weeks=1)  # acaba mañana
        t = self._task(plan)
        with mock.patch.object(Plan, "progress_pct", lambda self: 62):
            data = self.client.get(reverse("api:task_list")).json()
        notice = [x for x in data["pending"] if x["uuid"] == str(t.uuid)][0]["plan_last_session"]
        self.assertEqual(notice["progress_pct"], 62)
        self.assertEqual(notice["threshold"], 70)
        self.assertFalse(notice["on_track"])

    def test_middle_of_the_plan_has_no_notice(self):
        plan = _plan(weeks=4)
        t = self._task(plan)
        data = self.client.get(reverse("api:task_list")).json()
        self.assertIsNone([x for x in data["pending"] if x["uuid"] == str(t.uuid)][0]["plan_last_session"])
