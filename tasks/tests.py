import json
from datetime import date, time, timedelta

from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from .models import Exercise, Occurrence, Task
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

    def test_routine_rejects_non_timed_exercises(self):
        """Un circuito solo admite ejercicios cronometrados: por API no se
        debe poder colar uno de cámara."""
        Exercise.objects.create(slug="plank-t", name="Plancha", mode=Exercise.MODE_TIMED)
        Exercise.objects.create(slug="pullup-t", name="Dominadas", mode=Exercise.MODE_POSE)
        r = self._post("/api/routines/", {"name": "Mixto", "items": ["plank-t", "pullup-t"]})
        self.assertEqual(r.status_code, 201)
        slugs = [i["slug"] for i in r.json()["routine"]["items"]]
        self.assertEqual(slugs, ["plank-t"])

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
