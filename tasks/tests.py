import json
from datetime import date, time, timedelta

from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from .models import Exercise, Occurrence, Task, WorkoutSession
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
        debe resolver en éxito una antitarea vencida, sin tocar nada a mano."""
        t = Task.objects.create(
            title="No gastar de más", due_time=time(0, 1), category=Task.CATEGORY_AVOID, user=get_current_user(),
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
        past = (timezone.localtime(timezone.now()) - timedelta(hours=5)).time().replace(microsecond=0)
        t = Task.objects.create(
            title="No fumar", category=Task.CATEGORY_AVOID,
            due_date=None, due_time=past, user=get_current_user(),
        )
        Task.expire_overdue()
        t.refresh_from_db()
        self.assertTrue(t.is_done)      # se resolvió sola, correcto

        t.reopen()
        Task.expire_overdue()           # lo que pasa al recargar la lista
        t.refresh_from_db()
        self.assertFalse(t.is_done)     # y sigue arriba

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
