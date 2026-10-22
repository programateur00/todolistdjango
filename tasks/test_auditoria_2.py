"""
Tests de regresión de la segunda revisión de octubre 2026 (la primera está en
test_auditoria.py): pequeños fallos de "la misma petición llega dos veces".

La app móvil guarda en cola lo que no pudo enviar sin red y lo reenvía al
volver la conexión, y en la web un doble toque envía el formulario dos veces:
el servidor tiene que aguantar la petición repetida sin romper nada.
"""
import json
import uuid as uuid_mod
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import CourseModule, Plan, Task
from .utils import get_current_user


def _language_plan(modules=8, daily=30):
    plan = Plan.objects.create(
        user=get_current_user(), name="Alemán", plan_type=Plan.PLAN_TYPE_STUDY,
        study_subtype=Plan.STUDY_SUBTYPE_LANGUAGE, language_name="Alemán",
        level_from="A1", level_to="A2", language_daily_minutes=daily, weeks=8,
        repeat="daily", started_on=date.today(),
    )
    for i in range(modules):
        CourseModule.objects.create(
            plan=plan, order=i, level="A1", youtube_video_id=f"vid{i:08d}",
            title=f"Vídeo {i}", duration_seconds=300,
        )
    plan.sync_task()
    return plan, Task.objects.get(series_id=plan.task_series_id, is_done=False)


def _watched(plan):
    return plan.course_modules.filter(watched_at__isnull=False).count()


class DuplicateVideoSaveTests(TestCase):
    """Terminar la misma sesión de vídeo dos veces (doble toque, o la copia
    que quedó en cola sin red) avanzaba el temario DOS veces: se "comía" el
    siguiente vídeo del curso sin haberlo visto."""

    PAYLOAD = {"minutes": 10, "videos_watched": 2}

    def _api(self, task):
        return self.client.post(
            reverse("api:video_save", args=[task.uuid]),
            data=json.dumps(self.PAYLOAD), content_type="application/json",
        )

    def _web(self, task):
        return self.client.post(
            reverse("tasks:task_video_save", args=[task.pk]),
            data=json.dumps(self.PAYLOAD), content_type="application/json",
        )

    def test_api_same_save_twice_advances_once(self):
        plan, task = _language_plan()
        self.assertEqual(self._api(task).status_code, 200)
        self.assertEqual(self._api(task).status_code, 200)
        self.assertEqual(_watched(plan), 2)

    def test_web_same_save_twice_advances_once(self):
        plan, task = _language_plan()
        self.assertEqual(self._web(task).status_code, 200)
        self.assertEqual(self._web(task).status_code, 200)
        self.assertEqual(_watched(plan), 2)

    def test_repeated_save_does_not_spawn_a_second_next_task(self):
        plan, task = _language_plan()
        self._api(task)
        self._api(task)
        self._web(task)
        pending = Task.objects.filter(series_id=task.series_id, is_done=False)
        self.assertEqual(pending.count(), 1)

    def test_next_day_task_still_advances_normally(self):
        """La guarda es por tarea hecha, no por plan: el vídeo de mañana (otra
        tarea de la misma serie) sigue sumando."""
        plan, task = _language_plan()
        self._api(task)
        nxt = Task.objects.get(series_id=task.series_id, is_done=False)
        self.assertNotEqual(nxt.pk, task.pk)
        self._api(nxt)
        self.assertEqual(_watched(plan), 4)

    def test_repeated_save_of_the_last_modules_keeps_the_plan_closed_once(self):
        plan, task = _language_plan(modules=2)
        r1 = self._web(task)
        plan.refresh_from_db()
        first_closed_at = plan.closed_at
        self.assertIsNotNone(first_closed_at)
        self.assertIn("/planes/", r1.json()["redirect_url"])
        r2 = self._web(task)
        self.assertEqual(r2.status_code, 200)
        plan.refresh_from_db()
        self.assertEqual(plan.closed_at, first_closed_at)
        self.assertEqual(_watched(plan), 2)

    def test_first_save_after_manual_reopen_counts_again(self):
        """Reabrir la tarea («me equivoqué») y terminarla de nuevo sí vuelve a
        contar: la guarda mira si la tarea YA estaba hecha, no si hubo antes
        un guardado."""
        plan, task = _language_plan()
        self._api(task)
        task.refresh_from_db()
        task.reopen()
        self._api(task)
        self.assertEqual(_watched(plan), 4)


class IdempotentApiTaskCreateTests(TestCase):
    """La app genera el uuid de la tarea en el móvil. Si la respuesta del
    primer envío se pierde, la cola lo reenvía: antes chocaba con el uuid
    único (500) y, como la cola se detiene en los 5xx, TODOS los cambios
    posteriores se quedaban sin enviar para siempre."""

    URL = "/api/tasks/create/"

    def _create(self, **extra):
        body = {"title": "Comprar pan", "category": "general", "repeat": "none"}
        body.update(extra)
        return self.client.post(self.URL, data=json.dumps(body), content_type="application/json")

    def test_client_uuid_is_respected(self):
        u = str(uuid_mod.uuid4())
        r = self._create(uuid=u)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["task"]["uuid"], u)

    def test_same_uuid_twice_returns_the_task_already_created(self):
        u = str(uuid_mod.uuid4())
        r1 = self._create(uuid=u)
        r2 = self._create(uuid=u)
        self.assertEqual(r1.status_code, 201, r1.content)
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertTrue(r2.json()["ok"])
        self.assertEqual(r2.json()["task"]["uuid"], u)
        self.assertEqual(Task.objects.filter(uuid=u).count(), 1)

    def test_client_uuid_alias_is_idempotent_too(self):
        u = str(uuid_mod.uuid4())
        self._create(client_uuid=u)
        r2 = self._create(client_uuid=u)
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertEqual(Task.objects.filter(uuid=u).count(), 1)

    def test_garbage_uuid_is_ignored_and_a_fresh_one_is_generated(self):
        for junk in ("no-es-un-uuid", 12345, ["x"]):
            r = self._create(uuid=junk)
            self.assertEqual(r.status_code, 201, (junk, r.content))
        self.assertEqual(Task.objects.filter(title="Comprar pan").count(), 3)

    def test_uuid_owned_by_another_account_is_not_reused_nor_leaked(self):
        other = get_user_model().objects.create(username="otra-cuenta")
        foreign = Task.objects.create(title="Ajena", user=other)
        r = self._create(uuid=str(foreign.uuid))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertNotEqual(r.json()["task"]["uuid"], str(foreign.uuid))
        self.assertEqual(r.json()["task"]["title"], "Comprar pan")
        foreign.refresh_from_db()
        self.assertEqual(foreign.title, "Ajena")

    def test_replay_does_not_overwrite_what_the_user_changed_since(self):
        u = str(uuid_mod.uuid4())
        self._create(uuid=u)
        t = Task.objects.get(uuid=u)
        t.title = "Comprar pan integral"
        t.save()
        r = self._create(uuid=u)
        self.assertEqual(r.status_code, 200, r.content)
        t.refresh_from_db()
        self.assertEqual(t.title, "Comprar pan integral")
        self.assertEqual(r.json()["task"]["title"], "Comprar pan integral")

    def test_invalid_payload_with_a_known_uuid_still_returns_the_existing_task(self):
        """Un reenvío es un reenvío: no se vuelve a validar el cuerpo."""
        u = str(uuid_mod.uuid4())
        self._create(uuid=u)
        r = self.client.post(
            self.URL, data=json.dumps({"uuid": u}), content_type="application/json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["task"]["uuid"], u)

    def test_new_task_without_uuid_still_validates_the_title(self):
        r = self.client.post(
            self.URL, data=json.dumps({"title": "", "category": "general"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)


class WebTaskCreateReplayTests(TestCase):
    """El formulario web de «Nueva tarea» lleva un uuid generado en el
    navegador. Si el mismo formulario llegaba dos veces (doble clic, o volver
    atrás y reenviar) la segunda reventaba con un 500 aunque la primera tarea
    SÍ se hubiera creado: el usuario veía una página de error."""

    def _post(self, u, **extra):
        data = {"title": "Comprar pan", "category": "general", "repeat": "none", "client_uuid": u}
        data.update(extra)
        return self.client.post(reverse("tasks:task_create"), data)

    def test_same_form_twice_creates_one_task_and_no_error(self):
        u = str(uuid_mod.uuid4())
        r1 = self._post(u)
        r2 = self._post(u)
        self.assertEqual(r1.status_code, 302)
        self.assertEqual(r2.status_code, 302)
        self.assertEqual(Task.objects.filter(uuid=u).count(), 1)
        self.assertEqual(Task.objects.filter(title="Comprar pan").count(), 1)

    def test_replay_keeps_what_the_user_changed_in_between(self):
        u = str(uuid_mod.uuid4())
        self._post(u)
        t = Task.objects.get(uuid=u)
        t.title = "Comprar pan integral"
        t.save()
        self._post(u)
        t.refresh_from_db()
        self.assertEqual(t.title, "Comprar pan integral")
        self.assertEqual(Task.objects.count(), 1)

    def test_uuid_of_another_account_is_never_reused(self):
        other = get_user_model().objects.create(username="otra-cuenta")
        foreign = Task.objects.create(title="Ajena", user=other)
        r = self._post(str(foreign.uuid))
        self.assertEqual(r.status_code, 302)
        foreign.refresh_from_db()
        self.assertEqual(foreign.title, "Ajena")
        mine = Task.objects.get(title="Comprar pan")
        self.assertNotEqual(mine.uuid, foreign.uuid)
        self.assertEqual(mine.user_id, get_current_user().pk)

    def test_first_submission_uses_the_uuid_from_the_browser(self):
        u = str(uuid_mod.uuid4())
        self._post(u)
        self.assertEqual(str(Task.objects.get(title="Comprar pan").uuid), u)

    def test_without_uuid_or_with_garbage_a_normal_task_is_created(self):
        self._post("")
        self._post("no-es-un-uuid")
        self.assertEqual(Task.objects.filter(title="Comprar pan").count(), 2)


class ImpossibleDatesAndTimesNeverCrashTests(TestCase):
    """Un año de 5 cifras tecleado sin querer en el campo de fecha, o una fecha
    imposible que llega a la API, acababan en un error 500 en vez de en un
    aviso (editar una tarea ya lo controlaba; crear no)."""

    def _web_create(self, **extra):
        data = {"title": "Con fecha", "category": "general", "repeat": "none"}
        data.update(extra)
        return self.client.post(reverse("tasks:task_create"), data)

    def test_web_create_with_a_five_digit_year_shows_a_message_not_a_500(self):
        r = self._web_create(due_date="20266-10-17")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "La fecha no es válida")
        self.assertFalse(Task.objects.filter(title="Con fecha").exists())

    def test_web_create_with_an_impossible_date_shows_a_message(self):
        r = self._web_create(due_date="2026-02-30")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "La fecha no es válida")
        self.assertFalse(Task.objects.filter(title="Con fecha").exists())

    def test_web_create_with_a_valid_date_still_works(self):
        r = self._web_create(due_date="2026-12-24")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Task.objects.get(title="Con fecha").due_date, date(2026, 12, 24))

    def test_web_create_without_date_still_works(self):
        self.assertEqual(self._web_create().status_code, 302)

    def _api(self, method, url, body):
        return getattr(self.client, method)(url, data=json.dumps(body), content_type="application/json")

    def test_api_task_impossible_date_or_time_is_a_400_with_a_message(self):
        for field, value, text in (
            ("due_date", "2026-02-30", "Fecha inválida"),
            ("due_date", "2026-13-45", "Fecha inválida"),
            ("due_date", 5, "Fecha inválida"),
            ("due_date", ["x"], "Fecha inválida"),
            ("due_time", "25:61", "Hora inválida"),
            ("due_time", "24:00", "Hora inválida"),
            ("due_time", 5, "Hora inválida"),
        ):
            r = self._api("post", "/api/tasks/create/", {"title": "T", "category": "general", field: value})
            self.assertEqual(r.status_code, 400, (field, value, r.content))
            self.assertIn(text, r.json()["error"])
        self.assertFalse(Task.objects.filter(title="T").exists())

    def test_api_task_patch_with_impossible_date_keeps_the_task_untouched(self):
        t = Task.objects.create(title="Editar", user=get_current_user(), due_date=date(2026, 1, 5))
        r = self._api("patch", f"/api/tasks/{t.uuid}/", {"due_date": "2026-02-30"})
        self.assertEqual(r.status_code, 400)
        t.refresh_from_db()
        self.assertEqual(t.due_date, date(2026, 1, 5))

    def test_api_task_valid_date_and_time_still_work(self):
        r = self._api("post", "/api/tasks/create/", {
            "title": "Bien", "category": "general", "due_date": "2026-12-24", "due_time": "07:30",
        })
        self.assertEqual(r.status_code, 201, r.content)
        t = Task.objects.get(title="Bien")
        self.assertEqual(t.due_date, date(2026, 12, 24))
        self.assertEqual(t.due_time.strftime("%H:%M"), "07:30")

    def test_api_plan_impossible_start_date_falls_back_to_today(self):
        r = self._api("post", "/api/plans/create/", {
            "name": "Plan", "plan_type": "study", "started_on": "2026-02-30", "due_time": "08:00",
        })
        self.assertLess(r.status_code, 500, r.content)

    def test_api_plan_impossible_time_is_a_400(self):
        r = self._api("post", "/api/plans/create/", {
            "name": "Plan", "plan_type": "study", "due_time": "25:61",
        })
        self.assertEqual(r.status_code, 400, r.content)


class QuizFailureNeverBreaksVideoSaveTests(TestCase):
    """El test de repaso lo genera una IA por red: si esa llamada se rompe de
    una forma que nadie previó (conexión cortada a medias...), el vídeo ya está
    guardado y la web no puede acabar mostrando «No se pudo guardar»."""

    def _plan_with_quiz(self):
        plan, task = _language_plan(modules=6)
        plan.quiz_every_n_videos = 2
        plan.save(update_fields=["quiz_every_n_videos"])
        return plan, task

    def _save(self, task):
        return self.client.post(
            reverse("tasks:task_video_save", args=[task.pk]),
            data=json.dumps({"minutes": 10, "videos_watched": 2}), content_type="application/json",
        )

    def test_unexpected_error_while_generating_the_quiz_still_saves_the_video(self):
        from unittest import mock

        from . import api
        plan, task = self._plan_with_quiz()
        with mock.patch.object(api.ai, "generate_quiz", side_effect=ConnectionResetError("cortada")):
            with self.assertLogs("tasks.views", level="ERROR"):
                r = self._save(task)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(_watched(plan), 2)
        task.refresh_from_db()
        self.assertTrue(task.is_done)
        self.assertEqual(plan.quizzes.count(), 0)
        self.assertNotIn("test", r.json()["redirect_url"])

    def test_a_quiz_that_does_generate_still_redirects_to_it(self):
        from unittest import mock

        from . import api
        plan, task = self._plan_with_quiz()
        fake = {"questions": [{"question": "?", "options": ["a", "b", "c", "d"], "correct_index": 0}]}
        with mock.patch.object(api.ai, "generate_quiz", return_value=fake):
            r = self._save(task)
        quiz = plan.quizzes.get()
        self.assertEqual(r.json()["redirect_url"], reverse("tasks:quiz_take", args=[quiz.uuid]))

    def test_repeated_save_does_not_generate_a_second_quiz(self):
        from unittest import mock

        from . import api
        plan, task = self._plan_with_quiz()
        fake = {"questions": [{"question": "?", "options": ["a", "b", "c", "d"], "correct_index": 0}]}
        with mock.patch.object(api.ai, "generate_quiz", return_value=fake) as gen:
            self._save(task)
            self._save(task)
        self.assertEqual(gen.call_count, 1)
        self.assertEqual(plan.quizzes.count(), 1)


# ─────────────────────────────────────────────────────────────────────────────
# Cursos de idioma largos: el temario no se recorta a 50 vídeos
# ─────────────────────────────────────────────────────────────────────────────
from unittest import mock  # noqa: E402

from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from . import api as api_module  # noqa: E402
from .models import CoursePlaylist  # noqa: E402


def _long_youtube(total, calls=None):
    """YouTube de mentira con UNA playlist de `total` vídeos. Respeta
    `max_results` como la función real (que pagina hasta ese tope)."""
    def items(pid, max_results=50):
        if calls is not None:
            calls.append(max_results)
        return [{"video_id": f"L{i:010d}", "title": f"Vídeo {i}"} for i in range(total)][:max_results]

    def details(ids):
        return {
            v: {"title": f"Título {v}", "channel_title": "Canal", "duration_seconds": 300,
                "has_captions": True, "embeddable": True}
            for v in ids
        }

    return mock.patch.multiple("tasks.api", list_playlist_items=items, get_videos_details=details)


class _LongCatalogSetup:
    """Material común: un catálogo con UN curso largo (A1→B2) y atajos para
    crear el plan por la API de la app o por el formulario web."""

    FORM = {
        "name": "Mi francés", "plan_type": "study", "study_subtype": "language",
        "language_name": "Francés", "level_from": "A1", "level_to": "B2",
        "known_languages": ["español"], "language_daily_minutes": "30",
        "due_time": "20:00", "custom_days": ["0", "2", "4"], "weeks": "12", "is_active": "on",
    }
    DRAFT_REQUEST = {
        "language_name": "Francés", "level_from": "A1", "level_to": "B2", "known_languages": "español",
        "weeks": 12, "custom_days": [0, 2, 4], "language_daily_minutes": 30, "due_time": "20:00",
    }

    def setUp(self):
        # La migración que siembra cursos reales de francés también corre en
        # la BD de pruebas: se vacía el catálogo para que solo cuente este.
        CoursePlaylist.objects.all().delete()
        CoursePlaylist.objects.create(
            language="francés", level="A1", level_to="B2", native_language="español",
            youtube_playlist_id="PL_LARGO", title="Francés completo A1-B2", channel_title="Canal",
        )

    def _post_json(self, name, body):
        return self.client.post(reverse(name), data=json.dumps(body), content_type="application/json")

    def _api_save(self):
        draft = self._post_json("api:plan_language_draft", self.DRAFT_REQUEST).json()["draft"]
        return self._post_json("api:plan_language_save", {
            "selected": draft["selected"], "plan_fields": draft["plan_fields"],
            "due_time": "20:00", "name": "Mi francés", "notes": "", "reward": "",
        })



class LongCatalogCourseIsNotTruncatedTests(_LongCatalogSetup, TestCase):
    """El catálogo admite «un curso entero de A1 a B2 en una sola lista»
    (CoursePlaylist.level_to), que casi siempre pasa de 50 vídeos. Antes se
    quedaba en silencio con los 50 primeros: el plan decía A1→B2 y el curso
    acababa a mitad de A2."""

    def test_api_keeps_every_video_of_a_120_video_course_in_order(self):
        calls = []
        with _long_youtube(120, calls):
            r = self._api_save()
        self.assertEqual(r.status_code, 201, r.content)
        plan = Plan.objects.get()
        mods = list(plan.course_modules.order_by("order"))
        self.assertEqual(len(mods), 120)
        self.assertEqual([m.order for m in mods], list(range(120)))
        self.assertEqual(mods[0].youtube_video_id, "L0000000000")
        self.assertEqual(mods[-1].youtube_video_id, "L0000000119")
        self.assertTrue(all(m.plan_id == plan.pk for m in mods))
        self.assertEqual(r.json()["plan"]["course_progress"]["total"], 120)
        # se pide el tope entero a YouTube (la función real pagina hasta ahí)
        self.assertEqual(calls, [api_module.MAX_VIDEOS_PER_CATALOG_COURSE])

    def test_weeks_are_spread_over_the_whole_plan_without_overflowing(self):
        with _long_youtube(120):
            self._api_save()
        weeks = [m.scheduled_week for m in Plan.objects.get().course_modules.order_by("order")]
        self.assertEqual(weeks, sorted(weeks))
        self.assertEqual((min(weeks), max(weeks)), (1, 12))

    def test_a_playlist_over_the_cap_is_cut_at_the_cap_not_at_50(self):
        with _long_youtube(600):
            r = self._api_save()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(
            Plan.objects.get().course_modules.count(), api_module.MAX_VIDEOS_PER_CATALOG_COURSE,
        )

    def test_the_web_confirm_keeps_every_video_too(self):
        self.client.post(reverse("tasks:plan_create"), self.FORM)
        with _long_youtube(120):
            r = self.client.post(reverse("tasks:plan_language_confirm"), {"name": "Mi francés", "due_time": "21:00"})
        plan = Plan.objects.get()
        self.assertRedirects(r, reverse("tasks:plan_detail", args=[plan.pk]), fetch_redirect_response=False)
        self.assertEqual(plan.course_modules.count(), 120)
        # y el detalle de un curso tan largo se sigue viendo bien
        self.assertEqual(self.client.get(reverse("tasks:plan_detail", args=[plan.pk])).status_code, 200)

    def test_retry_for_an_empty_course_keeps_every_video_too(self):
        plan = Plan.objects.create(
            user=get_current_user(), name="Francés", plan_type=Plan.PLAN_TYPE_STUDY,
            study_subtype=Plan.STUDY_SUBTYPE_LANGUAGE, language_name="Francés", level_from="A1",
            level_to="B2", known_languages="español", language_daily_minutes=30, weeks=12,
            repeat="custom", custom_days="0,2,4", started_on=date.today(),
        )
        plan.sync_task()
        with _long_youtube(120):
            self.client.post(reverse("tasks:plan_language_retry", args=[plan.pk]))
        self.assertEqual(plan.course_modules.count(), 120)

    def test_the_syllabus_is_saved_in_a_handful_of_queries_not_one_per_video(self):
        plan = Plan.objects.create(
            user=get_current_user(), name="Francés", plan_type=Plan.PLAN_TYPE_STUDY,
            study_subtype=Plan.STUDY_SUBTYPE_LANGUAGE, language_name="Francés", weeks=12,
            repeat="daily", started_on=date.today(),
        )
        modules = [
            CourseModule(order=i, youtube_video_id=f"M{i:010d}", title=f"V{i}", duration_seconds=60)
            for i in range(300)
        ]
        with CaptureQueriesContext(connection) as ctx:
            api_module.save_course_modules(plan, modules)
        self.assertEqual(plan.course_modules.count(), 300)
        self.assertLess(len(ctx), 30, "un INSERT por vídeo sería ~300 consultas")


# ─────────────────────────────────────────────────────────────────────────────
# CSRF: la cookie es HttpOnly, así que ningún script web puede fiarse de ella
# ─────────────────────────────────────────────────────────────────────────────
import re  # noqa: E402
from pathlib import Path  # noqa: E402

from django.conf import settings  # noqa: E402
from django.test import Client  # noqa: E402
from django.utils import timezone  # noqa: E402

from .models import WarmupStatus, WorkoutSession  # noqa: E402


class WorkoutSaveWorksWithTheHttpOnlyCsrfCookieTests(TestCase):
    """settings.CSRF_COOKIE_HTTPONLY = True: JavaScript no puede leer la
    cookie `csrftoken`. workout.js la leía con document.cookie para guardar
    el entreno suelto, mandaba «null» y el servidor contestaba 403 — la
    sesión no se guardaba nunca. Ahora manda el token del formulario."""

    def setUp(self):
        self.user = get_current_user()
        WarmupStatus.objects.update_or_create(user=self.user, defaults={"last_warmup_at": timezone.now()})
        self.task = Task.objects.create(
            user=self.user, title="Dominadas", category=Task.CATEGORY_SPORT,
            subcategory=Task.SUBCATEGORY_UPPER_BODY, due_date=timezone.localdate(),
        )
        self.client = Client(enforce_csrf_checks=True)   # como un navegador de verdad
        self.page = self.client.get(reverse("tasks:task_workout", args=[self.task.pk]) + "?exercise=pullup")
        self.save_url = reverse("tasks:task_workout_save", args=[self.task.pk]) + "?exercise=pullup"
        self.payload = json.dumps({
            "total_reps": 5, "rep_durations": [1, 1, 1, 1, 1], "sets": [{"reps": 5}],
            "session_duration_seconds": 20,
        })

    def _token_in_page(self):
        m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', self.page.content.decode())
        self.assertIsNotNone(m, "la página del entreno tiene que llevar el token en el formulario")
        return m.group(1)

    def test_the_cookie_is_http_only_so_scripts_cannot_read_it(self):
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertTrue(self.client.cookies[settings.CSRF_COOKIE_NAME]["httponly"])

    def test_saving_with_the_token_from_the_form_works(self):
        r = self.client.post(
            self.save_url, data=self.payload, content_type="application/json",
            HTTP_X_CSRFTOKEN=self._token_in_page(),
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["ok"])
        # la sesión queda guardada y la tarea sigue al enfriamiento obligatorio
        self.assertEqual(WorkoutSession.objects.get(task=self.task).total_reps, 5)
        self.assertEqual(r.json()["redirect_url"], reverse("tasks:task_cooldown", args=[self.task.pk]))

    def test_what_the_old_script_sent_when_it_could_not_read_the_cookie_is_refused(self):
        r = self.client.post(
            self.save_url, data=self.payload, content_type="application/json", HTTP_X_CSRFTOKEN="null",
        )
        self.assertEqual(r.status_code, 403)

    def test_no_web_script_reads_the_csrf_token_from_the_cookie_alone(self):
        """Quien llame a getCookie("csrftoken") tiene que leer antes el token
        del formulario (csrfmiddlewaretoken) — o no valdrá con la cookie HttpOnly."""
        offenders = []
        for path in sorted((Path(settings.BASE_DIR) / "static" / "js").glob("*.js")):
            text = path.read_text(encoding="utf-8")
            if re.search(r'X-CSRFToken["\']?\s*:\s*getCookie\(', text):
                offenders.append(path.name)               # la cabecera sale SOLO de la cookie
            if "getCookie(" in text and "csrftoken" in text and "csrfmiddlewaretoken" not in text:
                offenders.append(path.name)
        self.assertEqual(sorted(set(offenders)), [])


class LanguagePlanAndSyllabusAreSavedTogetherTests(_LongCatalogSetup, TestCase):
    """Si algo falla al guardar el temario, no se queda un plan de idiomas
    vacío (ni, al reintentar, un segundo plan): o entra todo o no entra nada."""

    def test_api_failure_while_saving_the_syllabus_leaves_no_plan_behind(self):
        from django.db import DatabaseError
        client = Client(raise_request_exception=False)
        draft = client.post(
            reverse("api:plan_language_draft"), data=json.dumps(self.DRAFT_REQUEST),
            content_type="application/json",
        ).json()["draft"]
        with _long_youtube(30), mock.patch.object(
            CourseModule.objects, "bulk_create", side_effect=DatabaseError("database is locked"),
        ):
            r = client.post(reverse("api:plan_language_save"), data=json.dumps({
                "selected": draft["selected"], "plan_fields": draft["plan_fields"],
                "due_time": "20:00", "name": "Mi francés", "notes": "", "reward": "",
            }), content_type="application/json")
        self.assertEqual(r.status_code, 500)
        self.assertEqual((Plan.objects.count(), CourseModule.objects.count()), (0, 0))

    def test_web_failure_while_saving_the_syllabus_leaves_no_plan_behind(self):
        from django.db import DatabaseError
        client = Client(raise_request_exception=False)
        client.post(reverse("tasks:plan_create"), self.FORM)
        with _long_youtube(30), mock.patch.object(
            CourseModule.objects, "bulk_create", side_effect=DatabaseError("database is locked"),
        ):
            r = client.post(reverse("tasks:plan_language_confirm"), {"name": "Mi francés", "due_time": "21:00"})
        self.assertEqual(r.status_code, 500)
        self.assertEqual((Plan.objects.count(), CourseModule.objects.count()), (0, 0))
        # el borrador sigue en la sesión: se puede volver a confirmar sin rellenar nada
        with _long_youtube(30):
            r = client.post(reverse("tasks:plan_language_confirm"), {"name": "Mi francés", "due_time": "21:00"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Plan.objects.count(), 1)
        self.assertEqual(Plan.objects.get().course_modules.count(), 30)
