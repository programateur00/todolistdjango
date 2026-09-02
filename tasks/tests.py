import json
from datetime import date, time, timedelta

from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from .models import (
    Exercise, Occurrence, Plan, PlanItem, Routine, RoutineItem, Task, TimerSession, WorkoutSession,
)
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


class AntiTaskTests(TestCase):
    def test_normal_task_silence_is_failure(self):
        """Una tarea normal, si pasa la hora sin tocar nada, cuenta como fallo."""
        t = Task.objects.create(
            title="Estudiar", due_time=time(0, 1), category=Task.CATEGORY_STUDY, user=get_current_user(),
        )
        t.mark_expired()
        occ = Occurrence.objects.filter(series_id=t.series_id).latest("recorded_at")
        self.assertEqual(occ.result, Occurrence.RESULT_NOT_DONE)
        self.assertTrue(t.is_done)
        self.assertTrue(t.expired)

    def test_avoid_task_silence_is_success(self):
        """Una antitarea (category='avoid'), si pasa la hora sin tocar nada,
        cuenta como éxito (silencio = lo evitaste) — justo lo contrario de
        una tarea normal."""
        t = Task.objects.create(
            title="No fumar", due_time=time(0, 1), category=Task.CATEGORY_AVOID, user=get_current_user(),
        )
        self.assertTrue(t.is_avoid)
        t.mark_expired()
        occ = Occurrence.objects.filter(series_id=t.series_id).latest("recorded_at")
        self.assertEqual(occ.result, Occurrence.RESULT_DONE)
        self.assertTrue(t.is_done)
        self.assertTrue(t.expired)

    def test_expire_overdue_picks_up_avoid_task(self):
        """El barrido automático (el que se llama al abrir la lista) también
        debe resolver en éxito una antitarea vencida, sin tocar nada a mano.

        Lleva fecha de ayer a propósito: sin fecha, la hora se ancla al día
        de creación, y una tarea creada ahora mismo aún no habría vencido.
        """
        yesterday = date.today() - timedelta(days=1)
        t = Task.objects.create(
            title="No gastar de más", due_date=yesterday, due_time=time(12, 0),
            category=Task.CATEGORY_AVOID, user=get_current_user(),
        )
        expired = Task.expire_overdue()
        self.assertIn(t, expired)
        t.refresh_from_db()
        self.assertTrue(t.is_done)
        occ = Occurrence.objects.filter(series_id=t.series_id).latest("recorded_at")
        self.assertEqual(occ.result, Occurrence.RESULT_DONE)

    def test_mark_failed_spawns_next_occurrence(self):
        """"He caído hoy" en una antitarea diaria debe seguir generando
        mañana — si no, la serie se quedaría colgada la primera vez que caes."""
        t = Task.objects.create(
            title="No fumar", due_date=date.today(), repeat=Task.REPEAT_DAILY,
            interval=1, category=Task.CATEGORY_AVOID, subcategory=Task.SUBCATEGORY_UPPER_BODY,
            user=get_current_user(),
        )
        t.mark_failed()
        occ = Occurrence.objects.filter(series_id=t.series_id).latest("recorded_at")
        self.assertEqual(occ.result, Occurrence.RESULT_NOT_DONE)
        self.assertTrue(t.is_done)  # se resuelve el dia, a diferencia de mark_not_done()

        next_task = Task.objects.exclude(pk=t.pk).get(series_id=t.series_id)
        self.assertEqual(next_task.due_date, date.today() + timedelta(days=1))
        self.assertEqual(next_task.category, Task.CATEGORY_AVOID)  # se propaga a la siguiente
        self.assertTrue(next_task.is_avoid)
        self.assertEqual(next_task.subcategory, Task.SUBCATEGORY_UPPER_BODY)  # bonus: ya no se pierde

    def test_mark_not_done_still_used_for_undo_stays_unchanged(self):
        """mark_not_done() (el botón "Desmarcar") no debe tocarse: sigue
        dejando is_done=False y sin generar la siguiente ocurrencia."""
        t = Task.objects.create(title="X", category=Task.CATEGORY_AVOID, user=get_current_user())
        t.mark_done()
        t.mark_not_done()
        self.assertFalse(t.is_done)

    def test_create_form_saves_avoid_category(self):
        resp = self.client.post(reverse("tasks:task_create"), {
            "title": "No fumar", "category": "avoid", "repeat": Task.REPEAT_NONE, "interval": 1,
        })
        self.assertEqual(resp.status_code, 302)
        t = Task.objects.get(title="No fumar")
        self.assertEqual(t.category, Task.CATEGORY_AVOID)
        self.assertTrue(t.is_avoid)

    def test_create_form_defaults_to_general_not_avoid(self):
        resp = self.client.post(reverse("tasks:task_create"), {
            "title": "Tarea normal", "repeat": Task.REPEAT_NONE, "interval": 1,
        })
        self.assertEqual(resp.status_code, 302)
        t = Task.objects.get(title="Tarea normal")
        self.assertFalse(t.is_avoid)


class OccurrenceIdempotencyTests(TestCase):
    """
    El resultado de un día es un hecho corregible, no un log que se apila.
    Antes, marcar/desmarcar/marcar creaba 3 filas para el mismo día y
    streak_stats() las contaba todas — rachas infladas. Además es lo que
    permite que web y móvil resuelvan el mismo día sin duplicarlo.
    """

    def test_mark_done_twice_keeps_one_occurrence(self):
        t = Task.objects.create(
            title="Estudiar", due_date=date.today(), user=get_current_user(),
        )
        t.mark_done()
        t.mark_not_done()
        t.mark_done()
        occs = Occurrence.objects.filter(series_id=t.series_id, due_date=date.today())
        self.assertEqual(occs.count(), 1)
        self.assertEqual(occs.first().result, Occurrence.RESULT_DONE)

    def test_streak_not_inflated_by_toggling(self):
        """Marcar y desmarcar el mismo día no debe subir la racha."""
        t = Task.objects.create(
            title="Leer", due_date=date.today(), user=get_current_user(),
        )
        t.mark_done()
        t.mark_not_done()
        t.mark_done()
        stats = Occurrence.streak_stats(t.series_id)
        self.assertEqual(stats["current_streak"], 1)

    def test_two_clients_resolving_same_day_produce_one_row(self):
        """Simula web y móvil resolviendo el mismo día por separado."""
        t = Task.objects.create(
            title="No fumar", due_date=date.today(), category=Task.CATEGORY_AVOID,
            due_time=time(0, 1), user=get_current_user(),
        )
        t.mark_expired()          # lo resuelve el móvil
        t2 = Task.objects.get(pk=t.pk)
        t2.mark_expired()         # y luego la web, sin saberlo
        self.assertEqual(
            Occurrence.objects.filter(series_id=t.series_id, due_date=date.today()).count(), 1
        )

    def test_tasks_without_due_date_can_have_several_occurrences(self):
        """Sin fecha no hay 'día' al que anclar: ahí sí se apilan."""
        t = Task.objects.create(title="Cuando pueda", user=get_current_user())
        t.mark_done()
        t.mark_not_done()
        self.assertEqual(Occurrence.objects.filter(series_id=t.series_id).count(), 2)

    def test_sync_fields_are_unique_and_populated(self):
        a = Task.objects.create(title="A", user=get_current_user())
        b = Task.objects.create(title="B", user=get_current_user())
        self.assertIsNotNone(a.uuid)
        self.assertNotEqual(a.uuid, b.uuid)
        self.assertIsNotNone(a.updated_at)
        self.assertIsNone(a.deleted_at)


class AvoidGraceTests(TestCase):
    """
    Una antitarea NO debe resolverse sola en el mismo instante de la hora
    límite: a esa hora salta el aviso, y hace falta un margen para poder
    contestarlo. Antes se auto-completaba al segundo y contestar no
    servía de nada.
    """

    def _avoid_task(self, hours_ago):
        """Antitarea cuya hora límite fue hace `hours_ago` horas."""
        now = timezone.localtime(timezone.now())
        deadline = now - timedelta(hours=hours_ago)
        return Task.objects.create(
            title="No fumar", category=Task.CATEGORY_AVOID,
            due_date=deadline.date(), due_time=deadline.time().replace(microsecond=0),
            user=get_current_user(),
        )

    def test_not_resolved_right_at_deadline(self):
        """Justo pasada la hora límite todavía no se resuelve: es el rato
        que tienes para contestar la notificación."""
        t = self._avoid_task(hours_ago=0.5)
        self.assertFalse(t.is_overdue())
        self.assertNotIn(t, Task.expire_overdue())

    def test_resolved_after_grace(self):
        """Pasado el margen sin contestar, sí se da por evitada."""
        t = self._avoid_task(hours_ago=Task.AVOID_GRACE_HOURS + 1)
        self.assertTrue(t.is_overdue())
        self.assertIn(t, Task.expire_overdue())
        occ = Occurrence.objects.filter(series_id=t.series_id).latest("recorded_at")
        self.assertEqual(occ.result, Occurrence.RESULT_DONE)

    def test_normal_task_has_no_grace(self):
        """Una tarea normal sigue expirando en la hora límite, sin margen."""
        now = timezone.localtime(timezone.now())
        deadline = now - timedelta(minutes=30)
        t = Task.objects.create(
            title="Estudiar", category=Task.CATEGORY_STUDY,
            due_date=deadline.date(), due_time=deadline.time().replace(microsecond=0),
            user=get_current_user(),
        )
        self.assertTrue(t.is_overdue())

    def test_answering_during_grace_wins(self):
        """Si contestas dentro del margen, tu respuesta manda y la tarea
        ya no se resuelve sola."""
        t = self._avoid_task(hours_ago=0.5)
        t.mark_failed()   # "he caído hoy"
        t.refresh_from_db()
        self.assertTrue(t.is_done)
        occ = Occurrence.objects.filter(series_id=t.series_id, due_date=t.due_date).first()
        self.assertEqual(occ.result, Occurrence.RESULT_NOT_DONE)


class ReopenTests(TestCase):
    """
    Deshacer una tarea marcada debe dejarlo TODO como estaba: la racha no
    puede quedarse contando ese día, ni puede sobrevivir la instancia
    futura que se generó al marcarla.
    """

    def test_reopened_task_is_not_immediately_reexpired(self):
        """
        Regresión del fallo más molesto: expire_overdue() se ejecuta al
        cargar la lista, así que al devolver a pendientes una tarea cuya
        hora ya pasó, el barrido la volvía a cerrar en el acto y parecía
        que el botón de deshacer no hacía nada.
        """
        now = timezone.localtime(timezone.now())
        past = now - timedelta(hours=3)
        t = Task.objects.create(
            title="Estudiar", due_date=past.date(),
            due_time=past.time().replace(microsecond=0), user=get_current_user(),
        )
        t.mark_done()
        t.reopen()
        t.refresh_from_db()
        self.assertFalse(t.is_done)

        Task.expire_overdue()          # lo que pasa al recargar la lista
        t.refresh_from_db()
        self.assertFalse(t.is_done)    # sigue pendiente, como pediste

    def test_reopened_task_without_due_date_is_not_reexpired(self):
        """
        Regresión: una tarea con solo hora y sin fecha no tiene un
        "momento límite" absoluto, así que resolve_datetime() devuelve
        None y la protección de reapertura se saltaba por completo. El
        botón de deshacer parecía roto justo en ese caso.
        """
        t = Task.objects.create(
            title="No fumar", category=Task.CATEGORY_AVOID,
            due_date=None, due_time=time(12, 0), user=get_current_user(),
        )
        # Sin fecha, la hora se ancla al día de creación. Para que esté
        # vencida de verdad hay que simular que se creó ayer — si no, su
        # límite sería hoy a las 12:00 y podría estar aún por llegar.
        Task.objects.filter(pk=t.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        t.refresh_from_db()
        Task.expire_overdue()
        t.refresh_from_db()
        self.assertTrue(t.is_done)      # se resolvió sola, correcto

        t.reopen()
        Task.expire_overdue()           # lo que pasa al recargar la lista
        t.refresh_from_db()
        self.assertFalse(t.is_done)     # y sigue arriba

    def test_dateless_deadline_survives_midnight(self):
        """
        Regresión encontrada a las 00:45: una tarea con hora pero sin
        fecha se comparaba hora contra hora, y pasada la medianoche la
        cuenta salía al revés ("21:45 < 00:45" es falso), así que no
        vencía nunca en esa franja. Ahora la hora se ancla al día de
        creación, que da un instante absoluto.
        """
        t = Task.objects.create(
            title="Estudiar", due_date=None, due_time=time(21, 0),
            user=get_current_user(),
        )
        Task.objects.filter(pk=t.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        t.refresh_from_db()
        # Creada ayer con límite a las 21:00 de ayer: da igual la hora a
        # la que se mire hoy, tiene que estar vencida.
        self.assertTrue(t.is_overdue())
        self.assertIn(t, Task.expire_overdue())

    def test_dateless_deadline_not_yet_reached(self):
        """Y creada hoy, su límite es hoy: todavía no vence."""
        t = Task.objects.create(
            title="Estudiar", due_date=None, due_time=time(23, 59),
            user=get_current_user(),
        )
        self.assertFalse(t.is_overdue())

    def test_marking_done_twice_does_not_duplicate_future_task(self):
        """Marcar, deshacer y volver a marcar dejaba DOS tareas idénticas
        en el futuro."""
        t = Task.objects.create(
            title="Diaria", due_date=date.today(), repeat=Task.REPEAT_DAILY,
            interval=1, user=get_current_user(),
        )
        t.mark_done()
        t.mark_not_done()
        t.mark_done()
        tomorrow = date.today() + timedelta(days=1)
        self.assertEqual(
            Task.objects.filter(series_id=t.series_id, due_date=tomorrow).count(), 1
        )

    def test_reopen_removes_occurrence_and_restores_stats(self):
        t = Task.objects.create(
            title="Leer", due_date=date.today(), user=get_current_user(),
        )
        t.mark_done()
        self.assertEqual(Occurrence.objects.filter(series_id=t.series_id).count(), 1)

        t.reopen()
        t.refresh_from_db()
        self.assertFalse(t.is_done)
        # La ocurrencia se borra, no se marca como fallo: si se quedara,
        # la racha seguiría contando ese día.
        self.assertEqual(Occurrence.objects.filter(series_id=t.series_id).count(), 0)
        self.assertEqual(Occurrence.streak_stats(t.series_id)["current_streak"], 0)

    def test_reopen_deletes_spawned_future_task(self):
        """Marcar una tarea diaria genera la de mañana. Deshacer debe
        borrarla, o quedaría una tarea duplicada en el futuro."""
        t = Task.objects.create(
            title="No fumar", due_date=date.today(), repeat=Task.REPEAT_DAILY,
            interval=1, user=get_current_user(),
        )
        t.mark_done()
        self.assertEqual(Task.objects.filter(series_id=t.series_id).count(), 2)

        t.reopen()
        self.assertEqual(Task.objects.filter(series_id=t.series_id).count(), 1)

    def test_reopen_keeps_workout_sessions(self):
        """Las repeticiones se hicieron de verdad: no se borran por
        deshacer el marcado."""
        t = Task.objects.create(
            title="Dominadas", due_date=date.today(),
            category=Task.CATEGORY_SPORT, user=get_current_user(),
        )
        WorkoutSession.objects.create(task=t, user=get_current_user(), total_reps=8)
        t.mark_done()
        t.reopen()
        self.assertEqual(t.workout_sessions.count(), 1)

    def test_reopen_differs_from_mark_not_done(self):
        """mark_not_done registra un fallo; reopen no registra nada."""
        a = Task.objects.create(title="A", due_date=date.today(), user=get_current_user())
        a.mark_done()
        a.mark_not_done()
        self.assertEqual(Occurrence.objects.filter(series_id=a.series_id).count(), 1)

        b = Task.objects.create(title="B", due_date=date.today(), user=get_current_user())
        b.mark_done()
        b.reopen()
        self.assertEqual(Occurrence.objects.filter(series_id=b.series_id).count(), 0)

    def test_reopen_via_api(self):
        r = self.client.post(
            "/api/tasks/create/",
            data=json.dumps({"title": "X", "due_date": date.today().isoformat()}),
            content_type="application/json",
        )
        uuid_ = r.json()["task"]["uuid"]
        self.client.post(f"/api/tasks/{uuid_}/mark/done/")
        self.assertTrue(Task.objects.get(uuid=uuid_).is_done)

        r2 = self.client.post(f"/api/tasks/{uuid_}/mark/reopen/")
        self.assertEqual(r2.status_code, 200)
        self.assertFalse(Task.objects.get(uuid=uuid_).is_done)


class CatchUpTests(TestCase):
    """
    Si pasas varios días sin abrir la app, TODOS deben quedar
    registrados. Antes solo se registraba uno por recarga: el barrido
    cerraba una tarea, generaba la siguiente, y ahí paraba. Los huecos
    aparecían justo cuando peor lo habías hecho.
    """

    def test_missed_days_are_all_recorded_in_one_sweep(self):
        four_days_ago = date.today() - timedelta(days=4)
        now_time = timezone.localtime(timezone.now()).time().replace(microsecond=0)
        t = Task.objects.create(
            title="Estudiar", due_date=four_days_ago, due_time=now_time,
            repeat=Task.REPEAT_DAILY, interval=1, user=get_current_user(),
        )
        Task.expire_overdue()
        occs = Occurrence.objects.filter(series_id=t.series_id)
        self.assertGreaterEqual(occs.count(), 4)
        self.assertTrue(all(o.result == Occurrence.RESULT_NOT_DONE for o in occs))

    def test_avoid_task_catch_up_counts_as_success(self):
        """Lo mismo para antitareas, pero cada día cuenta como evitado."""
        four_days_ago = date.today() - timedelta(days=4)
        now_time = timezone.localtime(timezone.now()).time().replace(microsecond=0)
        t = Task.objects.create(
            title="No fumar", category=Task.CATEGORY_AVOID,
            due_date=four_days_ago, due_time=now_time,
            repeat=Task.REPEAT_DAILY, interval=1, user=get_current_user(),
        )
        Task.expire_overdue()
        occs = Occurrence.objects.filter(series_id=t.series_id)
        self.assertGreaterEqual(occs.count(), 3)
        self.assertTrue(all(o.result == Occurrence.RESULT_DONE for o in occs))


class AvoidLabelTests(TestCase):
    def test_custom_labels_are_exposed_with_defaults(self):
        t = Task.objects.create(
            title="No fumar", category=Task.CATEGORY_AVOID, user=get_current_user(),
        )
        r = self.client.get(f"/api/tasks/{t.uuid}/")
        data = r.json()["task"]
        self.assertEqual(data["avoid_success_label"], "Sigo con la racha")
        self.assertEqual(data["avoid_question"], "¿Has caído hoy?")

    def test_custom_labels_round_trip(self):
        r = self.client.post("/api/tasks/create/", data=json.dumps({
            "title": "No fumar", "category": "avoid",
            "avoid_question": "¿Has fumado hoy?",
            "avoid_success_label": "Ni uno",
            "avoid_fail_label": "He fumado",
        }), content_type="application/json")
        data = r.json()["task"]
        self.assertEqual(data["avoid_question"], "¿Has fumado hoy?")
        self.assertEqual(data["avoid_success_label"], "Ni uno")

    def test_labels_propagate_to_next_occurrence(self):
        """Si no se propagan, mañana la notificación vuelve a los textos
        genéricos."""
        t = Task.objects.create(
            title="No fumar", category=Task.CATEGORY_AVOID, due_date=date.today(),
            repeat=Task.REPEAT_DAILY, interval=1, avoid_success_label="Ni uno",
            user=get_current_user(),
        )
        t.mark_done()
        nxt = Task.objects.exclude(pk=t.pk).get(series_id=t.series_id)
        self.assertEqual(nxt.avoid_success_label, "Ni uno")


class WorkoutKindTests(TestCase):
    """
    El botón de la lista debe prometer lo que la sesión va a hacer de
    verdad. Antes cualquier tarea de Deporte enseñaba una cámara, aunque
    fuera un circuito a cronómetro o una salida a correr que se rellena
    a mano — incongruente.
    """

    def _kind(self, subcategory, category=Task.CATEGORY_SPORT):
        return Task(category=category, subcategory=subcategory).workout_kind

    def test_upper_body_uses_camera(self):
        self.assertEqual(self._kind(Task.SUBCATEGORY_UPPER_BODY), "camera")

    def test_lower_body_uses_timer(self):
        self.assertEqual(self._kind(Task.SUBCATEGORY_LOWER_BODY), "timer")

    def test_running_is_manual(self):
        self.assertEqual(self._kind(Task.SUBCATEGORY_RUNNING), "distance")

    def test_non_sport_has_no_workout_button(self):
        self.assertIsNone(self._kind("", category=Task.CATEGORY_STUDY))
        self.assertIsNone(self._kind("", category=Task.CATEGORY_AVOID))

    def test_api_exposes_workout_kind(self):
        t = Task.objects.create(
            title="Abdos", category=Task.CATEGORY_SPORT,
            subcategory=Task.SUBCATEGORY_LOWER_BODY, user=get_current_user(),
        )
        r = self.client.get(f"/api/tasks/{t.uuid}/")
        self.assertEqual(r.json()["task"]["workout_kind"], "timer")


class PlanProgressionTests(TestCase):
    """
    Tres formas de progresar, porque no todo progresa igual. Y ninguna
    puede diverger: una progresión lineal pediría 3x47 dominadas a los
    seis meses.
    """

    def setUp(self):
        self.user = get_current_user()
        self.plan = Plan.objects.create(name="En forma", user=self.user)
        self.pull = Exercise.objects.create(
            slug="pull-p", name="Dominadas", mode=Exercise.MODE_POSE,
        )
        self.task = Task.objects.create(
            title="Entrenar", category=Task.CATEGORY_SPORT, user=self.user,
        )

    def _session(self, reps, target_reps):
        return WorkoutSession.objects.create(
            task=self.task, plan=self.plan, user=self.user, exercise=self.pull.slug,
            total_reps=reps, total_sets=3, target_sets=3, target_reps=target_reps,
        )

    # ---------------------------------------------------- cumplimiento

    def test_completion_never_climbs(self):
        """Estudiar 2 horas no se convierte en 2 y media hasta reventar."""
        item = PlanItem.objects.create(
            plan=self.plan, series_id=self.task.series_id, label="Estudiar",
            progression=PlanItem.PROG_COMPLETION, start_reps=1,
        )
        reps = [r["reps"] for r in item.schedule(5)]
        self.assertEqual(reps, [1, 1, 1, 1, 1])

    # ----------------------------------------------------- repeticiones

    def test_reps_stops_at_goal(self):
        item = PlanItem.objects.create(
            plan=self.plan, exercise=self.pull, progression=PlanItem.PROG_REPS,
            start_reps=8, goal_reps=11, reps_increment=1, sessions_per_step=1,
        )
        rows = item.schedule(10)
        self.assertEqual([r["reps"] for r in rows], [8, 9, 10, 11])
        self.assertTrue(rows[-1]["done"])   # y el plan TERMINA

    # ------------------------------------------------------------ doble

    def test_double_resets_reps_and_adds_weight(self):
        """La clave para no diverger: al llegar arriba del rango, sube el
        peso y las repeticiones vuelven al suelo."""
        item = PlanItem.objects.create(
            plan=self.plan, exercise=self.pull, progression=PlanItem.PROG_DOUBLE,
            start_sets=4, start_weight_kg=0, goal_sets=4, goal_reps=8,
            goal_weight_kg=10, rep_range_low=6, weight_increment_kg=5,
        )
        rows = item.schedule(12)
        self.assertEqual(rows[0]["reps"], 6)
        self.assertEqual(rows[2]["reps"], 8)        # techo del rango
        self.assertEqual(rows[3]["reps"], 6)        # vuelve abajo...
        self.assertEqual(rows[3]["weight_kg"], 5)   # ...con más peso

    def test_double_reaches_the_goal_and_stops(self):
        item = PlanItem.objects.create(
            plan=self.plan, exercise=self.pull, progression=PlanItem.PROG_DOUBLE,
            start_sets=4, start_weight_kg=0, goal_sets=4, goal_reps=12,
            goal_weight_kg=20, rep_range_low=6, weight_increment_kg=5,
        )
        rows = item.schedule(60)
        self.assertTrue(rows[-1]["done"])
        self.assertEqual(rows[-1]["weight_kg"], 20)
        self.assertEqual(rows[-1]["reps"], 12)
        self.assertIsNotNone(item.sessions_to_goal())

    # ------------------------------------------------- series proporcionales

    def test_sets_climb_proportionally_with_reps(self):
        """Regresión: antes las series saltaban a la meta desde el
        primer escalón (2x5 -> destino 4x12 enseñaba "4x5" nada más
        empezar). Ahora suben poco a poco, en la misma proporción que
        las repeticiones."""
        item = PlanItem.objects.create(
            plan=self.plan, exercise=self.pull, progression=PlanItem.PROG_REPS,
            start_sets=2, start_reps=5, goal_sets=4, goal_reps=12,
            reps_increment=1, sessions_per_step=1,
        )
        rows = item.schedule(10)
        self.assertEqual(rows[0]["sets"], 2)     # punto de partida, no la meta
        self.assertEqual(rows[0]["reps"], 5)
        self.assertEqual(rows[-1]["sets"], 4)    # llega a la meta justo cuando
        self.assertEqual(rows[-1]["reps"], 12)   # las reps llegan a la suya
        self.assertTrue(rows[-1]["done"])
        # y sube de forma monótona, nunca de golpe ni hacia atrás
        sets_seen = [r["sets"] for r in rows]
        self.assertEqual(sets_seen, sorted(sets_seen))

    def test_sets_stay_fixed_without_a_goal(self):
        """Sin meta de series no hay con qué interpolar: se quedan en
        las de partida durante todo el plan."""
        item = PlanItem.objects.create(
            plan=self.plan, exercise=self.pull, progression=PlanItem.PROG_REPS,
            start_sets=3, start_reps=8, goal_reps=20, sessions_per_step=1,
        )
        rows = item.schedule(15)
        self.assertTrue(all(r["sets"] == 3 for r in rows))

    def test_double_progression_climbs_sets_with_weight(self):
        """En progresión doble el peso es lo que mide el progreso de
        verdad (las reps solo oscilan dentro del rango), así que las
        series interpolan contra el peso, no contra las reps."""
        item = PlanItem.objects.create(
            plan=self.plan, exercise=self.pull, progression=PlanItem.PROG_DOUBLE,
            start_sets=2, start_weight_kg=0, goal_sets=4, goal_reps=12,
            goal_weight_kg=20, rep_range_low=6, weight_increment_kg=5,
        )
        rows = item.schedule(60)
        self.assertEqual(rows[0]["sets"], 2)
        self.assertTrue(rows[-1]["done"])
        self.assertEqual(rows[-1]["sets"], 4)

    # --------------------------------------------------- el entrenador

    def test_does_not_climb_if_you_fall_short(self):
        item = PlanItem.objects.create(
            plan=self.plan, exercise=self.pull, progression=PlanItem.PROG_REPS,
            start_reps=8, goal_reps=15, sessions_per_step=2, deload_after_failures=3,
        )
        self._session(15, 8)      # 15 de 24 = no cumplida
        self._session(15, 8)
        self.assertEqual(item.current_target()["reps"], 8)

    def test_deloads_after_repeated_failures(self):
        """Un entrenador no te deja atascado para siempre en un número
        que hoy no puedes: baja un escalón y reconstruyes."""
        item = PlanItem.objects.create(
            plan=self.plan, exercise=self.pull, progression=PlanItem.PROG_REPS,
            start_reps=8, goal_reps=15, sessions_per_step=2, deload_after_failures=3,
        )
        self._session(24, 8)
        self._session(24, 8)
        self.assertEqual(item.current_target()["reps"], 9)   # subió
        for _ in range(3):
            self._session(15, 9)                              # tres fallos
        self.assertEqual(item.current_target()["reps"], 8)    # bajó

    def test_timed_progression_uses_seconds(self):
        plank = Exercise.objects.create(
            slug="plank-p", name="Plancha", mode=Exercise.MODE_TIMED,
        )
        item = PlanItem.objects.create(
            plan=self.plan, exercise=plank, progression=PlanItem.PROG_REPS,
            start_seconds=30, goal_seconds=45, reps_increment=5, sessions_per_step=1,
        )
        self.assertEqual([r["seconds"] for r in item.schedule(6)], [30, 35, 40, 45])


class PlanHeadlineTests(TestCase):
    """
    El objetivo de verdad ("estar en forma") es difuso y no se mide. Lo
    que se mide es una prueba concreta de que vas hacia él — 4x12 con 20
    kg. Esa es la medida principal; el resto de ejercicios son el camino.
    """

    def setUp(self):
        self.user = get_current_user()
        self.plan = Plan.objects.create(name="Ponerme en forma", user=self.user)
        self.wp = Exercise.objects.create(
            slug="wp-h", name="Dominadas con peso", mode=Exercise.MODE_POSE,
        )
        self.plank = Exercise.objects.create(
            slug="pl-h", name="Plancha", mode=Exercise.MODE_TIMED,
        )

    def _headline(self):
        return PlanItem.objects.create(
            plan=self.plan, exercise=self.wp, is_headline=True,
            progression=PlanItem.PROG_DOUBLE, start_sets=4, start_weight_kg=0,
            goal_sets=4, goal_reps=12, goal_weight_kg=20,
            rep_range_low=6, weight_increment_kg=5, order=0,
        )

    def _support(self):
        return PlanItem.objects.create(
            plan=self.plan, exercise=self.plank, progression=PlanItem.PROG_REPS,
            start_seconds=30, goal_seconds=90, reps_increment=5, order=1,
        )

    def test_headline_is_the_marked_one(self):
        self._support()
        head = self._headline()
        self.assertEqual(self.plan.headline, head)

    def test_support_items_exclude_the_headline(self):
        head = self._headline()
        sup = self._support()
        self.assertEqual(list(self.plan.support_items), [sup])
        self.assertNotIn(head, self.plan.support_items)

    def test_falls_back_to_first_when_none_marked(self):
        """Sin marcar ninguna, la pantalla debe seguir teniendo algo que
        destacar en vez de quedarse vacía."""
        sup = self._support()
        self.assertEqual(self.plan.headline, sup)

    def test_progress_measured_on_headline_not_calendar(self):
        """El plan avanza con lo que haces, no con lo que pasa el
        calendario: recién creado va al 0% aunque el reloj corra."""
        self._headline()
        self.assertEqual(self.plan.progress_pct(), 0)

    def test_a_plan_holds_several_exercises(self):
        self._headline()
        self._support()
        self.assertEqual(self.plan.items.count(), 2)


class PlanViewTests(TestCase):
    """Las pantallas de plan en la web."""

    def setUp(self):
        self.user = get_current_user()
        self.wp = Exercise.objects.create(
            slug="wp-v", name="Dominadas con peso", mode=Exercise.MODE_POSE,
        )

    def _create_plan(self):
        self.client.post(reverse("tasks:plan_create"), {
            "name": "Ponerme en forma", "weeks": 12, "is_active": "on", "due_time": "18:00",
        })
        return Plan.objects.get(name="Ponerme en forma")

    def test_create_plan_from_web(self):
        plan = self._create_plan()
        self.assertTrue(plan.is_active)
        self.assertEqual(plan.user, self.user)

    def test_add_headline_item(self):
        plan = self._create_plan()
        r = self.client.post(reverse("tasks:plan_item_create", args=[plan.pk]), {
            "exercise": self.wp.slug, "progression": "double", "is_headline": "on",
            "start_sets": 4, "start_reps": 6, "start_weight_kg": 0,
            "goal_sets": 4, "goal_reps": 12, "goal_weight_kg": 20,
            "rep_range_low": 6, "weight_increment_kg": 5, "sessions_per_step": 2,
        })
        self.assertEqual(r.status_code, 302)
        item = plan.items.get()
        self.assertTrue(item.is_headline)
        self.assertEqual(item.goal_weight_kg, 20)

    def test_only_one_headline_allowed(self):
        plan = self._create_plan()
        other = Exercise.objects.create(slug="ot-v", name="Otro", mode=Exercise.MODE_POSE)
        for slug in (self.wp.slug, other.slug):
            self.client.post(reverse("tasks:plan_item_create", args=[plan.pk]), {
                "exercise": slug, "progression": "reps", "is_headline": "on",
                "start_sets": 3, "start_reps": 8, "goal_reps": 12,
            })
        self.assertEqual(plan.items.filter(is_headline=True).count(), 1)

    def test_detail_shows_path_to_the_goal(self):
        """La tabla tiene que llegar al destino: con un número fijo de
        filas se cortaba antes y no se veía el final."""
        plan = self._create_plan()
        self.client.post(reverse("tasks:plan_item_create", args=[plan.pk]), {
            "exercise": self.wp.slug, "progression": "double", "is_headline": "on",
            "start_sets": 4, "start_reps": 6, "start_weight_kg": 0,
            "goal_sets": 4, "goal_reps": 12, "goal_weight_kg": 20,
            "rep_range_low": 6, "weight_increment_kg": 5, "sessions_per_step": 2,
        })
        html = self.client.get(reverse("tasks:plan_detail", args=[plan.pk])).content.decode()
        self.assertIn("Medida del plan", html)
        self.assertIn("con 20 kg", html)     # el destino aparece
        self.assertIn("destino", html)

    def test_plan_list_renders(self):
        self._create_plan()
        html = self.client.get(reverse("tasks:plan_list")).content.decode()
        self.assertIn("Ponerme en forma", html)

    def test_delete_plan_is_soft(self):
        plan = self._create_plan()
        self.client.post(reverse("tasks:plan_delete", args=[plan.pk]))
        plan.refresh_from_db()
        self.assertIsNotNone(plan.deleted_at)
        html = self.client.get(reverse("tasks:plan_list")).content.decode()
        self.assertNotIn("Ponerme en forma", html)


class NotificationSeriesTests(TestCase):
    """
    Una notificación local recurrente (Android la repite sola cada día, sin
    reabrir la app) se programa una vez y mantiene siempre el mismo
    contenido. Si apuntara al uuid de la tarea de un día concreto, dejaría
    de servir en cuanto esa tarea se resolviera y naciera la del día
    siguiente. Apuntando a la serie, la misma notificación sigue
    resolviendo el día que toque, sin importar cuántos días hayan pasado
    sin abrir la app.
    """

    def test_marks_current_pending_task_of_the_series(self):
        t = Task.objects.create(
            title="No fumar", category=Task.CATEGORY_AVOID, due_date=date.today(),
            due_time=time(22, 0), repeat=Task.REPEAT_DAILY, interval=1,
            user=get_current_user(),
        )
        r = self.client.post(f"/api/series/{t.series_id}/mark/done/")
        self.assertTrue(r.json()["ok"])
        # confirma la tarea que ACABA de resolver...
        self.assertEqual(r.json()["task"]["uuid"], str(t.uuid))
        # ...y ya existe una nueva pendiente para mañana en la misma serie.
        tomorrow = Task.objects.get(series_id=t.series_id, is_done=False)
        self.assertNotEqual(tomorrow.uuid, t.uuid)

    def test_keeps_working_across_many_unopened_days(self):
        """Simula varios toques seguidos sin reabrir la app entre medias:
        cada uno debe encontrar y avanzar la tarea pendiente de ese
        momento, aunque su uuid cambie cada vez."""
        t = Task.objects.create(
            title="No fumar", category=Task.CATEGORY_AVOID, due_date=date.today(),
            due_time=time(22, 0), repeat=Task.REPEAT_DAILY, interval=1,
            user=get_current_user(),
        )
        for _ in range(4):
            pending = Task.objects.get(series_id=t.series_id, is_done=False)
            r = self.client.post(f"/api/series/{t.series_id}/mark/done/")
            self.assertEqual(r.json()["task"]["uuid"], str(pending.uuid))
        self.assertEqual(Task.objects.filter(series_id=t.series_id).count(), 5)

    def test_unknown_series_gives_clean_404(self):
        r = self.client.post(
            "/api/series/00000000-0000-0000-0000-000000000000/mark/done/"
        )
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r["Content-Type"], "application/json")

    def test_failed_action_records_it_as_a_relapse(self):
        t = Task.objects.create(
            title="No fumar", category=Task.CATEGORY_AVOID, due_date=date.today(),
            due_time=time(22, 0), repeat=Task.REPEAT_DAILY, interval=1,
            user=get_current_user(),
        )
        self.client.post(f"/api/series/{t.series_id}/mark/failed/")
        occ = Occurrence.objects.filter(series_id=t.series_id).latest("recorded_at")
        self.assertEqual(occ.result, Occurrence.RESULT_NOT_DONE)


class PlanTaskFlowTests(TestCase):
    """
    Lo que hace la app entendible: creas un plan y te aparece la tarea.
    Le das al play y entrenas. Sin elegir circuito ni ejercicio — el plan
    ya lo decidió, que es para lo que existe.
    """

    def setUp(self):
        self.wp = Exercise.objects.create(
            slug="wp-f", name="Dominadas con peso", mode=Exercise.MODE_POSE,
        )

    def _plan_with_exercise(self):
        self.client.post(reverse("tasks:plan_create"), {
            "name": "Ponerme en forma", "weeks": 12, "is_active": "on",
            "custom_days": ["0", "2", "4"], "due_time": "18:00",
        })
        plan = Plan.objects.get(name="Ponerme en forma")
        self.client.post(reverse("tasks:plan_item_create", args=[plan.pk]), {
            "exercise": self.wp.slug, "progression": "double", "is_headline": "on",
            "start_sets": 4, "start_reps": 6, "start_weight_kg": 0,
            "goal_sets": 4, "goal_reps": 12, "goal_weight_kg": 20,
            "rep_range_low": 6, "weight_increment_kg": 5, "sessions_per_step": 2,
        })
        return plan

    def test_creating_a_plan_creates_its_task(self):
        plan = self._plan_with_exercise()
        self.assertIsNotNone(plan.task)
        self.assertEqual(plan.task.title, "Ponerme en forma")
        self.assertEqual(plan.task.category, Task.CATEGORY_SPORT)

    def test_task_appears_in_the_list(self):
        self._plan_with_exercise()
        html = self.client.get(reverse("tasks:task_list")).content.decode()
        self.assertIn("Ponerme en forma", html)

    def test_play_goes_straight_to_the_session(self):
        """Sin selector de ejercicio: el plan ya decidió."""
        plan = self._plan_with_exercise()
        r = self.client.get(reverse("tasks:task_workout", args=[plan.task.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertIn(f"/plan/{plan.pk}/", r.url)

    def test_session_shows_todays_target(self):
        plan = self._plan_with_exercise()
        html = self.client.get(
            reverse("tasks:plan_session", args=[plan.task.pk, plan.pk])
        ).content.decode()
        self.assertIn("Dominadas con peso", html)
        self.assertIn("4 × 6", html)

    def test_saving_completes_task_and_records_per_exercise(self):
        plan = self._plan_with_exercise()
        task = plan.task
        r = self.client.post(
            reverse("tasks:plan_session_save", args=[task.pk, plan.pk]),
            data=json.dumps({"breakdown": [
                {"exercise": self.wp.slug, "reps": 24, "sets": 4, "seconds": 200},
            ]}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        task.refresh_from_db()
        self.assertTrue(task.is_done)
        self.assertEqual(WorkoutSession.objects.filter(plan=plan).count(), 1)

    def test_pausing_the_plan_removes_its_pending_task(self):
        plan = self._plan_with_exercise()
        self.assertIsNotNone(plan.task)
        plan.is_active = False
        plan.save()
        plan.sync_task()
        self.assertIsNone(plan.task)

    def test_deleting_the_plan_removes_its_task(self):
        plan = self._plan_with_exercise()
        self.client.post(reverse("tasks:plan_delete", args=[plan.pk]))
        plan.refresh_from_db()
        self.assertIsNone(plan.task)


class PostureCameraWorkoutTests(TestCase):
    """
    Plancha / plancha lateral ahora se pueden entrenar sueltas (fuera de
    un circuito): antes, al ser mode="timed", task_workout las excluía
    del todo y las trataba como "no soportadas". Ver POSTURE_COUNTERS en
    views.py.
    """

    def setUp(self):
        self.user = get_current_user()
        self.task = Task.objects.create(title="Plancha", category=Task.CATEGORY_SPORT, user=self.user)

    def test_standalone_plank_renders_the_camera_workout_screen(self):
        r = self.client.get(
            reverse("tasks:task_workout", args=[self.task.pk]) + "?exercise=plank"
        )
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "tasks/task_workout.html")
        self.assertEqual(r.context["exercise"].counter_key, "plank")

    def test_standalone_side_plank_renders_the_camera_workout_screen(self):
        r = self.client.get(
            reverse("tasks:task_workout", args=[self.task.pk]) + "?exercise=side-plank"
        )
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "tasks/task_workout.html")
        self.assertEqual(r.context["exercise"].counter_key, "sideplank")

    def test_standalone_wall_sit_renders_the_camera_workout_screen(self):
        r = self.client.get(
            reverse("tasks:task_workout", args=[self.task.pk]) + "?exercise=wall-sit"
        )
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "tasks/task_workout.html")
        self.assertEqual(r.context["exercise"].counter_key, "wallsit")


class PlanAndFreestyleTests(TestCase):
    """
    Plan y "a mi aire" conviviendo: si el ejercicio está en un plan
    activo manda el plan; si no, mandan los objetivos fijos del circuito.
    """

    def setUp(self):
        self.user = get_current_user()
        self.pull = Exercise.objects.create(
            slug="pull-x", name="Dominadas", mode=Exercise.MODE_POSE, counter_key="pullup",
        )
        self.routine = Routine.objects.create(name="Circuito", user=self.user)
        self.item = RoutineItem.objects.create(
            routine=self.routine, exercise=self.pull, target_sets=3, target_reps=8,
        )
        self.task = Task.objects.create(
            title="Entrenar", category=Task.CATEGORY_SPORT, user=self.user,
        )

    def _plan(self, **kw):
        plan = Plan.objects.create(name="En forma", user=self.user)
        PlanItem.objects.create(
            plan=plan, exercise=self.pull,
            **{"start_sets": 4, "start_reps": 6, "reps_increment": 1,
               "sessions_per_step": 2, **kw},
        )
        return plan

    def test_without_plan_uses_routine_target(self):
        t = self.item.resolved_target(self.user)
        self.assertEqual((t["sets"], t["reps"], t["source"]), (3, 8, "routine"))

    def test_plan_overrides_routine_target(self):
        self._plan()
        t = self.item.resolved_target(self.user)
        self.assertEqual((t["sets"], t["reps"], t["source"]), (4, 6, "plan"))

    def test_inactive_plan_falls_back_to_routine(self):
        plan = self._plan()
        plan.is_active = False
        plan.save()
        self.assertEqual(self.item.resolved_target(self.user)["source"], "routine")

    def test_circuit_saves_one_session_per_exercise(self):
        """Con una sola sesión conjunta, la progresión del plan nunca
        avanzaría (cuenta sesiones por ejercicio) y se perdían las reps."""
        plank = Exercise.objects.create(slug="plank-x", name="Plancha", mode=Exercise.MODE_TIMED)
        RoutineItem.objects.create(routine=self.routine, exercise=plank, order=1)
        r = self.client.post(
            f"/api/tasks/{self.task.uuid}/circuit/{self.routine.uuid}/",
            data=json.dumps({"breakdown": [
                {"exercise": "pull-x", "reps": 18, "sets": 3, "seconds": 120},
                {"exercise": "plank-x", "seconds": 30},
            ]}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["sessions"]), 2)
        self.assertEqual(WorkoutSession.objects.filter(task=self.task).count(), 2)
        # y las repeticiones ya no se pierden
        ws = WorkoutSession.objects.get(task=self.task, exercise="pull-x")
        self.assertEqual(ws.total_reps, 18)

    def test_session_records_plan_and_target(self):
        plan = self._plan()
        self.client.post(
            f"/api/tasks/{self.task.uuid}/circuit/{self.routine.uuid}/",
            data=json.dumps({"breakdown": [{"exercise": "pull-x", "reps": 18, "sets": 3}]}),
            content_type="application/json",
        )
        ws = WorkoutSession.objects.get(task=self.task, exercise="pull-x")
        self.assertEqual(ws.plan, plan)
        self.assertEqual((ws.target_sets, ws.target_reps), (4, 6))
        self.assertEqual(ws.achievement_pct, 75)   # 18 de 24

    def test_plan_climbs_after_enough_sessions(self):
        self._plan()
        for _ in range(2):
            self.client.post(
                f"/api/tasks/{self.task.uuid}/circuit/{self.routine.uuid}/",
                data=json.dumps({"breakdown": [{"exercise": "pull-x", "reps": 24, "sets": 4}]}),
                content_type="application/json",
            )
        self.assertEqual(self.item.resolved_target(self.user)["reps"], 7)


class SingleExerciseCompletionTests(TestCase):
    """
    Regla: un ejercicio SUELTO con objetivo solo completa la tarea si lo
    alcanza; si se queda corto, la tarea sigue pendiente y el porcentaje
    queda guardado en la sesión. Sin objetivo (sin plan), se completa
    como siempre. Cubre la API (móvil) y la web con el mismo criterio,
    porque antes solo la API enlazaba la sesión con el plan.
    """

    def setUp(self):
        self.user = get_current_user()
        self.pull = Exercise.objects.create(
            slug="pull-c", name="Dominadas", mode=Exercise.MODE_POSE, counter_key="pullup",
        )
        self.task = Task.objects.create(
            title="Dominadas sueltas", category=Task.CATEGORY_SPORT,
            subcategory=Task.SUBCATEGORY_UPPER_BODY, user=self.user,
        )
        self.plan = Plan.objects.create(name="Fuerza", user=self.user)
        PlanItem.objects.create(
            plan=self.plan, exercise=self.pull, progression=PlanItem.PROG_REPS,
            start_sets=3, start_reps=8, reps_increment=1, sessions_per_step=2,
        )

    # ---------------------------------------------------------- API

    def test_api_below_target_leaves_task_pending(self):
        r = self.client.post(
            f"/api/tasks/{self.task.uuid}/workout/",
            data=json.dumps({"exercise": "pull-c", "total_reps": 10, "total_sets": 3}),  # objetivo 3x8=24
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.task.refresh_from_db()
        self.assertFalse(self.task.is_done)
        ws = WorkoutSession.objects.get(task=self.task)
        self.assertEqual(ws.achievement_pct, 42)
        self.assertFalse(ws.target_met)

    def test_api_meeting_or_beating_target_completes_task(self):
        r = self.client.post(
            f"/api/tasks/{self.task.uuid}/workout/",
            data=json.dumps({"exercise": "pull-c", "total_reps": 30, "total_sets": 3}),  # 125% del objetivo
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_done)
        ws = WorkoutSession.objects.get(task=self.task)
        self.assertEqual(ws.achievement_pct, 125)

    def test_api_without_plan_always_completes(self):
        """Entreno libre (sin plan que lo siga): no hay objetivo, se
        completa como antes de este cambio."""
        Exercise.objects.create(slug="free-c", name="Sentadillas", mode=Exercise.MODE_POSE)
        r = self.client.post(
            f"/api/tasks/{self.task.uuid}/workout/",
            data=json.dumps({"exercise": "free-c", "total_reps": 5, "total_sets": 1}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_done)

    # ---------------------------------------------------------- web

    def test_web_below_target_leaves_task_pending(self):
        """Regresión: antes la web ni siquiera enlazaba la sesión con el
        plan, así que esto nunca podía funcionar."""
        r = self.client.post(
            reverse("tasks:task_workout_save", args=[self.task.pk]) + "?exercise=pull-c",
            data=json.dumps({"total_reps": 10, "total_sets": 3}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.task.refresh_from_db()
        self.assertFalse(self.task.is_done)
        ws = WorkoutSession.objects.get(task=self.task)
        self.assertEqual(ws.plan, self.plan)
        self.assertEqual(ws.achievement_pct, 42)

    def test_web_meeting_target_completes_task(self):
        r = self.client.post(
            reverse("tasks:task_workout_save", args=[self.task.pk]) + "?exercise=pull-c",
            data=json.dumps({"total_reps": 24, "total_sets": 3}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_done)


class MultiExerciseCompletionTests(TestCase):
    """
    Regla contraria para sesiones con varios ejercicios (circuito o
    plan): la tarea se completa siempre que entrenes, lleguen o no todos
    los ejercicios a su objetivo. El % de cada uno se guarda igual.
    """

    def setUp(self):
        self.user = get_current_user()
        self.plank = Exercise.objects.create(slug="plank-c", name="Plancha", mode=Exercise.MODE_TIMED)
        self.routine = Routine.objects.create(name="Core", user=self.user)
        RoutineItem.objects.create(routine=self.routine, exercise=self.plank, order=0)
        self.task = Task.objects.create(
            title="Circuito core", category=Task.CATEGORY_SPORT, user=self.user,
        )

    def test_web_routine_save_records_one_session_per_exercise(self):
        """Regresión: antes se guardaba UNA sesión combinada
        (exercise='ab-circuit'), y ningún plan por ejercicio la veía."""
        plan = Plan.objects.create(name="Aguante", user=self.user)
        PlanItem.objects.create(
            plan=plan, exercise=self.plank, progression=PlanItem.PROG_REPS,
            start_sets=3, start_seconds=30, reps_increment=5, sessions_per_step=2,
        )
        r = self.client.post(
            reverse("tasks:routine_save", args=[self.task.pk, self.routine.pk]),
            data=json.dumps({"breakdown": [{"exercise": "plank-c", "seconds": 15}]}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        ws = WorkoutSession.objects.get(task=self.task)
        self.assertEqual(ws.exercise, "plank-c")   # no "ab-circuit"
        self.assertEqual(ws.plan, plan)
        self.assertFalse(ws.target_met)            # 15s de 90s (3x30) pedidos
        # pero la tarea se completa igualmente: es una sesión con varios
        # ejercicios en potencia, y aquí lo que cuenta es que entrenaste.
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_done)

    def test_web_routine_save_without_plan_still_completes(self):
        r = self.client.post(
            reverse("tasks:routine_save", args=[self.task.pk, self.routine.pk]),
            data=json.dumps({"breakdown": [{"exercise": "plank-c", "seconds": 40}]}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_done)
        ws = WorkoutSession.objects.get(task=self.task)
        self.assertIsNone(ws.plan)
        self.assertEqual(ws.exercise, "plank-c")


class ExerciseCatalogTests(TestCase):
    """
    Estado del catálogo tras 0002_seed_exercise_catalog (ya editada) +
    0011_camera_exercise_updates (por si alguna base de datos ya había
    corrido la 0002 vieja) — decisión del usuario: Superman y Circuito
    de abdominales fuera del todo; crunch y elevación de piernas con
    cámara; plancha y plancha lateral cronometradas pero con
    counter_key para la comprobación de postura.
    """

    def test_ab_circuit_and_superman_are_gone(self):
        self.assertFalse(Exercise.objects.filter(slug="ab-circuit").exists())
        self.assertFalse(Exercise.objects.filter(slug="superman").exists())

    def test_crunch_and_leg_raise_are_camera_exercises(self):
        crunch = Exercise.objects.get(slug="crunch")
        leg_raise = Exercise.objects.get(slug="leg-raise")
        self.assertEqual(crunch.mode, Exercise.MODE_POSE)
        self.assertEqual(crunch.counter_key, "crunch")
        self.assertEqual(leg_raise.mode, Exercise.MODE_POSE)
        self.assertEqual(leg_raise.counter_key, "legraise")

    def test_situp_already_has_its_own_counter(self):
        situp = Exercise.objects.get(slug="situp")
        self.assertEqual(situp.mode, Exercise.MODE_POSE)
        self.assertEqual(situp.counter_key, "situp")

    def test_plank_and_side_plank_stay_timed_with_counter_key(self):
        plank = Exercise.objects.get(slug="plank")
        side_plank = Exercise.objects.get(slug="side-plank")
        self.assertEqual(plank.mode, Exercise.MODE_TIMED)
        self.assertEqual(plank.counter_key, "plank")
        self.assertEqual(side_plank.mode, Exercise.MODE_TIMED)
        self.assertEqual(side_plank.counter_key, "sideplank")

    def test_bicycle_crunch_stays_plain_timed(self):
        """No todos los cronometrados llevan cámara — bicicleta no tiene
        contador propio y se queda como cronómetro a secas."""
        bicycle = Exercise.objects.get(slug="bicycle-crunch")
        self.assertEqual(bicycle.mode, Exercise.MODE_TIMED)
        self.assertEqual(bicycle.counter_key, "")

    def test_default_routine_no_longer_includes_superman(self):
        routine = Routine.objects.get(name="Abdominales completo")
        slugs = list(routine.items.values_list("exercise__slug", flat=True))
        self.assertNotIn("superman", slugs)
        self.assertNotIn("ab-circuit", slugs)
        self.assertIn("plank", slugs)

    def test_double_crunch_is_a_camera_exercise(self):
        double_crunch = Exercise.objects.get(slug="double-crunch")
        self.assertEqual(double_crunch.mode, Exercise.MODE_POSE)
        self.assertEqual(double_crunch.counter_key, "doublecrunch")

    def test_scissor_kick_is_a_camera_exercise(self):
        scissor = Exercise.objects.get(slug="scissor-kick")
        self.assertEqual(scissor.mode, Exercise.MODE_POSE)
        self.assertEqual(scissor.counter_key, "scissor")

    def test_wall_sit_stays_timed_with_counter_key(self):
        """Silla en pared se aguanta, igual que plancha/plancha lateral
        — no se cuenta en repeticiones, así que va como mode="timed" con
        counter_key puesto, no mode="pose"."""
        wall_sit = Exercise.objects.get(slug="wall-sit")
        self.assertEqual(wall_sit.mode, Exercise.MODE_TIMED)
        self.assertEqual(wall_sit.counter_key, "wallsit")
        self.assertEqual(wall_sit.body_area, "lower_body")

    def test_archer_pullup_is_a_camera_exercise(self):
        """Dominadas de arquero: mismo criterio de subida/bajada que las
        dominadas normales, con su propio counter_key porque además hace
        falta medir el ángulo de cada brazo (ver processArcherPullup en
        workout.js) — por eso no comparte "pullup" como sí hacen
        wide-pullup/chinup/etc."""
        archer = Exercise.objects.get(slug="archer-pullup")
        self.assertEqual(archer.mode, Exercise.MODE_POSE)
        self.assertEqual(archer.counter_key, "archerpullup")
        self.assertEqual(archer.body_area, "upper_body")

    def test_archer_pullup_counter_key_is_registered_as_supported(self):
        """0013 añade el ejercicio al catálogo, pero task_workout solo lo
        trata como soportado por cámara si su counter_key también está en
        views.COUNTERS (ver is_pose_supported) — sin esto, el ejercicio
        existiría pero la pantalla de entreno lo trataría como "no
        soportado"."""
        from tasks.views import COUNTERS
        self.assertIn("archerpullup", COUNTERS)

    def test_incline_push_up_is_a_camera_exercise(self):
        """Flexiones inclinadas: mismo gesto de brazo que push-up, pero
        con su PROPIO counter_key ("inclinepushup", no "pushup") porque el
        contador de cámara tiene que aceptar cualquier inclinación de pies
        sin techo (ver processInclinePushup en workout.js y el porqué en
        0023_add_incline_push_up) — a diferencia de weighted-squat, que sí
        reutiliza el counter_key de squat porque ahí no cambia nada del
        gesto que MediaPipe mide."""
        incline_push_up = Exercise.objects.get(slug="incline-push-up")
        self.assertEqual(incline_push_up.mode, Exercise.MODE_POSE)
        self.assertEqual(incline_push_up.counter_key, "inclinepushup")
        self.assertEqual(incline_push_up.body_area, "upper_body")

    def test_incline_push_up_counter_key_is_registered_as_supported(self):
        """Igual que test_archer_pullup_counter_key_is_registered_as_supported:
        sin "inclinepushup" en views.COUNTERS, task_workout trataría el
        ejercicio como no soportado por cámara aunque exista en el
        catálogo."""
        from tasks.views import COUNTERS
        self.assertIn("inclinepushup", COUNTERS)

    def test_dumbbell_curl_is_a_camera_exercise(self):
        """Curl con mancuernas (0024_add_dumbbell_curl): counter_key propio
        ("dumbbellcurl") porque el contador mide el ángulo de codo de
        FRENTE a la cámara (como dominadas), no de perfil como push-up/
        squat/dip, y necesita comprobar que el codo se queda pegado al
        costado y la muñeca no sube a la altura de la cara — ver
        processDumbbellCurl en workout.js y el porqué en la migración."""
        curl = Exercise.objects.get(slug="dumbbell-curl")
        self.assertEqual(curl.mode, Exercise.MODE_POSE)
        self.assertEqual(curl.counter_key, "dumbbellcurl")
        self.assertEqual(curl.body_area, "upper_body")

    def test_dumbbell_curl_counter_key_is_registered_as_supported(self):
        """Igual que test_archer_pullup_counter_key_is_registered_as_supported:
        sin "dumbbellcurl" en views.COUNTERS, task_workout trataría el
        ejercicio como no soportado por cámara aunque exista en el
        catálogo."""
        from tasks.views import COUNTERS
        self.assertIn("dumbbellcurl", COUNTERS)


class WebCircuitBuilderTests(TestCase):
    """
    El constructor de circuitos de la web aceptaba solo ejercicios
    mode="timed" — se relaja para admitir cualquier ejercicio activo
    (cámara incluida), igual que ya hacía la API para la app móvil (ver
    ApiTests.test_routine_accepts_any_active_exercise).
    """

    def setUp(self):
        self.user = get_current_user()
        self.plank = Exercise.objects.create(slug="plank-w", name="Plancha", mode=Exercise.MODE_TIMED)
        self.crunch = Exercise.objects.create(
            slug="crunch-w", name="Crunch", mode=Exercise.MODE_POSE, counter_key="crunch",
        )

    def test_camera_exercises_appear_in_the_available_list(self):
        r = self.client.get(reverse("tasks:routine_create"))
        self.assertContains(r, "Crunch")
        self.assertContains(r, "Plancha")

    def test_saving_a_mixed_routine_keeps_both_items(self):
        r = self.client.post(reverse("tasks:routine_create"), {
            "name": "Mixto", "subcategory": "lower_body",
            "default_work_seconds": 40, "default_rest_seconds": 20,
            "items": f"{self.plank.pk},{self.crunch.pk}",
        })
        self.assertEqual(r.status_code, 302)
        routine = Routine.objects.get(name="Mixto")
        self.assertEqual(
            list(routine.items.order_by("order").values_list("exercise_id", flat=True)),
            [self.plank.pk, self.crunch.pk],
        )


class WebCircuitPlayAndSaveTests(TestCase):
    def setUp(self):
        self.user = get_current_user()
        self.plank = Exercise.objects.create(
            slug="plank-play", name="Plancha", mode=Exercise.MODE_TIMED, counter_key="plank",
        )
        self.crunch = Exercise.objects.create(
            slug="crunch-play", name="Crunch", mode=Exercise.MODE_POSE, counter_key="crunch",
        )
        self.routine = Routine.objects.create(name="Circuito mixto", user=self.user)
        RoutineItem.objects.create(routine=self.routine, exercise=self.plank, order=0)
        RoutineItem.objects.create(routine=self.routine, exercise=self.crunch, order=1)
        self.task = Task.objects.create(title="Circuito", category=Task.CATEGORY_SPORT, user=self.user)

    def test_items_json_carries_mode_and_counter_key(self):
        r = self.client.get(reverse("tasks:routine_play", args=[self.task.pk, self.routine.pk]))
        self.assertEqual(r.status_code, 200)
        items = json.loads(r.context["items_json"])
        by_slug = {i["slug"]: i for i in items}
        self.assertEqual(by_slug["plank-play"]["mode"], Exercise.MODE_TIMED)
        self.assertEqual(by_slug["plank-play"]["counter_key"], "plank")
        self.assertEqual(by_slug["crunch-play"]["mode"], Exercise.MODE_POSE)
        self.assertEqual(by_slug["crunch-play"]["counter_key"], "crunch")

    def test_routine_save_records_reps_for_camera_items(self):
        r = self.client.post(
            reverse("tasks:routine_save", args=[self.task.pk, self.routine.pk]),
            data=json.dumps({"breakdown": [
                {"exercise": "plank-play", "seconds": 40},
                {"exercise": "crunch-play", "reps": 15, "sets": 3, "seconds": 60},
            ]}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        crunch_session = WorkoutSession.objects.get(task=self.task, exercise="crunch-play")
        self.assertEqual(crunch_session.total_reps, 15)
        self.assertEqual(crunch_session.total_sets, 3)
        plank_session = WorkoutSession.objects.get(task=self.task, exercise="plank-play")
        self.assertEqual(plank_session.session_duration_seconds, 40)


class PlanMissedDayTests(TestCase):
    """
    Sin hora límite, una tarea de plan no expiraba nunca sola — se
    quedaba pendiente indefinidamente y se podía completar días después
    como si tal cosa, sin que contara como fallo. Y aunque expirase, sin
    ninguna WorkoutSession ese día quedaba invisible para el plan: no
    contaba ni como fallo ni movía la racha de cara al deload.
    """

    def setUp(self):
        self.user = get_current_user()
        self.pull = Exercise.objects.create(slug="pull-miss", name="Dominadas", mode=Exercise.MODE_POSE)
        self.plan = Plan.objects.create(name="Constancia", user=self.user)
        self.item = PlanItem.objects.create(
            plan=self.plan, exercise=self.pull, progression=PlanItem.PROG_REPS,
            start_sets=2, start_reps=5, goal_sets=4, goal_reps=12,
        )

    def test_plan_task_defaults_to_end_of_day_deadline(self):
        task = self.plan.sync_task()
        self.assertEqual(task.due_time, time(23, 59))

    def test_unplayed_day_resolves_as_failed_with_zero_percent(self):
        task = self.plan.sync_task()
        task.due_date = timezone.localtime(timezone.now()).date() - timedelta(days=1)
        task.save()

        expired = Task.expire_overdue()
        self.assertIn(task.pk, [t.pk for t in expired])

        task.refresh_from_db()
        self.assertTrue(task.is_done)
        self.assertTrue(task.expired)

        ws = WorkoutSession.objects.get(task=task)
        self.assertEqual(ws.achievement_pct, 0)
        self.assertEqual(ws.plan, self.plan)

        successes, streak = self.item.successes_and_streak()
        self.assertEqual(successes, 0)
        self.assertEqual(streak, 1)  # el día perdido ya cuenta

    def test_does_not_double_record_if_something_was_actually_played(self):
        """Si sí jugaste algo (aunque no llegaras a marcarla a tiempo),
        no se inventa una sesión de 0% encima de la real."""
        task = self.plan.sync_task()
        WorkoutSession.objects.create(
            task=task, user=self.user, plan=self.plan, exercise="pull-miss",
            total_reps=6, total_sets=2, target_sets=2, target_reps=5,
        )
        task.due_date = timezone.localtime(timezone.now()).date() - timedelta(days=1)
        task.save()

        Task.expire_overdue()

        self.assertEqual(WorkoutSession.objects.filter(task=task).count(), 1)


class ListFilteringTests(TestCase):
    """
    Regresiones de dos molestias reales:

    Al resolver una tarea repetida se genera ya la del día siguiente, y
    aparecía en la lista al instante — podías marcarla otra vez el mismo
    día y contaba dos veces en las estadísticas.

    Y las hechas se acumulaban para siempre: a los treinta días tenías
    treinta "No fumar" en la lista.
    """

    def setUp(self):
        self.user = get_current_user()

    def test_tomorrows_task_is_not_shown_today(self):
        t = Task.objects.create(
            title="No fumar", category=Task.CATEGORY_AVOID, due_date=date.today(),
            due_time=time(22, 0), repeat=Task.REPEAT_DAILY, interval=1, user=self.user,
        )
        t.mark_done()
        # existe, pero no se enseña hasta que le toque
        tomorrow = Task.objects.get(series_id=t.series_id, is_done=False)
        self.assertEqual(tomorrow.due_date, date.today() + timedelta(days=1))

        html = self.client.get(reverse("tasks:task_list")).content.decode()
        self.assertEqual(html.count("No fumar"), 1)   # solo en Hechas

        api = self.client.get("/api/tasks/").json()
        self.assertEqual(api["pending"], [])

    def test_overdue_tasks_are_still_shown(self):
        """Una tarea vencida sigue pendiente y debe verse: el filtro es
        para el futuro, no para el pasado."""
        Task.objects.create(
            title="Atrasada", due_date=date.today() - timedelta(days=2), user=self.user,
        )
        api = self.client.get("/api/tasks/").json()
        self.assertEqual([t["title"] for t in api["pending"]], ["Atrasada"])

    def test_tasks_without_date_are_always_shown(self):
        Task.objects.create(title="Cuando pueda", user=self.user)
        api = self.client.get("/api/tasks/").json()
        self.assertIn("Cuando pueda", [t["title"] for t in api["pending"]])

    def test_completed_list_only_shows_today(self):
        old = Task.objects.create(title="Vieja", user=self.user)
        old.mark_done()
        Task.objects.filter(pk=old.pk).update(
            completed_at=timezone.now() - timedelta(days=5)
        )
        recent = Task.objects.create(title="De hoy", user=self.user)
        recent.mark_done()

        api = self.client.get("/api/tasks/").json()
        titles = [t["title"] for t in api["completed"]]
        self.assertIn("De hoy", titles)
        self.assertNotIn("Vieja", titles)


class ApiTests(TestCase):
    """API JSON que consume la app móvil."""

    def _post(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type="application/json")

    def _patch(self, url, payload):
        return self.client.patch(url, data=json.dumps(payload), content_type="application/json")

    def test_create_and_list(self):
        r = self._post("/api/tasks/create/", {"title": "Desde la app", "category": "study"})
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.json()["ok"])
        r = self.client.get("/api/tasks/")
        self.assertEqual(len(r.json()["pending"]), 1)

    def test_dates_are_parsed_not_passed_through(self):
        """Regresión: asignar la fecha como cadena rompía el serializador."""
        r = self._post("/api/tasks/create/", {"title": "Con fecha", "due_date": "2026-07-27", "due_time": "22:00"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["task"]["due_date"], "2026-07-27")
        self.assertEqual(r.json()["task"]["due_time"], "22:00")

    def test_invalid_date_is_rejected_cleanly(self):
        r = self._post("/api/tasks/create/", {"title": "X", "due_date": "27-07-2026"})
        self.assertEqual(r.status_code, 400)

    def test_invalid_category_falls_back(self):
        """La app no debe poder meter valores fuera de los choices."""
        r = self._post("/api/tasks/create/", {"title": "X", "category": "inventada"})
        self.assertEqual(r.json()["task"]["category"], Task.CATEGORY_GENERAL)

    def test_empty_title_rejected(self):
        r = self._post("/api/tasks/create/", {"title": "   "})
        self.assertEqual(r.status_code, 400)

    def test_delete_is_soft_and_hides_task(self):
        r = self._post("/api/tasks/create/", {"title": "Borrame"})
        uuid_ = r.json()["task"]["uuid"]
        self.client.delete(f"/api/tasks/{uuid_}/")
        t = Task.objects.get(uuid=uuid_)
        self.assertIsNotNone(t.deleted_at)  # la fila sigue existiendo
        listed = self.client.get("/api/tasks/").json()
        self.assertEqual(len(listed["pending"]) + len(listed["completed"]), 0)

    def test_mark_actions(self):
        r = self._post("/api/tasks/create/", {"title": "Marcame"})
        uuid_ = r.json()["task"]["uuid"]
        self.assertEqual(self.client.post(f"/api/tasks/{uuid_}/mark/done/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/tasks/{uuid_}/mark/inventada/").status_code, 400)

    def test_routine_accepts_any_active_exercise(self):
        """Un circuito puede mezclar cronometrados y de cámara: una serie
        de tren superior (dominadas, anchas...) es tan válida como un
        circuito de abdominales."""
        Exercise.objects.create(slug="plank-t", name="Plancha", mode=Exercise.MODE_TIMED)
        Exercise.objects.create(slug="pullup-t", name="Dominadas", mode=Exercise.MODE_POSE)
        r = self._post("/api/routines/", {"name": "Mixto", "items": ["plank-t", "pullup-t"]})
        self.assertEqual(r.status_code, 201)
        slugs = [i["slug"] for i in r.json()["routine"]["items"]]
        self.assertEqual(slugs, ["plank-t", "pullup-t"])

    def test_routine_ignores_inactive_exercises(self):
        Exercise.objects.create(slug="ok-t", name="Ok", mode=Exercise.MODE_TIMED)
        Exercise.objects.create(slug="off-t", name="Off", mode=Exercise.MODE_TIMED, is_active=False)
        r = self._post("/api/routines/", {"name": "X", "items": ["ok-t", "off-t"]})
        self.assertEqual([i["slug"] for i in r.json()["routine"]["items"]], ["ok-t"])

    def test_routine_needs_at_least_one_exercise(self):
        r = self._post("/api/routines/", {"name": "Vacio", "items": []})
        self.assertEqual(r.status_code, 400)

    def test_cors_allows_capacitor_origin_only(self):
        r = self.client.get("/api/tasks/", HTTP_ORIGIN="https://localhost")
        self.assertEqual(r.headers.get("Access-Control-Allow-Origin"), "https://localhost")
        r = self.client.get("/api/tasks/", HTTP_ORIGIN="https://evil.example.com")
        self.assertIsNone(r.headers.get("Access-Control-Allow-Origin"))

    def test_cors_not_applied_outside_api(self):
        """La web normal no debe aceptar peticiones de otros orígenes."""
        r = self.client.get(reverse("tasks:task_list"), HTTP_ORIGIN="https://localhost")
        self.assertIsNone(r.headers.get("Access-Control-Allow-Origin"))

    def test_malformed_json_returns_json_not_html(self):
        """Si la app manda basura, debe recibir JSON — no una página de
        error HTML que no sabría interpretar."""
        r = self.client.post("/api/tasks/create/", data="{no es json", content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["ok"], False)

    def test_not_found_returns_json_not_html(self):
        """Regresión: pedir algo inexistente devolvía la página HTML de
        Django, la app hacía resp.json(), reventaba, y el usuario veía un
        error incomprensible en vez de saber qué había pasado."""
        r = self.client.delete("/api/tasks/00000000-0000-0000-0000-000000000000/")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r["Content-Type"], "application/json")
        self.assertFalse(r.json()["ok"])

    def test_deleting_twice_gives_clean_json_error(self):
        """Borrar dos veces (p.ej. reintento de la cola sin conexión) no
        debe soltar HTML."""
        uuid_ = self._post("/api/tasks/create/", {"title": "Doble borrado"}).json()["task"]["uuid"]
        self.assertEqual(self.client.delete(f"/api/tasks/{uuid_}/").status_code, 200)
        r2 = self.client.delete(f"/api/tasks/{uuid_}/")
        self.assertEqual(r2.status_code, 404)
        self.assertEqual(r2["Content-Type"], "application/json")


class UdemyTrackingTests(TestCase):
    """
    Fase 2 del tracking de tiempo en Udemy (ver docs/plan-tracking-tiempo.md):
    subtipo "Curso de Udemy" dentro de Estudio, TimerSession.SOURCE_PC_USAGE,
    y el cierre de la serie entera cuando la extensión de Chrome detecta el
    curso al 100%.
    """
    def setUp(self):
        self.user = get_current_user()
        self.task = Task.objects.create(
            title="Curso de Linux", category=Task.CATEGORY_STUDY,
            subcategory=Task.SUBCATEGORY_UDEMY, watch_keyword="Linux",
            repeat=Task.REPEAT_DAILY, user=self.user,
        )

    def test_capability_and_meta_expose_udemy(self):
        self.assertTrue(self.task.has_capability("app_usage"))
        r = self.client.get(reverse("api:meta"))
        values = {c["value"] for c in r.json()["study_subcategories"]}
        self.assertIn("udemy", values)

    def test_task_list_exposes_watch_keyword(self):
        r = self.client.get(reverse("api:task_list"))
        mine = [t for t in r.json()["pending"] if t["uuid"] == str(self.task.uuid)]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]["watch_keyword"], "Linux")
        self.assertEqual(mine[0]["subcategory"], "udemy")

    def test_focus_save_with_pc_usage_creates_session(self):
        r = self.client.post(
            reverse("api:focus_save", args=[self.task.uuid]),
            data=json.dumps({"minutes": 15, "source": "pc_usage", "app_package": "udemy.com"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        ts = TimerSession.objects.get(task=self.task)
        self.assertEqual(ts.source, TimerSession.SOURCE_PC_USAGE)
        self.assertEqual(ts.app_package, "udemy.com")
        self.assertEqual(ts.minutes, 15)

    def test_course_complete_stops_the_series(self):
        r = self.client.post(reverse("api:task_mark", args=[self.task.uuid, "course-complete"]))
        self.assertEqual(r.status_code, 200, r.content)
        self.task.refresh_from_db()
        self.assertTrue(self.task.is_done)
        self.assertEqual(self.task.repeat, Task.REPEAT_NONE)
        # No debe haber nacido una instancia de mañana: finish_recurring_series
        # pone repeat=NONE ANTES de mark_done(), así que _spawn_next() no crea nada.
        self.assertEqual(Task.objects.filter(series_id=self.task.series_id).count(), 1)

    def test_time_stats_picks_up_udemy_sessions(self):
        from .time_stats import time_totals
        TimerSession.objects.create(
            task=self.task, user=self.user, subcategory=self.task.subcategory,
            source=TimerSession.SOURCE_PC_USAGE, app_package="udemy.com", minutes=120,
        )
        buckets = time_totals(self.user)
        self.assertIn("study_udemy", buckets)
        self.assertEqual(buckets["study_udemy"]["all_time_hours"], 2.0)

    # ---------------------------------------------------- Fase 3 (formulario web)

    def test_web_create_saves_watch_keyword_and_target_minutes(self):
        r = self.client.post(reverse("tasks:task_create"), {
            "title": "Curso de Excel", "category": "study", "subcategory": "udemy",
            "watch_keyword": "Excel completo", "target_minutes": "45",
            "due_date": "2026-09-10", "due_time": "20:00", "repeat": "daily",
        })
        self.assertEqual(r.status_code, 302, r.content)
        t = Task.objects.get(title="Curso de Excel")
        self.assertEqual(t.watch_keyword, "Excel completo")
        self.assertEqual(t.target_minutes, 45)
        self.assertEqual(t.category, Task.CATEGORY_STUDY)
        self.assertEqual(t.subcategory, Task.SUBCATEGORY_UDEMY)

    def test_web_edit_updates_watch_keyword(self):
        r = self.client.post(reverse("tasks:task_edit", args=[self.task.pk]), {
            "title": self.task.title, "category": "study", "subcategory": "udemy",
            "watch_keyword": "Linux avanzado", "target_minutes": "30",
            "due_date": "2026-09-10", "due_time": "20:00", "repeat": "daily",
        })
        self.assertEqual(r.status_code, 302, r.content)
        self.task.refresh_from_db()
        self.assertEqual(self.task.watch_keyword, "Linux avanzado")

    def test_web_form_renders_with_udemy_task(self):
        """La página de editar no debe romperse con una tarea de Udemy ya guardada."""
        r = self.client.get(reverse("tasks:task_edit", args=[self.task.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "watch_keyword")
