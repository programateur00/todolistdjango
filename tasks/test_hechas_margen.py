"""
Lista de "Hechas" y margen de las tareas empezadas a tiempo.

Si abres una tarea ANTES de su hora límite tienes STARTED_GRACE_HOURS (3 h)
para terminarla (Task.mark_started / in_progress_grace). Si la terminas en ese
margen DESPUÉS de medianoche, completed_at cae en el día siguiente, pero la
app la cuenta para el día de su fecha límite (Occurrence se guarda por
due_date). La lista de Hechas tiene que decir lo mismo que las estadísticas:
la tarea es del día de su fecha límite, no del día siguiente.
"""
import datetime
from datetime import date, time, timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from .models import Occurrence, Task
from .utils import get_current_user

DOMINGO = date(2026, 10, 11)       # el lunes siguiente ya es otra semana
LUNES = DOMINGO + timedelta(days=1)


def _at(day, hh, mm=0):
    return timezone.make_aware(datetime.datetime.combine(day, time(hh, mm)))


def _now(moment):
    return mock.patch("django.utils.timezone.now", return_value=moment)


class HechasMargenTests(TestCase):
    def setUp(self):
        self.user = get_current_user()

    def _qs(self):
        return Task.objects.filter(user=self.user)

    def _tarea(self, *, due_day=DOMINGO, due_time=time(23, 30), started=None, done=None,
               avoid=False):
        """Crea la tarea; `started`/`done` son datetimes con zona (o None)."""
        t = Task.objects.create(
            title="Leer", due_date=due_day, due_time=due_time, user=self.user,
            category=Task.CATEGORY_AVOID if avoid else Task.CATEGORY_GENERAL,
        )
        if started:
            with _now(started):
                t.mark_started()
        if done:
            with _now(done):
                t.mark_done()
        return Task.objects.get(pk=t.pk)

    def _hechas_hoy(self, ahora):
        with _now(ahora):
            return list(Task.completed_today(self._qs()))

    def _hechas_rango(self, ahora, rango):
        with _now(ahora):
            return list(Task.completed_in_range(self._qs(), rango))

    # ── el caso del bug ────────────────────────────────────────────────

    def test_terminada_en_el_margen_pasada_medianoche_es_del_dia_limite(self):
        t = self._tarea(started=_at(DOMINGO, 23, 10), done=_at(LUNES, 0, 40))
        # La estadística ya la cuenta para el domingo (fecha límite)...
        self.assertEqual(Occurrence.objects.get(series_id=t.series_id).due_date, DOMINGO)
        # ...así que el lunes NO debe aparecer en Hechas de hoy,
        self.assertEqual(self._hechas_hoy(_at(LUNES, 10)), [])
        # ni en la semana del lunes (era del domingo, semana anterior),
        self.assertEqual(self._hechas_rango(_at(LUNES, 10), Task.RANGE_WEEK), [])
        # y SÍ en el domingo.
        self.assertEqual([x.pk for x in self._hechas_hoy(_at(DOMINGO, 23, 50))], [t.pk])
        self.assertEqual(
            [x.pk for x in self._hechas_rango(_at(DOMINGO, 12), Task.RANGE_WEEK)], [t.pk]
        )

    def test_en_el_limite_exacto_del_margen_sigue_siendo_del_dia_limite(self):
        # límite 23:30 + 3 h = 02:30
        t = self._tarea(started=_at(DOMINGO, 23, 0), done=_at(LUNES, 2, 30))
        self.assertEqual(self._hechas_hoy(_at(LUNES, 10)), [])
        self.assertEqual([x.pk for x in self._hechas_hoy(_at(DOMINGO, 23, 59))], [t.pk])

    def test_pasado_el_margen_cuenta_el_dia_en_que_la_terminaste(self):
        t = self._tarea(started=_at(DOMINGO, 23, 0), done=_at(LUNES, 2, 31))
        self.assertEqual([x.pk for x in self._hechas_hoy(_at(LUNES, 10))], [t.pk])
        self.assertEqual(self._hechas_hoy(_at(DOMINGO, 23, 59)), [])

    def test_antitarea_respondida_en_su_margen_pasada_medianoche(self):
        # antitarea: aviso 22:30, margen propio de 2 h para contestar
        t = self._tarea(due_time=time(22, 30), avoid=True, done=_at(LUNES, 0, 15))
        self.assertEqual(self._hechas_hoy(_at(LUNES, 10)), [])
        self.assertEqual([x.pk for x in self._hechas_hoy(_at(DOMINGO, 23, 50))], [t.pk])

    # ── lo que NO debe cambiar ─────────────────────────────────────────

    def test_terminada_el_mismo_dia_sigue_en_hoy(self):
        t = self._tarea(due_time=time(10, 0), started=_at(DOMINGO, 9, 0), done=_at(DOMINGO, 11, 0))
        self.assertEqual([x.pk for x in self._hechas_hoy(_at(DOMINGO, 12))], [t.pk])
        self.assertEqual(self._hechas_hoy(_at(LUNES, 10)), [])

    def test_terminada_antes_de_tiempo_es_del_dia_en_que_la_hiciste(self):
        t = self._tarea(due_day=LUNES, due_time=time(23, 30), done=_at(DOMINGO, 20, 0))
        self.assertEqual([x.pk for x in self._hechas_hoy(_at(DOMINGO, 21))], [t.pk])
        self.assertEqual(self._hechas_hoy(_at(LUNES, 10)), [])

    def test_sin_fecha_limite_cuenta_el_dia_en_que_la_marcas(self):
        t = self._tarea(due_day=None, due_time=None, done=_at(LUNES, 0, 40))
        self.assertEqual([x.pk for x in self._hechas_hoy(_at(LUNES, 10))], [t.pk])
        self.assertEqual(self._hechas_hoy(_at(DOMINGO, 23, 59)), [])

    def test_con_fecha_y_sin_hora_la_hora_limite_es_23_59_y_tiene_margen(self):
        # Task.save() pone 23:59 a toda tarea con fecha y sin hora: el margen
        # (hasta las 02:59) también vale para ella.
        t = self._tarea(due_time=None, started=_at(DOMINGO, 23, 0), done=_at(LUNES, 1, 0))
        self.assertEqual(t.due_time, time(23, 59))
        self.assertEqual(self._hechas_hoy(_at(LUNES, 10)), [])
        self.assertEqual([x.pk for x in self._hechas_hoy(_at(DOMINGO, 23, 59))], [t.pk])

    def test_tarea_con_retraso_de_dias_cuenta_el_dia_en_que_la_haces(self):
        t = self._tarea(due_time=time(23, 30), done=_at(DOMINGO + timedelta(days=3), 9, 0))
        self.assertEqual(self._hechas_hoy(_at(DOMINGO, 12)), [])
        self.assertEqual([x.pk for x in self._hechas_hoy(_at(DOMINGO + timedelta(days=3), 12))], [t.pk])

    def test_caducada_sigue_siendo_del_dia_limite(self):
        t = self._tarea(due_time=time(23, 30))
        with _now(_at(LUNES, 4, 0)):
            t.mark_expired()
        self.assertEqual(self._hechas_hoy(_at(LUNES, 10)), [])
        self.assertEqual([x.pk for x in self._hechas_hoy(_at(DOMINGO, 23, 59))], [t.pk])
