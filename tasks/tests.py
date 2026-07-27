from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from .models import Occurrence, Task
from .utils import get_current_user


class CategoryModelTests(TestCase):
    def test_default_category_is_general(self):
        t = Task.objects.create(title="Sin categoría")
        self.assertEqual(t.category, Task.CATEGORY_GENERAL)

    def test_create_with_explicit_category(self):
        t = Task.objects.create(title="Ir al gym", category=Task.CATEGORY_SPORT)
        self.assertEqual(t.category, Task.CATEGORY_SPORT)

    def test_category_capabilities_study_has_timer(self):
        t = Task(category=Task.CATEGORY_STUDY)
        self.assertTrue(t.has_capability("timer"))
        self.assertTrue(t.has_capability("pomodoro"))
        self.assertFalse(t.has_capability("pose_tracking"))

    def test_category_capabilities_sport_has_pose(self):
        t = Task(category=Task.CATEGORY_SPORT)
        self.assertTrue(t.has_capability("pose_tracking"))
        self.assertTrue(t.has_capability("timer"))

    def test_category_capabilities_general_empty(self):
        t = Task(category=Task.CATEGORY_GENERAL)
        self.assertEqual(t.category_capabilities, [])

    def test_recurrence_inherits_category(self):
        """Al marcar como hecha, la siguiente ocurrencia hereda la categoría."""
        t = Task.objects.create(
            title="Estudiar calculus",
            category=Task.CATEGORY_STUDY,
            due_date=date.today(),
            repeat=Task.REPEAT_DAILY,
            interval=1,
        )
        t.mark_done()
        new_task = Task.objects.exclude(pk=t.pk).get(title="Estudiar calculus")
        self.assertEqual(new_task.category, Task.CATEGORY_STUDY)
        self.assertEqual(
            Occurrence.objects.filter(task__isnull=False).count(), 1
        )


class CategoryViewTests(TestCase):
    def _post(self, **overrides):
        data = {
            "title": "Hacer sentadillas",
            "category": Task.CATEGORY_SPORT,
            "due_date": "2026-12-31",
            "due_time": "08:00",
            "repeat": Task.REPEAT_NONE,
            "interval": 1,
        }
        data.update(overrides)
        return self.client.post(reverse("tasks:task_create"), data)

    def test_create_with_category_persists(self):
        resp = self._post()
        self.assertEqual(resp.status_code, 302)
        t = Task.objects.get(title="Hacer sentadillas")
        self.assertEqual(t.category, Task.CATEGORY_SPORT)
        self.assertEqual(t.due_time, time(8, 0))

    def test_create_without_category_defaults_to_general(self):
        resp = self.client.post(
            reverse("tasks:task_create"),
            {"title": "Una cosa"},
        )
        self.assertEqual(resp.status_code, 302)
        t = Task.objects.get(title="Una cosa")
        self.assertEqual(t.category, Task.CATEGORY_GENERAL)

    def test_create_rejects_invalid_category(self):
        resp = self._post(category="not-a-real-category")
        self.assertEqual(resp.status_code, 302)
        t = Task.objects.get(title="Hacer sentadillas")
        # Se queda con el default si el valor es inválido.
        self.assertEqual(t.category, Task.CATEGORY_GENERAL)

    def test_list_filter_by_category(self):
        Task.objects.create(title="Hacer sentadillas", category=Task.CATEGORY_SPORT, user=get_current_user())
        Task.objects.create(title="Estudiar cálculo", category=Task.CATEGORY_STUDY, user=get_current_user())

        resp = self.client.get(reverse("tasks:task_list") + "?cat=sport")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Hacer sentadillas")
        self.assertNotContains(resp, "Estudiar cálculo")

    def test_list_renders_category_pill(self):
        Task.objects.create(title="Ir al gym", category=Task.CATEGORY_SPORT, user=get_current_user())
        resp = self.client.get(reverse("tasks:task_list"))
        self.assertContains(resp, "Deporte")  # get_category_display
        self.assertContains(resp, "meta-pill--sport")

    def test_edit_updates_category(self):
        t = Task.objects.create(title="X", category=Task.CATEGORY_GENERAL, user=get_current_user())
        resp = self.client.post(
            reverse("tasks:task_edit", args=[t.pk]),
            {
                "title": "X",
                "category": Task.CATEGORY_WORK,
                "repeat": Task.REPEAT_NONE,
                "interval": 1,
            },
        )
        self.assertEqual(resp.status_code, 302)
        t.refresh_from_db()
        self.assertEqual(t.category, Task.CATEGORY_WORK)
