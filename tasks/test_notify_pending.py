"""
Regresión: la comprobación previa de los avisos del móvil (notify_pending).

El móvil pregunta al servidor "¿sigue pendiente esto?" unos minutos antes de
enseñar un aviso. Para las tareas "cada día" y las antitareas el aviso se
ancla a la SERIE, y al resolver la de hoy el servidor ya crea la de mañana
(sin resolver) en esa misma serie: sin la fecha de la fila, la respuesta era
siempre "sí, pendiente" y el aviso de una tarea ya hecha desde la web, otro
móvil o la extensión de Chrome sonaba igualmente.
"""
from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from .models import Task
from .utils import get_current_user


class NotifyPendingDateTests(TestCase):
    def _daily(self, **kw):
        return Task.objects.create(
            title="Diaria", due_date=date.today(), repeat=Task.REPEAT_DAILY,
            user=get_current_user(), **kw,
        )

    def _pending(self, **params):
        r = self.client.get(reverse("api:notify_pending"), params)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["pending"]

    def test_done_today_is_not_pending_even_though_tomorrows_row_exists(self):
        t = self._daily()
        t.mark_done()
        self.assertTrue(Task.objects.filter(series_id=t.series_id, is_done=False).exists(),
                        "al resolver la de hoy ya existe la de mañana, sin resolver")
        self.assertFalse(self._pending(series=t.series_id, date=date.today().isoformat()))

    def test_tomorrows_row_is_still_pending_for_tomorrows_date(self):
        t = self._daily()
        t.mark_done()
        self.assertTrue(self._pending(series=t.series_id, date=(date.today() + timedelta(days=1)).isoformat()))

    def test_unresolved_today_is_pending(self):
        t = self._daily()
        self.assertTrue(self._pending(series=t.series_id, date=date.today().isoformat()))

    def test_without_date_keeps_the_old_behaviour_for_old_apps(self):
        t = self._daily()
        t.mark_done()
        self.assertTrue(self._pending(series=t.series_id))

    def test_bad_date_is_a_400(self):
        t = self._daily()
        r = self.client.get(reverse("api:notify_pending"), {"series": t.series_id, "date": "mañana"})
        self.assertEqual(r.status_code, 400)

    def test_single_task_by_uuid(self):
        t = Task.objects.create(title="Suelta", due_date=date.today(), user=get_current_user())
        self.assertTrue(self._pending(task=t.uuid))
        t.mark_done()
        self.assertFalse(self._pending(task=t.uuid))
