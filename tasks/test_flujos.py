"""
Flujos de Estudio / Lectura que ningún test ejecutaba (medido con coverage):
el temporizador web de Lectura, el guardado de vídeo de la web frente al de
la app, el progreso de los cursos de Udemy y los planes cerrados.

Cada clase dice qué prometía la app. Lo importante: lo que se hace por la web
y por la API del móvil tiene que dejar EXACTAMENTE el mismo estado.
"""
import json
from datetime import date

from django.test import TestCase
from django.urls import reverse

from .models import CourseModule, Occurrence, Plan, PlanItem, Task, TimerSession
from .utils import get_current_user


def _post_json(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


class WebFocusTimerTests(TestCase):
    """Temporizador web de Lectura / General con cronómetro (task_focus y
    task_focus_save): jamás se había ejecutado en un test."""

    def _reading(self, **kw):
        base = dict(
            title="Leer", category=Task.CATEGORY_WORK, subcategory=Task.SUBCATEGORY_READING,
            due_date=date.today(), repeat=Task.REPEAT_DAILY, user=get_current_user(),
        )
        base.update(kw)
        return Task.objects.create(**base)

    def _save(self, task, minutes):
        return _post_json(self.client, reverse("tasks:task_focus_save", args=[task.pk]), {"minutes": minutes})

    def test_page_shows_goal_and_marks_the_task_started(self):
        t = self._reading(target_minutes=30)
        r = self.client.get(reverse("tasks:task_focus", args=[t.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Objetivo: 30 min")
        self.assertContains(r, "lectura")
        t.refresh_from_db()
        self.assertIsNotNone(t.started_at)

    def test_page_without_goal_says_free_session(self):
        t = self._reading()
        r = self.client.get(reverse("tasks:task_focus", args=[t.pk]))
        self.assertContains(r, "Sesión libre, sin objetivo")

    def test_general_task_with_timer_uses_the_same_page(self):
        t = Task.objects.create(
            title="Estirar", category=Task.CATEGORY_GENERAL, wants_timer=True, target_minutes=10,
            due_date=date.today(), user=get_current_user(),
        )
        r = self.client.get(reverse("tasks:task_focus", args=[t.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "cronómetro")

    def test_short_session_is_saved_and_the_task_stays_pending(self):
        t = self._reading(target_minutes=30)
        r = self._save(t, 10)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["ok"])
        ts = TimerSession.objects.get(task=t)
        self.assertEqual((ts.minutes, ts.target_minutes, ts.source, ts.subcategory),
                         (10, 30, TimerSession.SOURCE_MANUAL, "reading"))
        t.refresh_from_db()
        self.assertFalse(t.is_done)
        self.assertEqual(Occurrence.objects.count(), 0)

    def test_reaching_the_goal_closes_the_day_and_spawns_tomorrow(self):
        t = self._reading(target_minutes=30)
        self._save(t, 30)
        t.refresh_from_db()
        self.assertTrue(t.is_done)
        self.assertEqual(Occurrence.objects.filter(series_id=t.series_id, result="done").count(), 1)
        self.assertEqual(Task.objects.filter(series_id=t.series_id, is_done=False).count(), 1)

    def test_free_session_closes_the_day(self):
        t = self._reading()
        self._save(t, 5)
        t.refresh_from_db()
        self.assertTrue(t.is_done)

    def test_invalid_body_is_a_clean_400(self):
        t = self._reading(target_minutes=30)
        r = self.client.post(reverse("tasks:task_focus_save", args=[t.pk]), data="no es json", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_garbage_minutes_do_not_crash_the_server(self):
        self.client.raise_request_exception = False
        t = self._reading(target_minutes=30)
        for bad in ("abc", None, [], {}):
            r = self._save(t, bad)
            self.assertLess(r.status_code, 500, f"minutes={bad!r} → {r.status_code}")
        self.assertEqual(TimerSession.objects.count(), 0)

    def test_body_that_is_not_an_object_does_not_crash_either(self):
        self.client.raise_request_exception = False
        t = self._reading(target_minutes=30)
        for body in ([], 5, "x", None):
            r = _post_json(self.client, reverse("tasks:task_focus_save", args=[t.pk]), body)
            self.assertLess(r.status_code, 500, f"body={body!r} → {r.status_code}")

    def test_web_and_app_leave_the_same_state(self):
        outcomes = {}
        for channel in ("web", "api"):
            Task.all_objects.all().delete()
            Occurrence.objects.all().delete()
            TimerSession.objects.all().delete()
            t = self._reading(target_minutes=30)
            for minutes in (10, 30):
                if channel == "web":
                    self._save(t, minutes)
                else:
                    _post_json(self.client, reverse("api:focus_save", args=[t.uuid]), {"minutes": minutes})
            outcomes[channel] = (
                sorted((x.is_done, str(x.due_date)) for x in Task.objects.all()),
                sorted((o.result, o.pct) for o in Occurrence.objects.all()),
                sorted((s.minutes, s.target_minutes, s.source) for s in TimerSession.objects.all()),
            )
        self.assertEqual(outcomes["web"], outcomes["api"])


class AppFocusTimerRobustnessTests(TestCase):
    """api.focus_save con basura en `minutes` o en el cuerpo."""

    def test_garbage_is_a_400_not_a_500(self):
        self.client.raise_request_exception = False
        t = Task.objects.create(
            title="Leer", category=Task.CATEGORY_WORK, subcategory=Task.SUBCATEGORY_READING,
            due_date=date.today(), target_minutes=30, user=get_current_user(),
        )
        for bad in ("abc", None, [], {}):
            r = _post_json(self.client, reverse("api:focus_save", args=[t.uuid]), {"minutes": bad})
            self.assertLess(r.status_code, 500, f"minutes={bad!r} → {r.status_code}")
        for body in ([], 5, "x"):
            r = _post_json(self.client, reverse("api:focus_save", args=[t.uuid]), body)
            self.assertLess(r.status_code, 500, f"body={body!r} → {r.status_code}")
        self.assertEqual(TimerSession.objects.count(), 0)


class VideoSaveWebVsApiTests(TestCase):
    """El guardado de un vídeo visto por la web (views.task_video_save) y por
    la app (api.video_save) tienen que dejar el MISMO estado."""

    def _save(self, channel, task, **body):
        if channel == "web":
            return _post_json(self.client, reverse("tasks:task_video_save", args=[task.pk]), body)
        return _post_json(self.client, reverse("api:video_save", args=[task.uuid]), body)

    def _wipe(self):
        Task.all_objects.all().delete()
        Occurrence.objects.all().delete()
        Plan.objects.all().delete()

    def _state(self):
        return {
            "tasks": sorted(
                (t.title, str(t.due_date), t.is_done, t.repeat,
                 -1 if t.playlist_start_index is None else t.playlist_start_index,
                 bool(t.course_completed_at))
                for t in Task.objects.all()
            ),
            "occurrences": sorted(
                (o.title, str(o.due_date), o.result, -1 if o.minutes_watched is None else o.minutes_watched, o.pct)
                for o in Occurrence.objects.all()
            ),
            "modules": sorted((m.order, m.watched_at is not None) for m in CourseModule.objects.all()),
            "plans": sorted((p.name, p.closed_at is not None) for p in Plan.objects.all()),
        }

    def _both(self, build, act):
        """build() monta el escenario y devuelve la tarea; act(channel, task)
        hace lo que haría el usuario. Devuelve el estado común."""
        states = {}
        for channel in ("web", "api"):
            self._wipe()
            task = build()
            resp = act(channel, task)
            self.assertEqual(resp.status_code, 200, (channel, resp.content))
            states[channel] = self._state()
        self.assertEqual(states["web"], states["api"], "la web y la app dejan estados distintos")
        return states["web"]

    def _study(self, **kw):
        base = dict(
            title="Estudio", category=Task.CATEGORY_STUDY, due_date=date.today(),
            repeat=Task.REPEAT_DAILY, user=get_current_user(),
        )
        base.update(kw)
        return Task.objects.create(**base)

    def test_single_video_closes_the_series(self):
        state = self._both(
            lambda: self._study(youtube_video_id="dQw4w9WgXcQ"),
            lambda ch, t: self._save(ch, t, minutes=5, videos_watched=1),
        )
        self.assertEqual(len(state["tasks"]), 1)
        self.assertEqual(state["tasks"][0][2:4], (True, Task.REPEAT_NONE))

    def test_playlist_advances_by_the_videos_watched(self):
        def build():
            t = self._study(youtube_playlist_id="PLabcdefghijklmnop", target_video_count=2)
            t.playlist_videos_cache = [{"video_id": f"v{i:010d}"} for i in range(6)]
            t.save()
            return t

        state = self._both(build, lambda ch, t: self._save(ch, t, videos_watched=2))
        self.assertIn(2, [x[4] for x in state["tasks"]], state["tasks"])

    def test_playlist_closes_on_its_last_video(self):
        def build():
            t = self._study(youtube_playlist_id="PLabcdefghijklmnop", target_video_count=2)
            t.playlist_videos_cache = [{"video_id": f"v{i:010d}"} for i in range(4)]
            t.playlist_start_index = 2
            t.save()
            return t

        state = self._both(build, lambda ch, t: self._save(ch, t, videos_watched=2))
        self.assertEqual(len(state["tasks"]), 1)
        self.assertEqual(state["tasks"][0][3], Task.REPEAT_NONE)

    def _language_plan(self, modules=5, daily=30):
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
        return Task.objects.get(series_id=plan.task_series_id)

    def test_language_course_advances_three_modules(self):
        state = self._both(
            lambda: self._language_plan(),
            lambda ch, t: self._save(ch, t, minutes=15, videos_watched=3),
        )
        self.assertEqual([w for _, w in state["modules"]].count(True), 3)

    def test_language_course_finishing_closes_the_plan(self):
        state = self._both(
            lambda: self._language_plan(modules=2),
            lambda ch, t: self._save(ch, t, minutes=10, videos_watched=2),
        )
        self.assertEqual(state["plans"], [("Alemán", True)])

    def test_language_course_zero_videos_does_not_advance(self):
        state = self._both(
            lambda: self._language_plan(),
            lambda ch, t: self._save(ch, t, minutes=10, videos_watched=0),
        )
        self.assertEqual([w for _, w in state["modules"]].count(True), 0)

    def test_language_course_without_counters_advances_one(self):
        state = self._both(
            lambda: self._language_plan(),
            lambda ch, t: self._save(ch, t),
        )
        self.assertEqual([w for _, w in state["modules"]].count(True), 1)

    def test_study_plan_item_with_a_video_records_the_minutes(self):
        def build():
            plan = Plan.objects.create(
                user=get_current_user(), name="Estudiar", plan_type=Plan.PLAN_TYPE_STUDY,
                repeat="daily", started_on=date.today(), weeks=4,
            )
            PlanItem.objects.create(
                plan=plan, label="Curso", progression=PlanItem.PROG_COMPLETION,
                youtube_video_id="dQw4w9WgXcQ", target_minutes=20,
            )
            plan.sync_task()
            return Task.objects.get(series_id=plan.task_series_id)

        state = self._both(build, lambda ch, t: self._save(ch, t, minutes=22, videos_watched=1))
        done = [o for o in state["occurrences"] if o[2] == "done"]
        self.assertEqual(len(done), 1)
        self.assertEqual(done[0][3], 22)

    def test_sport_video_is_not_closed_here(self):
        def build():
            return Task.objects.create(
                title="Rutina", category=Task.CATEGORY_SPORT, youtube_video_id="dQw4w9WgXcQ",
                due_date=date.today(), user=get_current_user(),
            )

        state = self._both(build, lambda ch, t: self._save(ch, t, minutes=20))
        self.assertFalse(state["tasks"][0][2])
        self.assertEqual(state["occurrences"], [])

    def test_garbage_body_is_tolerated_on_the_web(self):
        t = self._study(youtube_video_id="dQw4w9WgXcQ")
        r = self.client.post(reverse("tasks:task_video_save", args=[t.pk]), data="x", content_type="application/json")
        self.assertEqual(r.status_code, 200)


class VideoPageRendersTests(TestCase):
    """task_video (GET) nunca se había renderizado en un test."""

    def test_single_video_page(self):
        t = Task.objects.create(
            title="Vídeo", category=Task.CATEGORY_STUDY, youtube_video_id="dQw4w9WgXcQ",
            due_date=date.today(), user=get_current_user(),
        )
        r = self.client.get(reverse("tasks:task_video", args=[t.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "dQw4w9WgXcQ")

    def test_playlist_page_with_cache(self):
        t = Task.objects.create(
            title="Lista", category=Task.CATEGORY_STUDY, youtube_playlist_id="PLabcdefghijklmnop",
            due_date=date.today(), user=get_current_user(),
            playlist_videos_cache=[{"video_id": "aaaaaaaaaaa", "duration_seconds": 100}],
        )
        r = self.client.get(reverse("tasks:task_video", args=[t.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "aaaaaaaaaaa")

    def test_language_course_page_carries_the_queue(self):
        plan = Plan.objects.create(
            user=get_current_user(), name="Alemán", plan_type=Plan.PLAN_TYPE_STUDY,
            study_subtype=Plan.STUDY_SUBTYPE_LANGUAGE, language_name="Alemán", level_from="A1",
            level_to="A2", language_daily_minutes=30, weeks=8, repeat="daily", started_on=date.today(),
        )
        for i in range(3):
            CourseModule.objects.create(plan=plan, order=i, level="A1", youtube_video_id=f"vid{i:08d}",
                                        title=f"Vídeo {i}", duration_seconds=300)
        plan.sync_task()
        t = Task.objects.get(series_id=plan.task_series_id)
        r = self.client.get(reverse("tasks:task_video", args=[t.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "vid00000001")


class CourseProgressTests(TestCase):
    """La barra «cuánto llevas del curso» de Udemy: la extensión manda el %
    y las fracciones (course_progress_save y plan_item_course_progress_save)."""

    def _udemy(self, **kw):
        base = dict(
            title="Excel", category=Task.CATEGORY_STUDY, subcategory=Task.SUBCATEGORY_UDEMY,
            target_minutes=30, due_date=date.today(), repeat=Task.REPEAT_DAILY, user=get_current_user(),
        )
        base.update(kw)
        return Task.objects.create(**base)

    def _post(self, t, body):
        return _post_json(self.client, reverse("api:course_progress_save", args=[t.uuid]), body)

    def test_records_percentage_and_fractions(self):
        t = self._udemy()
        r = self._post(t, {"pct": 41.6, "done": 5, "total": 12})
        self.assertEqual(r.status_code, 200, r.content)
        t.refresh_from_db()
        self.assertEqual((t.course_progress_pct, t.course_lessons_done, t.course_lessons_total), (42, 5, 12))

    def test_percentage_is_clamped_to_0_100(self):
        t = self._udemy()
        self._post(t, {"pct": 180})
        t.refresh_from_db()
        self.assertEqual(t.course_progress_pct, 100)
        self._post(t, {"pct": -5})
        t.refresh_from_db()
        self.assertEqual(t.course_progress_pct, 0)

    def test_done_never_exceeds_total(self):
        t = self._udemy()
        self._post(t, {"pct": 100, "done": 30, "total": 12})
        t.refresh_from_db()
        self.assertEqual((t.course_lessons_done, t.course_lessons_total), (12, 12))

    def test_garbage_percentage_changes_nothing_and_is_not_an_error(self):
        t = self._udemy(course_progress_pct=30)
        for bad in ("abc", None, True, [], {}):
            r = self._post(t, {"pct": bad})
            self.assertEqual(r.status_code, 200, (bad, r.content))
        t.refresh_from_db()
        self.assertEqual(t.course_progress_pct, 30)

    def test_progress_survives_into_tomorrows_task(self):
        t = self._udemy()
        self._post(t, {"pct": 55, "done": 11, "total": 20})
        t.refresh_from_db()
        t.mark_done()
        nxt = Task.objects.exclude(pk=t.pk).get(series_id=t.series_id)
        self.assertEqual((nxt.course_progress_pct, nxt.course_lessons_done, nxt.course_lessons_total), (55, 11, 20))

    def test_unknown_task_is_a_clean_404(self):
        import uuid as uuid_mod
        r = _post_json(self.client, reverse("api:course_progress_save", args=[uuid_mod.uuid4()]), {"pct": 5})
        self.assertEqual(r.status_code, 404)

    # ------------------------------------------------ objetivo de un plan

    def _plan_item(self):
        plan = Plan.objects.create(
            user=get_current_user(), name="Cursos", plan_type=Plan.PLAN_TYPE_STUDY,
            repeat="daily", started_on=date.today(), weeks=4,
        )
        item = PlanItem.objects.create(
            plan=plan, label="Excel", progression=PlanItem.PROG_COMPLETION,
            watch_keyword="Excel", target_minutes=30,
        )
        return plan, item

    def test_plan_item_stores_the_progress_and_shows_it(self):
        plan, item = self._plan_item()
        self.assertIsNone(item.current_course_progress_pct())
        self.assertEqual(item.display_target_text(), "sigue el curso de Udemy")
        r = _post_json(self.client, reverse("api:plan_item_course_progress_save", args=[item.pk]),
                       {"pct": 64, "done": 16, "total": 25})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["pct"], 64)
        item.refresh_from_db()
        self.assertEqual(item.current_course_progress_pct(), 64)
        self.assertEqual(item.course_progress()["left"], 9)
        self.assertEqual(item.display_target_text(), "64% del curso completado")

    def test_plan_item_garbage_percentage_keeps_the_old_value(self):
        plan, item = self._plan_item()
        item.record_course_progress(40)
        r = _post_json(self.client, reverse("api:plan_item_course_progress_save", args=[item.pk]), {"pct": "mucho"})
        self.assertEqual(r.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.course_progress_pct, 40)

    def test_item_of_a_deleted_plan_is_a_404(self):
        from django.utils import timezone
        plan, item = self._plan_item()
        plan.deleted_at = timezone.now()
        plan.save()
        r = _post_json(self.client, reverse("api:plan_item_course_progress_save", args=[item.pk]), {"pct": 10})
        self.assertEqual(r.status_code, 404)

    def test_udemy_courses_list_for_the_extension(self):
        plan, item = self._plan_item()
        r = self.client.get(reverse("api:plan_udemy_courses"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual([c["item_id"] for c in r.json()["courses"]], [item.pk])
        # un plan cerrado deja de aparecer
        from django.utils import timezone
        plan.closed_at = timezone.now()
        plan.save()
        self.assertEqual(self.client.get(reverse("api:plan_udemy_courses")).json()["courses"], [])


# ─────────────────────────────────────────────────────────────────────────────
# Planes de Estudio · Idiomas (catálogo → borrador → confirmar → curso)
# ─────────────────────────────────────────────────────────────────────────────
from unittest import mock  # noqa: E402

from .models import CoursePlaylist, CourseQuiz  # noqa: E402
from .youtube_search import YouTubeSearchError  # noqa: E402


def _fake_youtube(n_videos=4, embeddable=True):
    """YouTube de mentira: cada playlist «PL_X» da n vídeos «X000000000i»."""
    def items(pid, max_results=50):
        return [{"video_id": f"{pid[-1]}{i:010d}", "title": f"{pid} vídeo {i}"} for i in range(n_videos)]

    def details(ids):
        return {
            v: {"title": f"Título {v}", "channel_title": "Canal", "duration_seconds": 600,
                "has_captions": True, "embeddable": embeddable}
            for v in ids
        }

    return mock.patch.multiple("tasks.api", list_playlist_items=items, get_videos_details=details)


class _CatalogMixin:
    def _catalog(self):
        # La migración 0025 siembra cursos reales de francés en la BD de
        # pruebas: se vacía el catálogo para que solo cuenten estos.
        CoursePlaylist.objects.all().delete()
        mk = CoursePlaylist.objects.create
        self.fr_a = mk(language="francés", level="A1", level_to="A2", native_language="español",
                       youtube_playlist_id="PL_A", title="Francés A1-A2", channel_title="Canal A", order=1)
        self.fr_b = mk(language="francés", level="B1", native_language="",
                       youtube_playlist_id="PL_B", title="Francés B1", channel_title="Canal B", order=1)
        self.fr_en = mk(language="francés", level="A1", native_language="inglés",
                        youtube_playlist_id="PL_E", title="French for English speakers", order=2)
        self.de = mk(language="alemán", level="A1", native_language="español",
                     youtube_playlist_id="PL_D", title="Alemán A1", order=1)
        self.fr_off = mk(language="francés", level="C1", native_language="español",
                         youtube_playlist_id="PL_O", title="Inactivo", is_active=False, order=1)


class LanguagePlanApiTests(_CatalogMixin, TestCase):
    """Crear un curso de idioma desde la app móvil: opciones → borrador → guardar."""

    DRAFT_REQUEST = {
        "language_name": "Francés", "level_from": "A1", "level_to": "B1", "known_languages": "español",
        "weeks": 8, "custom_days": [0, 2, 4], "language_daily_minutes": 30, "due_time": "20:00",
    }

    def setUp(self):
        self._catalog()

    def _draft(self, **over):
        body = dict(self.DRAFT_REQUEST, **over)
        return _post_json(self.client, reverse("api:plan_language_draft"), body)

    def test_options_list_only_active_languages_once(self):
        r = self.client.get(reverse("api:plan_language_options"))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["languages"], ["alemán", "francés"])
        self.assertEqual(data["native_languages"], ["español", "inglés"])
        self.assertIn("A1", [l["value"] for l in data["cefr_levels"]])

    def test_draft_picks_matching_courses_only(self):
        r = self._draft()
        self.assertEqual(r.status_code, 200, r.content)
        draft = r.json()["draft"]
        picked = sorted(s["youtube_playlist_id"] for s in draft["selected"])
        # A (español) y B (neutro): sí. E es para anglohablantes, D es otro idioma, O está inactivo.
        self.assertEqual(picked, ["PL_A", "PL_B"])
        self.assertEqual(draft["missing_levels"], [])
        self.assertEqual(sum(s["weeks_allocated"] for s in draft["selected"]), 8)
        self.assertEqual(draft["plan_fields"]["study_subtype"], "language")
        self.assertEqual(Plan.objects.count(), 0, "un borrador no guarda nada")

    def test_draft_reports_levels_without_a_course(self):
        r = self._draft(level_to="B2")
        self.assertEqual(r.json()["draft"]["missing_levels"], ["B2"])

    def test_native_language_filter_follows_what_the_user_knows(self):
        r = self._draft(known_languages="inglés", level_to="A2")
        picked = sorted(s["youtube_playlist_id"] for s in r.json()["draft"]["selected"])
        self.assertEqual(picked, ["PL_E"])

    def test_accents_and_extra_words_do_not_hide_a_course(self):
        r = self._draft(language_name="curso de FRANCES", known_languages="Español e inglés")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["draft"]["selected"])

    def test_draft_needs_language_and_known_languages(self):
        self.assertEqual(self._draft(language_name="").status_code, 400)
        self.assertEqual(self._draft(known_languages="").status_code, 400)

    def test_draft_without_catalog_for_that_language_is_a_clean_400(self):
        r = self._draft(language_name="Klingon")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Todavía no hay ningún curso", r.json()["error"])

    def test_garbage_weeks_and_days_fall_back_to_defaults(self):
        r = self._draft(weeks="mucho", custom_days=["x", 9, None])
        self.assertEqual(r.status_code, 200, r.content)
        fields = r.json()["draft"]["plan_fields"]
        self.assertEqual(fields["weeks"], 12)
        self.assertEqual(fields["custom_days"], [0, 2, 4])

    def _save(self, draft, **over):
        body = {
            "selected": draft["selected"], "plan_fields": draft["plan_fields"],
            "due_time": "20:00", "name": "Mi francés", "notes": "", "reward": "una cena",
        }
        body.update(over)
        return _post_json(self.client, reverse("api:plan_language_save"), body)

    def test_save_creates_the_plan_modules_and_daily_task(self):
        draft = self._draft().json()["draft"]
        with _fake_youtube(n_videos=4):
            r = self._save(draft)
        self.assertEqual(r.status_code, 201, r.content)
        plan = Plan.objects.get()
        self.assertEqual((plan.name, plan.study_subtype, plan.language_name, plan.reward),
                         ("Mi francés", "language", "Francés", "una cena"))
        self.assertEqual(plan.language_daily_minutes, 30)
        mods = list(plan.course_modules.order_by("order"))
        self.assertEqual(len(mods), 8)                       # 2 cursos x 4 vídeos
        self.assertEqual([m.order for m in mods], list(range(8)))
        self.assertEqual(mods[0].level, "A1")
        self.assertEqual(mods[-1].level, "B1")
        weeks = [m.scheduled_week for m in mods]
        self.assertEqual(weeks, sorted(weeks))               # el temario va en orden de semanas
        self.assertGreaterEqual(min(weeks), 1)
        self.assertLessEqual(max(weeks), 8)
        task = Task.objects.get(series_id=plan.task_series_id)
        self.assertEqual((task.youtube_video_id, task.target_minutes, task.level),
                         (mods[0].youtube_video_id, 30, "A1"))
        body = r.json()["plan"]
        self.assertEqual(body["study_subtype"], "language")
        self.assertEqual(body["course_progress"]["total"], 8)

    def test_save_without_a_time_is_refused(self):
        draft = self._draft().json()["draft"]
        with _fake_youtube():
            r = self._save(draft, due_time="")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Plan.objects.count(), 0)

    def test_save_is_all_or_nothing_when_youtube_fails(self):
        draft = self._draft().json()["draft"]
        with mock.patch("tasks.api.list_playlist_items", side_effect=YouTubeSearchError("sin cuota")):
            r = self._save(draft)
        self.assertEqual(r.status_code, 400)
        self.assertIn("sin cuota", r.json()["error"])
        self.assertEqual((Plan.objects.count(), CourseModule.objects.count()), (0, 0))

    def test_save_with_nothing_embeddable_is_refused(self):
        draft = self._draft().json()["draft"]
        with _fake_youtube(embeddable=False):
            r = self._save(draft)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Plan.objects.count(), 0)

    def test_save_with_a_course_removed_from_the_catalog_is_refused(self):
        draft = self._draft().json()["draft"]
        CoursePlaylist.objects.filter(pk=draft["selected"][0]["catalog_id"]).delete()
        with _fake_youtube():
            r = self._save(draft)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Plan.objects.count(), 0)

    def test_the_new_course_is_listed_and_its_detail_opens(self):
        draft = self._draft().json()["draft"]
        with _fake_youtube():
            plan_uuid = self._save(draft).json()["plan"]["uuid"]
        listed = self.client.get(reverse("api:plan_list")).json()["plans"]
        self.assertEqual([p["uuid"] for p in listed], [plan_uuid])
        detail = self.client.get(reverse("api:plan_detail", args=[plan_uuid])).json()["plan"]
        self.assertEqual(detail["course_progress"]["watched"], 0)
        self.assertEqual(detail["language_daily_minutes"], 30)


class LanguagePlanWebTests(_CatalogMixin, TestCase):
    """El mismo curso de idioma creado desde la web (formulario → revisar → confirmar)."""

    FORM = {
        "name": "Mi francés", "plan_type": "study", "study_subtype": "language",
        "language_name": "Francés", "level_from": "A1", "level_to": "B1",
        "known_languages": ["español"], "language_daily_minutes": "30", "quiz_every_n_videos": "3",
        "due_time": "20:00", "custom_days": ["0", "2", "4"], "weeks": "8", "is_active": "on",
    }

    def setUp(self):
        self._catalog()

    def test_full_flow(self):
        r = self.client.post(reverse("tasks:plan_create"), self.FORM)
        self.assertRedirects(r, reverse("tasks:plan_language_confirm"), fetch_redirect_response=False)
        self.assertEqual(Plan.objects.count(), 0, "hasta confirmar no se guarda nada")

        page = self.client.get(reverse("tasks:plan_language_confirm"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Francés A1-A2")
        self.assertContains(page, "Francés B1")
        self.assertNotContains(page, "French for English speakers")

        with _fake_youtube(n_videos=3):
            r = self.client.post(reverse("tasks:plan_language_confirm"), {"name": "Mi francés", "due_time": "21:30"})
        plan = Plan.objects.get()
        self.assertRedirects(r, reverse("tasks:plan_detail", args=[plan.pk]), fetch_redirect_response=False)
        self.assertEqual(plan.course_modules.count(), 6)
        self.assertEqual((plan.quiz_every_n_videos, plan.language_daily_minutes), (3, 30))
        self.assertEqual(plan.due_time.strftime("%H:%M"), "21:30")
        task = Task.objects.get(series_id=plan.task_series_id)
        self.assertEqual(task.due_time.strftime("%H:%M"), "21:30")
        # el borrador de la sesión se consume
        self.assertEqual(self.client.get(reverse("tasks:plan_language_confirm")).status_code, 302)
        # y el detalle del plan se ve
        self.assertEqual(self.client.get(reverse("tasks:plan_detail", args=[plan.pk])).status_code, 200)

    def test_missing_known_language_or_minutes_stays_on_the_form(self):
        for missing in ("known_languages", "language_daily_minutes"):
            form = dict(self.FORM)
            form.pop(missing)
            r = self.client.post(reverse("tasks:plan_create"), form)
            self.assertEqual(r.status_code, 200, missing)
            self.assertEqual(Plan.objects.count(), 0)

    def test_confirm_without_a_draft_goes_back_to_the_form(self):
        r = self.client.get(reverse("tasks:plan_language_confirm"))
        self.assertRedirects(r, reverse("tasks:plan_create"), fetch_redirect_response=False)

    def test_confirm_survives_a_youtube_failure_without_saving(self):
        self.client.post(reverse("tasks:plan_create"), self.FORM)
        with mock.patch("tasks.api.list_playlist_items", side_effect=YouTubeSearchError("sin red")):
            r = self.client.post(reverse("tasks:plan_language_confirm"), {"due_time": "20:00"})
        self.assertRedirects(r, reverse("tasks:plan_create"), fetch_redirect_response=False)
        self.assertEqual((Plan.objects.count(), CourseModule.objects.count()), (0, 0))

    def test_language_without_catalog_shows_an_error_and_saves_nothing(self):
        r = self.client.post(reverse("tasks:plan_create"), dict(self.FORM, language_name="Klingon"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Plan.objects.count(), 0)

    def _empty_language_plan(self):
        plan = Plan.objects.create(
            user=get_current_user(), name="Francés", plan_type=Plan.PLAN_TYPE_STUDY,
            study_subtype=Plan.STUDY_SUBTYPE_LANGUAGE, language_name="Francés", level_from="A1",
            level_to="B1", known_languages="español", language_daily_minutes=30, weeks=8,
            repeat="custom", custom_days="0,2,4", started_on=date.today(),
        )
        plan.sync_task()
        return plan

    def test_retry_fills_a_course_that_ended_up_without_videos(self):
        plan = self._empty_language_plan()
        with _fake_youtube(n_videos=2):
            r = self.client.post(reverse("tasks:plan_language_retry", args=[plan.pk]))
        self.assertRedirects(r, reverse("tasks:plan_detail", args=[plan.pk]), fetch_redirect_response=False)
        self.assertEqual(plan.course_modules.count(), 4)
        task = Task.objects.get(series_id=plan.task_series_id)
        self.assertEqual(task.youtube_video_id, plan.course_modules.order_by("order").first().youtube_video_id)

    def test_retry_does_not_duplicate_an_existing_syllabus(self):
        plan = self._empty_language_plan()
        with _fake_youtube(n_videos=2):
            self.client.post(reverse("tasks:plan_language_retry", args=[plan.pk]))
            self.client.post(reverse("tasks:plan_language_retry", args=[plan.pk]))
        self.assertEqual(plan.course_modules.count(), 4)

    def test_retry_on_a_non_language_plan_is_harmless(self):
        plan = Plan.objects.create(user=get_current_user(), name="Estudiar", plan_type=Plan.PLAN_TYPE_STUDY,
                                   repeat="daily", started_on=date.today())
        r = self.client.post(reverse("tasks:plan_language_retry", args=[plan.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(CourseModule.objects.count(), 0)


class CourseQuizWebTests(TestCase):
    """El test de repaso de un curso de idiomas (quiz_take / quiz_result)."""

    def setUp(self):
        self.plan = Plan.objects.create(
            user=get_current_user(), name="Alemán", plan_type=Plan.PLAN_TYPE_STUDY,
            study_subtype=Plan.STUDY_SUBTYPE_LANGUAGE, language_name="Alemán", level_from="A1",
            level_to="A2", language_daily_minutes=30, weeks=8, repeat="daily", started_on=date.today(),
        )
        self.quiz = CourseQuiz.objects.create(
            plan=self.plan, up_to_order=2, topics=["Saludos"], total=2,
            questions=[
                {"question": "¿Hola?", "options": ["Hallo", "Tschüss", "Danke", "Bitte"], "correct_index": 0},
                {"question": "¿Adiós?", "options": ["Hallo", "Tschüss", "Danke", "Bitte"], "correct_index": 1},
            ],
        )

    def test_take_page_lists_the_questions(self):
        r = self.client.get(reverse("tasks:quiz_take", args=[self.quiz.uuid]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "¿Hola?")
        self.assertContains(r, "Tschüss")

    def test_result_before_answering_sends_you_to_the_test(self):
        r = self.client.get(reverse("tasks:quiz_result", args=[self.quiz.uuid]))
        self.assertRedirects(r, reverse("tasks:quiz_take", args=[self.quiz.uuid]), fetch_redirect_response=False)

    def test_answering_scores_and_shows_the_review(self):
        r = self.client.post(reverse("tasks:quiz_take", args=[self.quiz.uuid]), {"q0": "0", "q1": "1"})
        self.assertRedirects(r, reverse("tasks:quiz_result", args=[self.quiz.uuid]), fetch_redirect_response=False)
        self.quiz.refresh_from_db()
        self.assertEqual((self.quiz.score, self.quiz.total, self.quiz.passed), (2, 2, True))
        page = self.client.get(reverse("tasks:quiz_result", args=[self.quiz.uuid]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "¿Adiós?")

    def test_a_half_answered_test_just_scores_lower(self):
        self.client.post(reverse("tasks:quiz_take", args=[self.quiz.uuid]), {"q0": "0"})
        self.quiz.refresh_from_db()
        self.assertEqual((self.quiz.score, self.quiz.passed), (1, False))

    def test_garbage_answers_count_as_wrong_not_as_a_crash(self):
        r = self.client.post(reverse("tasks:quiz_take", args=[self.quiz.uuid]), {"q0": "x", "q1": ""})
        self.assertEqual(r.status_code, 302)
        self.quiz.refresh_from_db()
        self.assertEqual(self.quiz.score, 0)

    def test_an_answered_test_cannot_be_answered_twice(self):
        self.client.post(reverse("tasks:quiz_take", args=[self.quiz.uuid]), {"q0": "0", "q1": "1"})
        self.client.post(reverse("tasks:quiz_take", args=[self.quiz.uuid]), {"q0": "3", "q1": "3"})
        self.quiz.refresh_from_db()
        self.assertEqual(self.quiz.score, 2)

    def test_streak_counts_passed_tests_in_a_row(self):
        self.quiz.answer([0, 1])
        second = CourseQuiz.objects.create(plan=self.plan, up_to_order=5, total=1,
                                           questions=[{"question": "?", "options": ["a", "b"], "correct_index": 0}])
        second.answer([1])
        self.assertEqual(self.plan.quiz_streak_stats(), {"current_streak": 0, "max_streak": 1})
        third = CourseQuiz.objects.create(plan=self.plan, up_to_order=8, total=1,
                                          questions=[{"question": "?", "options": ["a", "b"], "correct_index": 0}])
        third.answer([0])
        self.assertEqual(self.plan.quiz_streak_stats(), {"current_streak": 1, "max_streak": 1})


# ─────────────────────────────────────────────────────────────────────────────
# Plan de Estudio · Hábito simple (formulario web): validar ANTES de guardar
# ─────────────────────────────────────────────────────────────────────────────
def _fake_playlist(n=5):
    """YouTube de mentira para PlanItem.sync_playlist_videos()."""
    def items(pid, max_results=50):
        return [{"video_id": f"v{i:010d}"} for i in range(n)]

    def details(ids):
        return {v: {"duration_seconds": 300, "embeddable": True} for v in ids}

    return mock.patch.multiple("tasks.youtube_search", list_playlist_items=items, get_videos_details=details)


def _study_post(**over):
    data = {
        "name": "Inglés", "plan_type": "study", "study_subtype": "general", "repeat": "custom",
        "custom_days": ["0", "2", "4"], "due_time": "20:00", "is_active": "on", "weeks": "8",
        "study_source": "playlist", "youtube_playlist_id": "PLabcdefghijklmnop",
    }
    data.update(over)
    return {k: v for k, v in data.items() if v is not None}


class StudyPlanFormWebTests(TestCase):
    """Un error al guardar un plan de Estudio tiene que significar «no se ha
    guardado nada», no un plan a medias con su tarea diaria sin nada enlazado."""

    def _nothing_saved(self):
        self.assertEqual(Plan.objects.count(), 0, "se guardó el plan aunque dio error")
        self.assertEqual(Task.objects.count(), 0, "se creó la tarea diaria aunque dio error")
        self.assertEqual(PlanItem.objects.count(), 0)

    def _post(self, **over):
        return self.client.post(reverse("tasks:plan_create"), _study_post(**over), follow=True)

    def test_playlist_without_minutes_nor_count_saves_nothing(self):
        r = self._post()
        self.assertContains(r, "Con una playlist")
        self._nothing_saved()

    def test_nothing_linked_saves_nothing(self):
        r = self._post(study_source="video", youtube_playlist_id=None)
        self.assertContains(r, "Pon algo enlazado")
        self._nothing_saved()

    def test_udemy_without_minutes_saves_nothing(self):
        r = self._post(study_source="udemy", youtube_playlist_id=None, watch_keyword="Excel")
        self.assertContains(r, "Curso de Udemy: pon los minutos")
        self._nothing_saved()

    def test_ilerna_without_minutes_saves_nothing(self):
        r = self._post(study_source="ilerna", youtube_playlist_id=None, ilerna_keyword="Programación")
        self.assertContains(r, "Clases de Ilerna: pon los minutos")
        self._nothing_saved()

    def test_playlist_with_a_video_count_creates_the_plan_and_its_linked_task(self):
        with _fake_playlist(5):
            r = self._post(target_video_count="2")
        plan = Plan.objects.get()
        self.assertRedirects(r, reverse("tasks:plan_detail", args=[plan.pk]))
        item = plan.items.get()
        self.assertEqual((item.youtube_playlist_id, item.target_video_count, item.target_minutes),
                         ("PLabcdefghijklmnop", 2, None))
        self.assertEqual(len(item.playlist_videos_cache), 5)
        task = Task.objects.get(series_id=plan.task_series_id, is_done=False)
        self.assertEqual((task.youtube_playlist_id, task.target_video_count), ("PLabcdefghijklmnop", 2))

    def test_udemy_course_with_minutes_marks_the_task_as_udemy(self):
        self._post(study_source="udemy", youtube_playlist_id=None, watch_keyword="Excel",
                   target_minutes="30", watch_track_mode="time")
        plan = Plan.objects.get()
        item = plan.items.get()
        self.assertEqual((item.watch_keyword, item.target_minutes, item.watch_requires_audio), ("Excel", 30, False))
        task = Task.objects.get(series_id=plan.task_series_id, is_done=False)
        self.assertEqual(task.subcategory, Task.SUBCATEGORY_UDEMY)

    def test_ilerna_classes_with_minutes_mark_the_task_as_ilerna(self):
        self._post(study_source="ilerna", youtube_playlist_id=None, ilerna_keyword="Programación",
                   target_minutes="45")
        plan = Plan.objects.get()
        item = plan.items.get()
        self.assertEqual((item.watch_site, item.watch_keyword, item.target_minutes),
                         (PlanItem.SITE_ILERNA, "Programación", 45))
        task = Task.objects.get(series_id=plan.task_series_id, is_done=False)
        self.assertEqual(task.subcategory, Task.SUBCATEGORY_ILERNA)

    def test_a_failed_edit_leaves_the_plan_as_it_was(self):
        with _fake_playlist(5):
            self._post(target_video_count="2")
        plan = Plan.objects.get()
        r = self.client.post(
            reverse("tasks:plan_edit", args=[plan.pk]),
            _study_post(name="Otro nombre", target_video_count=None), follow=True,
        )
        self.assertContains(r, "Con una playlist")
        plan.refresh_from_db()
        self.assertEqual(plan.name, "Inglés")
        self.assertEqual(plan.items.get().target_video_count, 2)

    def test_a_good_edit_updates_plan_and_objective(self):
        with _fake_playlist(5):
            self._post(target_video_count="2")
            plan = Plan.objects.get()
            r = self.client.post(
                reverse("tasks:plan_edit", args=[plan.pk]),
                _study_post(name="Inglés B1", target_video_count=None, target_minutes="25"),
            )
        self.assertEqual(r.status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.name, "Inglés B1")
        item = plan.items.get()
        self.assertEqual((item.target_minutes, item.target_video_count), (25, None))
        task = Task.objects.get(series_id=plan.task_series_id, is_done=False)
        self.assertEqual((task.title, task.target_minutes), ("Inglés B1", 25))


# ─────────────────────────────────────────────────────────────────────────────
# Objetivos de un plan de Estudio (crear / editar / quitar) y cierre de plan:
# lo que hace la web tiene que dejar lo mismo que hace la app
# ─────────────────────────────────────────────────────────────────────────────
from datetime import time as _time  # noqa: E402


def _patch_json(client, url, body):
    return client.patch(url, data=json.dumps(body), content_type="application/json")


class StudyObjectiveParityTests(TestCase):
    def _plan(self):
        plan = Plan.objects.create(
            user=get_current_user(), name="Inglés", plan_type=Plan.PLAN_TYPE_STUDY, repeat="custom",
            custom_days="0,2,4", started_on=date.today(), weeks=8, due_time=_time(20, 0),
        )
        plan.sync_task()
        return plan

    def _snap(self, plan):
        task = Task.objects.filter(series_id=plan.task_series_id, is_done=False).first()
        return {
            "items": sorted(
                (i.label, i.youtube_video_id, i.youtube_playlist_id, i.target_minutes, i.target_video_count,
                 len(i.playlist_videos_cache or []))
                for i in plan.items.all()
            ),
            "task": None if task is None else (
                task.youtube_video_id, task.youtube_playlist_id, task.target_minutes, task.target_video_count,
                task.watch_keyword, task.subcategory,
            ),
        }

    # acciones: devuelven (status_ok, ya_existe_item) y no hacen más
    def _create(self, channel, plan, **data):
        if channel == "web":
            return self.client.post(reverse("tasks:plan_item_create", args=[plan.pk]), data)
        return _post_json(self.client, reverse("api:plan_item_create", args=[plan.uuid]), data)

    def _edit(self, channel, plan, item, **data):
        if channel == "web":
            return self.client.post(reverse("tasks:plan_item_edit", args=[plan.pk, item.pk]), data)
        return _patch_json(self.client, reverse("api:plan_item_detail", args=[plan.uuid, item.pk]), data)

    def _remove(self, channel, plan, item):
        if channel == "web":
            return self.client.post(reverse("tasks:plan_item_delete", args=[plan.pk, item.pk]))
        return self.client.delete(reverse("api:plan_item_detail", args=[plan.uuid, item.pk]))

    def _both(self, scenario):
        """scenario(channel) hace todo lo del usuario y devuelve el plan."""
        snaps = {}
        for channel in ("web", "api"):
            Plan.objects.all().delete()
            Task.all_objects.all().delete()
            with _fake_playlist(5):
                snaps[channel] = self._snap(scenario(channel))
        self.assertEqual(snaps["web"], snaps["api"], "la web y la app dejan el objetivo distinto")
        return snaps["web"]

    def test_video_objective_with_minutes(self):
        def scenario(ch):
            plan = self._plan()
            self._create(ch, plan, label="Podcast", youtube_video_id="dQw4w9WgXcQ", target_minutes="15")
            return plan

        snap = self._both(scenario)
        self.assertEqual(snap["items"], [("Podcast", "dQw4w9WgXcQ", "", 15, None, 0)])
        self.assertEqual(snap["task"][:3], ("dQw4w9WgXcQ", "", 15))

    def test_playlist_objective_with_a_video_count_syncs_the_playlist(self):
        def scenario(ch):
            plan = self._plan()
            self._create(ch, plan, youtube_playlist_id="PLabcdefghijklmnop", target_video_count="2")
            return plan

        snap = self._both(scenario)
        self.assertEqual(snap["items"], [("", "", "PLabcdefghijklmnop", None, 2, 5)])
        self.assertEqual(snap["task"][1], "PLabcdefghijklmnop")

    def test_timer_only_objective(self):
        def scenario(ch):
            plan = self._plan()
            self._create(ch, plan, label="Repaso", target_minutes="25")
            return plan

        snap = self._both(scenario)
        self.assertEqual(snap["items"], [("Repaso", "", "", 25, None, 0)])
        self.assertEqual(snap["task"][:4], ("", "", 25, None))

    def test_playlist_without_a_target_is_refused_everywhere_and_saves_nothing(self):
        def scenario(ch):
            plan = self._plan()
            r = self._create(ch, plan, youtube_playlist_id="PLabcdefghijklmnop")
            self.assertIn(r.status_code, (302, 400), ch)
            return plan

        snap = self._both(scenario)
        self.assertEqual(snap["items"], [])
        self.assertEqual(snap["task"][:2], ("", ""))

    def test_editing_the_video_updates_the_daily_task(self):
        def scenario(ch):
            plan = self._plan()
            self._create(ch, plan, youtube_video_id="dQw4w9WgXcQ", target_minutes="15")
            item = plan.items.get()
            self._edit(ch, plan, item, youtube_video_id="9bZkp7q19f0", target_minutes="30")
            return plan

        snap = self._both(scenario)
        self.assertEqual(snap["task"][:3], ("9bZkp7q19f0", "", 30))

    def test_switching_from_video_to_playlist_clears_the_video(self):
        def scenario(ch):
            plan = self._plan()
            self._create(ch, plan, youtube_video_id="dQw4w9WgXcQ", target_minutes="15")
            item = plan.items.get()
            self._edit(ch, plan, item, youtube_video_id="", youtube_playlist_id="PLabcdefghijklmnop",
                       target_video_count="1", target_minutes="")
            return plan

        snap = self._both(scenario)
        self.assertEqual(snap["task"][:4], ("", "PLabcdefghijklmnop", None, 1))

    def test_removing_the_objective_unlinks_the_daily_task_right_away(self):
        def scenario(ch):
            plan = self._plan()
            self._create(ch, plan, youtube_video_id="dQw4w9WgXcQ", target_minutes="15")
            self._remove(ch, plan, plan.items.get())
            return plan

        snap = self._both(scenario)
        self.assertEqual(snap["items"], [])
        self.assertEqual(snap["task"][:3], ("", "", None), "la tarea diaria conserva el vídeo de un objetivo ya quitado")

    def test_a_general_plan_takes_no_objectives(self):
        plan = Plan.objects.create(
            user=get_current_user(), name="Beber agua", plan_type=Plan.PLAN_TYPE_GENERAL, repeat="daily",
            started_on=date.today(), weeks=4, due_time=_time(21, 0),
        )
        plan.sync_task()
        before = plan.items.count()
        r = self.client.post(reverse("tasks:plan_item_create", args=[plan.pk]), {"label": "x"})
        self.assertRedirects(r, reverse("tasks:plan_detail", args=[plan.pk]), fetch_redirect_response=False)
        r = _post_json(self.client, reverse("api:plan_item_create", args=[plan.uuid]), {"label": "x"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(plan.items.count(), before)

    def test_unknown_item_and_other_plan_are_404(self):
        plan = self._plan()
        other = self._plan()
        r = self.client.post(reverse("tasks:plan_item_delete", args=[plan.pk, 99999]))
        self.assertEqual(r.status_code, 404)
        r = self.client.delete(reverse("api:plan_item_detail", args=[plan.uuid, 99999]))
        self.assertEqual(r.status_code, 404)
        item = PlanItem.objects.create(plan=other, progression=PlanItem.PROG_COMPLETION, is_headline=True)
        r = self.client.post(reverse("tasks:plan_item_delete", args=[plan.pk, item.pk]))
        self.assertEqual(r.status_code, 404, "se pudo borrar el objetivo de OTRO plan")

    def test_move_swaps_two_objectives_and_ignores_bad_direction(self):
        plan = self._plan()
        a = PlanItem.objects.create(plan=plan, label="A", progression=PlanItem.PROG_COMPLETION)
        b = PlanItem.objects.create(plan=plan, label="B", progression=PlanItem.PROG_COMPLETION)
        url = reverse("tasks:plan_item_move", args=[plan.pk, b.pk])
        self.client.post(url, {"direction": "up"})
        self.assertEqual([i.label for i in plan.ordered_items()], ["B", "A"])
        self.client.post(url, {"direction": "sideways"})
        self.assertEqual([i.label for i in plan.ordered_items()], ["B", "A"])
        self.client.post(url, {"direction": "up"})  # ya está arriba: no pasa nada
        self.assertEqual([i.label for i in plan.ordered_items()], ["B", "A"])
        self.assertEqual(self.client.get(url).status_code, 405)


class PlanCloseParityTests(TestCase):
    def _plan(self):
        plan = Plan.objects.create(
            user=get_current_user(), name="Inglés", plan_type=Plan.PLAN_TYPE_STUDY, repeat="custom",
            custom_days="0,2,4", started_on=date.today(), weeks=8, due_time=_time(20, 0),
        )
        PlanItem.objects.create(plan=plan, progression=PlanItem.PROG_COMPLETION, is_headline=True,
                                youtube_video_id="dQw4w9WgXcQ")
        plan.sync_task()
        return plan

    def _state(self, plan):
        plan.refresh_from_db()
        return (
            plan.closed_at is not None, plan.is_active, plan.final_progress_pct,
            Task.objects.filter(series_id=plan.task_series_id, is_done=False).count(),
        )

    def test_closing_by_web_and_by_app_leaves_the_same_state(self):
        states = {}
        for channel in ("web", "api"):
            Plan.objects.all().delete()
            Task.all_objects.all().delete()
            plan = self._plan()
            self.assertEqual(Task.objects.filter(series_id=plan.task_series_id, is_done=False).count(), 1)
            if channel == "web":
                r = self.client.post(reverse("tasks:plan_close", args=[plan.pk]))
                self.assertEqual(r.status_code, 200)
            else:
                r = self.client.post(reverse("api:plan_close", args=[plan.uuid]))
                self.assertEqual(r.status_code, 200)
            states[channel] = self._state(plan)
        self.assertEqual(states["web"], states["api"])
        closed, active, pct, pending = states["web"]
        self.assertEqual((closed, active, pending), (True, False, 0))
        self.assertIsNotNone(pct)

    def test_the_close_page_asks_first_and_closing_twice_changes_nothing(self):
        plan = self._plan()
        r = self.client.get(reverse("tasks:plan_close", args=[plan.pk]))
        self.assertEqual(r.status_code, 200)
        plan.refresh_from_db()
        self.assertIsNone(plan.closed_at, "solo mirar la pantalla de cierre no debe cerrar el plan")
        self.client.post(reverse("tasks:plan_close", args=[plan.pk]))
        plan.refresh_from_db()
        first = plan.closed_at
        self.assertIsNotNone(first)
        self.client.post(reverse("tasks:plan_close", args=[plan.pk]))
        _post_json(self.client, reverse("api:plan_close", args=[plan.uuid]), {})
        plan.refresh_from_db()
        self.assertEqual(plan.closed_at, first, "cerrar otra vez movió la fecha de cierre")

    def test_a_closed_plan_stays_listed_as_closed_and_its_page_renders(self):
        plan = self._plan()
        self.client.post(reverse("tasks:plan_close", args=[plan.pk]))
        r = self.client.get(reverse("tasks:plan_list"))
        self.assertContains(r, "Inglés")
        r = self.client.get(reverse("tasks:plan_detail", args=[plan.pk]))
        self.assertEqual(r.status_code, 200)
        data = self.client.get(reverse("api:plan_detail", args=[plan.uuid])).json()["plan"]
        self.assertIsNotNone(data["closed_at"])
        self.assertIsNotNone(data["final_progress_pct"])

    def test_deleting_a_plan_removes_its_pending_task_but_keeps_history(self):
        for channel in ("web", "api"):
            Plan.objects.all().delete()
            Task.all_objects.all().delete()
            plan = self._plan()
            if channel == "web":
                r = self.client.post(reverse("tasks:plan_delete", args=[plan.pk]))
                self.assertEqual(r.status_code, 302)
            else:
                r = self.client.delete(reverse("api:plan_detail", args=[plan.uuid]))
                self.assertEqual(r.status_code, 200)
            self.assertEqual(Task.objects.filter(series_id=plan.task_series_id, is_done=False).count(), 0, channel)
            self.assertEqual(self.client.get(reverse("tasks:plan_detail", args=[plan.pk])).status_code, 404, channel)


# ─────────────────────────────────────────────────────────────────────────────
# Plan de lectura (visor de PDF con página): formulario, progreso y sesión,
# por la web y por la app
# ─────────────────────────────────────────────────────────────────────────────
import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402

from django.test import override_settings  # noqa: E402
from django.utils import timezone  # noqa: E402

from .models import ReadingPdf  # noqa: E402


class _Clock:
    def __init__(self, start):
        self.t = timezone.make_aware(start)

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)


class ReadingPlanTests(TestCase):
    START = datetime(2026, 3, 2, 9, 0)  # lunes

    def setUp(self):
        self.clock = _Clock(self.START)
        patcher = mock.patch("django.utils.timezone.now", self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)

    FORM = {"title": "El libro", "reading_pdf_key": "k1", "reading_first_page": "1",
            "reading_last_page": "300", "reading_target_weeks": "6", "custom_days": ["0", "2", "4"]}

    def _web_create(self, **over):
        data = dict(self.FORM, **over)
        return self.client.post(reverse("tasks:reading_plan_create"), data)

    def _api_create(self, **over):
        data = {"title": "El libro", "pdf_key": "k1", "first_page": 1, "last_page": 300, "target_weeks": 6,
                "custom_days": [0, 2, 4]}
        data.update(over)
        return _post_json(self.client, reverse("api:reading_plan_create"), data)

    def _plan(self):
        self._web_create()
        return Task.objects.get(subcategory=Task.SUBCATEGORY_READING)

    def _progress(self, channel, task, page):
        if channel == "web":
            return _post_json(self.client, reverse("tasks:task_reading_progress", args=[task.pk]), {"page": page})
        return _post_json(self.client, reverse("api:reading_progress", args=[task.uuid]), {"page": page})

    def _save(self, channel, task):
        if channel == "web":
            return self.client.post(reverse("tasks:task_reading_save", args=[task.pk]))
        return self.client.post(reverse("api:reading_session_save", args=[task.uuid]))

    # ---- formulario ----
    def test_missing_pages_or_weeks_saves_nothing(self):
        for over in ({"reading_last_page": ""}, {"reading_target_weeks": ""}, {"reading_last_page": "abc"},
                     {"reading_target_weeks": "0"}):
            r = self._web_create(**over)
            self.assertEqual(r.status_code, 200, over)
        self.assertEqual(Task.objects.count(), 0)
        for over in ({"last_page": None}, {"target_weeks": 0}, {"last_page": "x"}):
            r = self._api_create(**over)
            self.assertEqual(r.status_code, 400, over)
        self.assertEqual(Task.objects.count(), 0)

    def test_first_page_after_the_last_is_refused(self):
        self.assertEqual(self._web_create(reading_first_page="400").status_code, 200)
        self.assertEqual(self._api_create(first_page=400).status_code, 400)
        self.assertEqual(Task.objects.count(), 0)

    def test_creating_by_web_and_by_app_gives_the_same_plan(self):
        def fields(t):
            return (t.title, t.category, t.subcategory, t.reading_mode, t.reading_pdf_key, t.reading_first_page,
                    t.reading_last_page, t.reading_target_weeks, str(t.reading_started_on), t.repeat, t.custom_days,
                    str(t.due_date), t.reading_day_goal)

        r = self._web_create()
        web = Task.objects.get(subcategory=Task.SUBCATEGORY_READING)
        self.assertRedirects(r, reverse("tasks:task_reading", args=[web.pk]), fetch_redirect_response=False)
        web_fields = fields(web)
        Task.all_objects.all().delete()
        self.assertEqual(self._api_create().status_code, 200)
        api_fields = fields(Task.objects.get(subcategory=Task.SUBCATEGORY_READING))
        self.assertEqual(web_fields, api_fields)
        # 300 páginas en 6 semanas (42 días): 8 al día, redondeando hacia arriba
        self.assertEqual(api_fields[-1], 8)

    def test_defaults_when_title_and_days_are_missing(self):
        self.client.post(reverse("tasks:reading_plan_create"), {
            "reading_last_page": "100", "reading_target_weeks": "2"})
        t = Task.objects.get()
        self.assertEqual((t.title, t.custom_days), ("Plan de lectura", "0,2,4"))
        Task.all_objects.all().delete()
        _post_json(self.client, reverse("api:reading_plan_create"), {"last_page": 100, "target_weeks": 2})
        t = Task.objects.get()
        self.assertEqual((t.title, t.custom_days), ("Plan de lectura", "0,2,4"))

    def test_editing_keeps_what_was_already_read(self):
        task = self._plan()
        self._progress("web", task, 20)
        task.refresh_from_db()
        started = task.reading_started_on
        r = self.client.post(reverse("tasks:reading_plan_edit", args=[task.pk]),
                             dict(self.FORM, title="Otro título", reading_target_weeks="10"))
        self.assertEqual(r.status_code, 302)
        task.refresh_from_db()
        self.assertEqual((task.title, task.reading_target_weeks), ("Otro título", 10))
        self.assertEqual((task.reading_current_page, task.reading_started_on), (20, started))
        # lo mismo desde la app
        r = _post_json(self.client, reverse("api:reading_plan_update", args=[task.uuid]),
                       {"title": "Desde el móvil", "last_page": 300, "target_weeks": 12, "custom_days": [1, 3]})
        self.assertEqual(r.status_code, 200, r.content)
        task.refresh_from_db()
        self.assertEqual((task.title, task.reading_target_weeks, task.custom_days), ("Desde el móvil", 12, "1,3"))
        self.assertEqual((task.reading_current_page, task.reading_started_on), (20, started))

    def test_editing_something_that_is_not_a_reading_plan_is_404(self):
        other = Task.objects.create(title="Otra", due_date=timezone.localtime(timezone.now()).date(),
                                    user=get_current_user())
        self.assertEqual(self.client.get(reverse("tasks:reading_plan_edit", args=[other.pk])).status_code, 404)
        r = _post_json(self.client, reverse("api:reading_plan_update", args=[other.uuid]),
                       {"last_page": 10, "target_weeks": 1})
        self.assertEqual(r.status_code, 404)

    # ---- visor ----
    def test_viewer_page_opens_for_a_plan_and_404_for_a_freestyle_reading(self):
        task = self._plan()
        r = self.client.get(reverse("tasks:task_reading", args=[task.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "El libro")
        free = Task.objects.create(
            title="Libreta", category=Task.CATEGORY_WORK, subcategory=Task.SUBCATEGORY_READING,
            due_date=timezone.localtime(timezone.now()).date(), user=get_current_user(),
        )
        self.assertEqual(self.client.get(reverse("tasks:task_reading", args=[free.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("api:reading_state", args=[task.uuid])).status_code, 200)

    # ---- progreso ----
    def test_pages_never_go_back_and_cannot_outrun_the_clock(self):
        task = self._plan()
        for ch in ("web", "api"):
            Task.all_objects.all().delete()
            task = self._plan()
            self.assertEqual(self._progress(ch, task, 5).status_code, 200)       # primer aviso: sin tope
            task.refresh_from_db()
            self.assertEqual(task.reading_current_page, 5, ch)
            self._progress(ch, task, 50)                                           # inmediato: no puede saltar
            task.refresh_from_db()
            self.assertEqual(task.reading_current_page, 5, ch)
            self.clock.advance(seconds=45 * 10)                                    # 10 páginas de lectura real
            self._progress(ch, task, 50)
            task.refresh_from_db()
            self.assertEqual(task.reading_current_page, 15, ch)
            self._progress(ch, task, 3)                                            # no retrocede
            task.refresh_from_db()
            self.assertEqual(task.reading_current_page, 15, ch)

    def test_garbage_page_is_a_400_not_a_500(self):
        task = self._plan()
        for ch in ("web", "api"):
            for bad in ("abc", None, [1], {"a": 1}):
                r = self._progress(ch, task, bad)
                self.assertEqual(r.status_code, 400, (ch, bad))

    def test_the_viewer_beacon_posts_a_form_not_json(self):
        task = self._plan()
        url = reverse("tasks:task_reading_progress", args=[task.pk])
        form = "application/x-www-form-urlencoded"  # lo que manda navigator.sendBeacon del visor
        r = self.client.post(url, data="page=7", content_type=form)
        self.assertEqual(r.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.reading_current_page, 7)
        r = self.client.post(url, data="page=x", content_type=form)
        self.assertEqual(r.status_code, 400)
        r = self.client.post(url, data="", content_type=form)
        self.assertEqual(r.status_code, 400)

    @override_settings()
    def test_reaching_the_last_page_closes_the_plan(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        with override_settings(MEDIA_ROOT=tmp):
            from django.core.files.uploadedfile import SimpleUploadedFile
            for ch in ("web", "api"):
                Task.all_objects.all().delete()
                TimerSession.objects.all().delete()
                self.clock.t = timezone.make_aware(self.START)
                task = self._plan()
                ReadingPdf.store(get_current_user(), "k1", SimpleUploadedFile("l.pdf", b"%PDF-1.4 x"))
                self._progress(ch, task, 10)
                self.clock.advance(days=14)                                        # en plazo (2 de 6 semanas)
                r = self._progress(ch, task, 9999)
                data = r.json()
                self.assertTrue(data["finished"], ch)
                task.refresh_from_db()
                self.assertEqual(task.reading_current_page, 300, ch)               # tope: la última página real
                self.assertEqual((task.reading_final_pct, task.repeat, task.is_done), (100, Task.REPEAT_NONE, True), ch)
                self.assertIsNotNone(task.reading_completed_at)
                self.assertEqual(ReadingPdf.objects.count(), 0, "el PDF del servidor debía borrarse al acabar")
                self.assertEqual(Task.objects.filter(is_done=False).count(), 0, "no debe nacer otro día")
                # tiempo de lectura volcado a una sesión (10 min de tope por aviso)
                self.assertEqual(TimerSession.objects.filter(task=task).count(), 1, ch)

    def test_finishing_late_scales_the_final_percentage(self):
        task = self._plan()
        self._progress("web", task, 1)
        self.clock.advance(days=84)                                                # 12 semanas para un plan de 6
        self._progress("web", task, 9999)
        task.refresh_from_db()
        self.assertEqual(task.reading_final_pct, 50)

    # ---- «terminar sesión de hoy» ----
    def test_ending_todays_session_marks_it_and_spawns_the_next_marked_day(self):
        for ch in ("web", "api"):
            Task.all_objects.all().delete()
            task = self._plan()                                                    # lunes
            self.assertEqual(self._save(ch, task).status_code, 200)
            task.refresh_from_db()
            self.assertTrue(task.is_done, ch)
            nxt = Task.objects.get(series_id=task.series_id, is_done=False)
            self.assertEqual(nxt.due_date, task.due_date + timedelta(days=2), ch)  # miércoles

    def test_ending_a_future_session_early_changes_nothing(self):
        for ch in ("web", "api"):
            Task.all_objects.all().delete()
            task = self._plan()
            self._save(ch, task)                                                   # cierra el lunes
            future = Task.objects.get(series_id=task.series_id, is_done=False)     # miércoles: aún no toca
            r = self._save(ch, future)
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.json().get("early"), ch)
            future.refresh_from_db()
            self.assertFalse(future.is_done, ch)
            self.assertEqual(Task.objects.filter(series_id=task.series_id).count(), 2, ch)

    def test_ending_the_session_of_a_finished_book_is_harmless(self):
        task = self._plan()
        self._progress("web", task, 1)
        self.clock.advance(days=3)
        self._progress("web", task, 9999)
        count = Task.all_objects.count()
        for ch in ("web", "api"):
            r = self._save(ch, task)
            self.assertEqual(r.status_code, 200, ch)
        self.assertEqual(Task.all_objects.count(), count)

    def test_reading_time_goes_to_the_time_stats(self):
        task = self._plan()
        self._progress("web", task, 1)
        self.clock.advance(minutes=5)
        self._progress("web", task, 2)
        self._save("web", task)
        mins = sum(s.minutes for s in TimerSession.objects.filter(task=task))
        self.assertEqual(mins, 5)

    # ---- borrar ----
    def test_deleting_one_day_skips_it_and_deleting_the_plan_removes_the_series(self):
        task = self._plan()
        r = self.client.delete(reverse("api:task_detail", args=[task.uuid]))
        self.assertEqual(r.status_code, 200)
        pend = Task.objects.filter(series_id=task.series_id, is_done=False)
        self.assertEqual(pend.count(), 1, "borrar el día debía dejar viva la serie")
        r = self.client.post(reverse("tasks:reading_plan_delete", args=[pend.get().pk]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Task.objects.filter(series_id=task.series_id).count(), 0)


# ─────────────────────────────────────────────────────────────────────────────
# Estudio · Hábito simple con una playlist seguida: qué vídeo toca cada día y
# cuándo se acaba el plan
# ─────────────────────────────────────────────────────────────────────────────
class StudyPlaylistTrackingTests(TestCase):
    def _plan(self, n_videos=6, **item_fields):
        with _fake_playlist(n_videos):
            self.client.post(reverse("tasks:plan_create"), _study_post(**item_fields))
        return Plan.objects.get()

    def _pending(self, plan):
        self.client.get(reverse("tasks:task_list"))  # lo que hace la lista al abrirse: sync_all_tasks
        return Task.objects.get(series_id=plan.task_series_id, is_done=False)

    def _done(self, plan, minutes=None):
        task = self._pending(plan)
        r = self.client.post(reverse("tasks:task_mark_done", args=[task.pk]))
        if minutes is not None:
            Occurrence.objects.filter(series_id=plan.task_series_id).update(minutes_watched=minutes)
        return r

    def test_videos_per_day_advance_the_start_index_and_the_plan_closes_with_the_list(self):
        plan = self._plan(target_video_count="2")
        self.assertEqual(self._pending(plan).playlist_start_index, 0)
        self._done(plan)
        self.assertEqual(self._pending(plan).playlist_start_index, 2)
        self._done(plan)
        self.assertEqual(self._pending(plan).playlist_start_index, 4)
        r = self._done(plan)  # el tercer día se acaban los 6 vídeos
        plan.refresh_from_db()
        self.assertIsNotNone(plan.closed_at, "al ver el último vídeo el plan debía cerrarse")
        self.assertFalse(plan.is_active)
        self.assertRedirects(r, reverse("tasks:plan_close", args=[plan.pk]), fetch_redirect_response=False)
        self.client.get(reverse("tasks:task_list"))
        self.assertEqual(Task.objects.filter(series_id=plan.task_series_id, is_done=False).count(), 0,
                         "un plan cerrado no debe seguir dejando tareas")

    def test_minutes_per_day_consume_whole_videos_by_real_minutes_watched(self):
        plan = self._plan(n_videos=6, target_minutes="10")  # vídeos de 5 min (fake)
        self.assertEqual(self._pending(plan).playlist_start_index, 0)
        self._done(plan, minutes=10)                          # 600 s → caben 2 vídeos enteros
        self.assertEqual(self._pending(plan).playlist_start_index, 2)
        Occurrence.objects.filter(series_id=plan.task_series_id).update(minutes_watched=7)
        self.assertEqual(self._pending(plan).playlist_start_index, 1,
                         "con 7 min vistos solo cabe 1 vídeo entero (no se reanuda a mitad)")

    def test_unmarking_a_day_gives_the_videos_back(self):
        plan = self._plan(target_video_count="2")
        first = self._pending(plan)
        self._done(plan)
        self.assertEqual(self._pending(plan).playlist_start_index, 2)
        self.client.post(reverse("tasks:task_reopen", args=[first.pk]))
        self.assertEqual(self._pending(plan).playlist_start_index, 0)

    def test_a_short_playlist_never_points_past_the_last_video(self):
        plan = self._plan(n_videos=3, target_video_count="5")
        self._done(plan)  # 5 vídeos de una lista de 3
        plan.refresh_from_db()
        self.assertIsNotNone(plan.closed_at)

    def test_without_a_synced_cache_the_playlist_starts_from_the_beginning_every_day(self):
        with mock.patch("tasks.youtube_search.list_playlist_items", side_effect=YouTubeSearchError("sin cuota")):
            self.client.post(reverse("tasks:plan_create"), _study_post(target_video_count="2"))
        plan = Plan.objects.get()
        self.assertEqual(plan.items.get().playlist_videos_cache, [])
        task = self._pending(plan)
        self.assertEqual((task.youtube_playlist_id, task.playlist_start_index), ("PLabcdefghijklmnop", None))
        self._done(plan)
        plan.refresh_from_db()
        self.assertIsNone(plan.closed_at, "sin caché no se puede saber cuándo se acaba la lista")
        self.assertIsNone(self._pending(plan).playlist_start_index)

    def test_the_app_marks_the_same_way(self):
        plan = self._plan(target_video_count="3")
        task = self._pending(plan)
        r = self.client.post(reverse("api:task_mark", args=[task.uuid, "done"]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._pending(plan).playlist_start_index, 3)
        task = self._pending(plan)
        self.client.post(reverse("api:task_mark", args=[task.uuid, "done"]))
        plan.refresh_from_db()
        self.assertIsNotNone(plan.closed_at)
        data = self.client.get(reverse("api:plan_detail", args=[plan.uuid])).json()["plan"]
        self.assertIsNotNone(data["closed_at"])


# ─────────────────────────────────────────────────────────────────────────────
# Barrido: TODAS las pantallas de la web y las lecturas de la API, con datos de
# todos los tipos a la vez. Un 500 o un fallo de plantilla en cualquiera de
# ellas rompe este test.
# ─────────────────────────────────────────────────────────────────────────────
from .models import Exercise  # noqa: E402


class EveryPageRendersTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_current_user()
        today = timezone.localtime(timezone.now()).date()
        mk = Task.objects.create
        cls.tasks = {}
        cls.tasks["simple"] = mk(title="Beber agua", due_date=today, repeat=Task.REPEAT_DAILY, user=user)
        cls.tasks["timer"] = mk(title="Meditar", due_date=today, repeat=Task.REPEAT_DAILY, user=user,
                                wants_timer=True, target_minutes=15)
        cls.tasks["avoid"] = mk(title="No fumar", category=Task.CATEGORY_AVOID, due_date=today,
                                repeat=Task.REPEAT_DAILY, user=user, due_time=_time(22, 0))
        cls.tasks["video"] = mk(title="Vídeo", category=Task.CATEGORY_STUDY, due_date=today, user=user,
                                youtube_video_id="dQw4w9WgXcQ", target_minutes=10)
        cls.tasks["playlist"] = mk(title="Playlist", category=Task.CATEGORY_STUDY, due_date=today, user=user,
                                   repeat=Task.REPEAT_DAILY, youtube_playlist_id="PLabcdefghijklmnop",
                                   target_video_count=2, playlist_start_index=1,
                                   playlist_videos_cache=[{"video_id": f"v{i:010d}", "duration_seconds": 300}
                                                          for i in range(5)])
        cls.tasks["udemy"] = mk(title="Excel", category=Task.CATEGORY_STUDY, subcategory=Task.SUBCATEGORY_UDEMY,
                                due_date=today, user=user, target_minutes=30, watch_keyword="Excel",
                                course_progress_pct=40)
        cls.tasks["ilerna"] = mk(title="Clase", category=Task.CATEGORY_STUDY, subcategory=Task.SUBCATEGORY_ILERNA,
                                 due_date=today, user=user, target_minutes=45)
        cls.tasks["reading_free"] = mk(title="Leer", category=Task.CATEGORY_WORK,
                                       subcategory=Task.SUBCATEGORY_READING, due_date=today, user=user,
                                       target_minutes=20)
        cls.tasks["reading_plan"] = mk(
            title="El libro", category=Task.CATEGORY_WORK, subcategory=Task.SUBCATEGORY_READING,
            reading_mode=Task.READING_MODE_PLAN, reading_first_page=1, reading_last_page=300,
            reading_target_weeks=6, reading_started_on=today, reading_current_page=40,
            repeat=Task.REPEAT_CUSTOM, custom_days="0,1,2,3,4,5,6", due_date=today, user=user,
        )
        cls.tasks["reading_plan"].ensure_reading_day_goal()
        cls.tasks["sport"] = mk(title="Flexiones", category=Task.CATEGORY_SPORT,
                                subcategory=Task.SUBCATEGORY_UPPER_BODY, due_date=today, user=user)
        cls.tasks["lower"] = mk(title="Piernas", category=Task.CATEGORY_SPORT,
                                subcategory=Task.SUBCATEGORY_LOWER_BODY, due_date=today, user=user)
        cls.tasks["running"] = mk(title="Correr", category=Task.CATEGORY_SPORT,
                                  subcategory=Task.SUBCATEGORY_RUNNING, due_date=today, user=user,
                                  target_distance_km=5)
        cls.tasks["done"] = mk(title="Ya hecha", due_date=today, user=user, repeat=Task.REPEAT_DAILY)
        cls.tasks["done"].mark_done()
        cls.tasks["failed"] = mk(title="Fallada", category=Task.CATEGORY_AVOID, due_date=today, user=user,
                                 repeat=Task.REPEAT_DAILY)
        cls.tasks["failed"].mark_failed()
        TimerSession.objects.create(task=cls.tasks["timer"], user=user, series_id=cls.tasks["timer"].series_id,
                                    source=TimerSession.SOURCE_MANUAL, minutes=12)
        TimerSession.objects.create(task=cls.tasks["udemy"], user=user, series_id=cls.tasks["udemy"].series_id,
                                    source=TimerSession.SOURCE_PC_USAGE, minutes=25, subcategory="udemy")

        # Planes de cada tipo
        mkp = Plan.objects.create
        base = dict(user=user, started_on=today, weeks=8, repeat="custom", custom_days="0,2,4", due_time=_time(20, 0))
        cls.plans = {}
        general = mkp(name="Beber agua (plan)", plan_type=Plan.PLAN_TYPE_GENERAL, **base)
        general.sync_task()
        cls.plans["general"] = general
        study = mkp(name="Inglés (plan)", plan_type=Plan.PLAN_TYPE_STUDY, **base)
        PlanItem.objects.create(
            plan=study, progression=PlanItem.PROG_COMPLETION, is_headline=True, youtube_playlist_id="PLzzzzzzzzzzzzzz",
            target_video_count=2, playlist_videos_cache=[{"video_id": f"w{i:010d}", "duration_seconds": 300}
                                                          for i in range(6)],
        )
        study.sync_task()
        cls.plans["study"] = study
        udemy = mkp(name="Excel (plan)", plan_type=Plan.PLAN_TYPE_STUDY, **base)
        PlanItem.objects.create(plan=udemy, progression=PlanItem.PROG_COMPLETION, is_headline=True,
                                watch_keyword="Excel", target_minutes=30)
        udemy.sync_task()
        cls.plans["udemy"] = udemy
        ilerna = mkp(name="Ilerna (plan)", plan_type=Plan.PLAN_TYPE_STUDY, **base)
        PlanItem.objects.create(plan=ilerna, progression=PlanItem.PROG_COMPLETION, is_headline=True,
                                watch_site=PlanItem.SITE_ILERNA, watch_keyword="Programación", target_minutes=45)
        ilerna.sync_task()
        cls.plans["ilerna"] = ilerna
        language = mkp(name="Alemán (plan)", plan_type=Plan.PLAN_TYPE_STUDY,
                       study_subtype=Plan.STUDY_SUBTYPE_LANGUAGE, language_name="Alemán", level_from="A1",
                       level_to="A2", language_daily_minutes=30, known_languages="español", quiz_every_n_videos=2,
                       **base)
        for i in range(4):
            CourseModule.objects.create(plan=language, order=i, title=f"Lección {i}", youtube_video_id=f"x{i:010d}",
                                        duration_seconds=600,
                                        watched_at=timezone.now() if i < 2 else None)
        language.sync_task()
        cls.plans["language"] = language
        cls.quiz = CourseQuiz.objects.create(
            plan=language, up_to_order=2, topics=["Saludos"], total=1,
            questions=[{"question": "¿Hola?", "options": ["Hallo", "Tschüss", "Danke", "Bitte"], "correct_index": 0}],
        )
        sport = mkp(name="Fuerza (plan)", plan_type=Plan.PLAN_TYPE_SPORT, **base)
        ex = Exercise.objects.exclude(mode=Exercise.MODE_DISTANCE).filter(is_active=True).first()
        if ex is not None:
            PlanItem.objects.create(plan=sport, exercise=ex, progression=PlanItem.PROG_REPS, start_sets=3,
                                    start_reps=8, goal_reps=12, sport_mode=PlanItem.SPORT_MODE_CAMERA)
        sport.sync_task()
        cls.plans["sport"] = sport
        closed = mkp(name="Cerrado (plan)", plan_type=Plan.PLAN_TYPE_GENERAL, **base)
        closed.sync_task()
        closed.final_progress_pct = 80
        closed.closed_at = timezone.now()
        closed.is_active = False
        closed.save()
        cls.plans["closed"] = closed

    def setUp(self):
        Task.expire_overdue()

    def _ok(self, url, codes=(200,), **kw):
        r = self.client.get(url, **kw)
        self.assertIn(r.status_code, codes, f"{url} → {r.status_code}")
        # Con DUMP_PAGES_DIR puesto, se guarda el HTML de cada página para
        # comprobar aparte (con node) que su JavaScript en línea compila.
        dump = os.environ.get("DUMP_PAGES_DIR")
        if dump and r.status_code == 200 and "text/html" in r.get("Content-Type", ""):
            os.makedirs(dump, exist_ok=True)
            name = re.sub(r"[^A-Za-z0-9_.-]+", "_", url.strip("/")) or "root"
            with open(os.path.join(dump, name + ".html"), "wb") as fh:
                fh.write(r.content)
        return r

    # ---- web ----
    def test_task_list_in_every_range_and_category(self):
        for rng, _ in Task.RANGE_CHOICES:
            self._ok(reverse("tasks:task_list") + f"?range={rng}")
            for cat, _ in Task.CATEGORY_CHOICES:
                self._ok(reverse("tasks:task_list") + f"?range={rng}&cat={cat}")
        self._ok(reverse("tasks:task_list") + "?range=nope&cat=nope")

    def test_task_forms_for_every_kind_of_task(self):
        self._ok(reverse("tasks:task_create"))
        for key, task in self.tasks.items():
            if key == "reading_plan":
                # un plan de lectura se edita en su propio formulario
                r = self.client.get(reverse("tasks:task_edit", args=[task.pk]))
                self.assertRedirects(r, reverse("tasks:reading_plan_edit", args=[task.pk]),
                                     fetch_redirect_response=False)
                self._ok(reverse("tasks:reading_plan_edit", args=[task.pk]))
                continue
            self._ok(reverse("tasks:task_edit", args=[task.pk]))

    def test_task_screens(self):
        t = self.tasks
        self._ok(reverse("tasks:task_focus", args=[t["timer"].pk]))
        self._ok(reverse("tasks:task_focus", args=[t["reading_free"].pk]))
        self._ok(reverse("tasks:task_focus", args=[t["udemy"].pk]))
        for key in ("video", "playlist", "udemy", "ilerna"):
            self._ok(reverse("tasks:task_video", args=[t[key].pk]), codes=(200, 302))
        self._ok(reverse("tasks:task_reading", args=[t["reading_plan"].pk]))
        # deporte: solo comprobar que abren
        for key in ("sport", "lower", "running"):
            self._ok(reverse("tasks:task_workout", args=[t[key].pk]), codes=(200, 302))

    def test_plan_screens(self):
        self._ok(reverse("tasks:plan_list"))
        self._ok(reverse("tasks:plan_create"))
        self._ok(reverse("tasks:plan_ai_create"))
        for key, plan in self.plans.items():
            self._ok(reverse("tasks:plan_detail", args=[plan.pk]))
            self._ok(reverse("tasks:plan_edit", args=[plan.pk]))
            self._ok(reverse("tasks:plan_close", args=[plan.pk]))
            self._ok(reverse("tasks:plan_item_create", args=[plan.pk]), codes=(200, 302))
            self._ok(reverse("tasks:plan_item_bulk_create", args=[plan.pk]), codes=(200, 302))
            for item in plan.items.all():
                self._ok(reverse("tasks:plan_item_edit", args=[plan.pk, item.pk]), codes=(200, 302))
        # sin borrador guardado, la confirmación de idioma vuelve al formulario
        self._ok(reverse("tasks:plan_language_confirm"), codes=(200, 302))

    def test_quiz_screens(self):
        self._ok(reverse("tasks:quiz_take", args=[self.quiz.uuid]))
        self._ok(reverse("tasks:quiz_result", args=[self.quiz.uuid]), codes=(200, 302))

    def test_stats_and_the_rest(self):
        self._ok(reverse("tasks:weekly_review"))
        self._ok(reverse("tasks:settings"))
        self._ok(reverse("tasks:profile"))
        self._ok(reverse("tasks:stats_list"))
        for key in ("done", "failed"):  # solo hay estadísticas de lo que ya se resolvió
            self._ok(reverse("tasks:stats_detail", args=[self.tasks[key].series_id]))
        self.assertEqual(self.client.get(reverse("tasks:stats_detail", args=[self.tasks["timer"].series_id])).status_code,
                         302, "sin ninguna ocurrencia, el detalle de estadísticas vuelve a la lista")
        for name in ("challenges_list", "challenge_sally_pushups", "challenge_pullups_100", "challenge_cindy",
                     "routine_create"):
            self._ok(reverse(f"tasks:{name}"))

    # ---- API ----
    def test_api_reads(self):
        for name in ("meta", "profile", "task_list", "plan_list", "stats_list", "weekly_review", "saved_video_list",
                     "routine_list", "plan_language_options", "exercise_list", "plan_udemy_courses", "warmup"):
            self._ok(reverse(f"api:{name}"))
        for key, task in self.tasks.items():
            self._ok(reverse("api:task_detail", args=[task.uuid]))
        for key in ("reading_plan", "reading_free"):
            self._ok(reverse("api:reading_state", args=[self.tasks[key].uuid]))
        for key, plan in self.plans.items():
            self._ok(reverse("api:plan_detail", args=[plan.uuid]))
        for key in ("done", "failed"):
            self._ok(reverse("api:stats_detail", args=[self.tasks[key].series_id]))
        self._ok(reverse("api:stats_detail", args=[self.tasks["timer"].series_id]), codes=(404,))
        self._ok(reverse("api:notify_pending") + f"?series={self.tasks['avoid'].series_id}")
        self._ok(reverse("api:notify_pending") + f"?task={self.tasks['avoid'].uuid}")
        self._ok(reverse("api:notify_pending"), codes=(400,))


# ─────────────────────────────────────────────────────────────────────────────
# Ajustes (peso), estadísticas (borrados) y descarga de la app móvil
# ─────────────────────────────────────────────────────────────────────────────
from pathlib import Path  # noqa: E402

from .models import UserSettings, WeightLog  # noqa: E402


class SettingsPageTests(TestCase):
    def _post(self, value):
        return self.client.post(reverse("tasks:settings"), {"body_weight_kg": value}, follow=True)

    def _weight(self):
        return UserSettings.objects.filter(user=get_current_user()).values_list("body_weight_kg", flat=True).first()

    def test_a_valid_weight_is_saved_with_a_comma_and_logged(self):
        r = self._post("70,5")
        self.assertContains(r, "Peso guardado")
        self.assertEqual(self._weight(), 70.5)
        self.assertEqual(WeightLog.objects.get().weight_kg, 70.5)

    def test_out_of_range_or_garbage_weights_are_refused_and_change_nothing(self):
        self._post("80")
        for bad in ("29", "301", "abc", "-5", "nan", "inf"):
            r = self._post(bad)
            self.assertContains(r, "Pon un peso válido", msg_prefix=bad)
            self.assertEqual(self._weight(), 80.0, bad)

    def test_blank_weight_goes_back_to_the_default(self):
        self._post("80")
        r = self._post("")
        self.assertContains(r, "Peso borrado")
        self.assertIsNone(self._weight())

    def test_same_weight_twice_logs_once(self):
        self._post("80")
        self._post("80")
        self.assertEqual(WeightLog.objects.count(), 1)

    def test_page_shows_the_saved_weight(self):
        self._post("82,5")
        self.assertContains(self.client.get(reverse("tasks:settings")), "82.5")


class StatsDeleteParityTests(TestCase):
    def _build(self):
        user = get_current_user()
        today = timezone.localtime(timezone.now()).date()
        a = Task.objects.create(title="A", due_date=today, repeat=Task.REPEAT_DAILY, user=user)
        b = Task.objects.create(title="B", due_date=today, repeat=Task.REPEAT_DAILY, user=user)
        a.mark_done()
        b.mark_done()
        return a, b

    def test_deleting_one_series_keeps_the_other_and_the_tasks(self):
        for channel in ("web", "api"):
            Task.all_objects.all().delete()
            Occurrence.objects.all().delete()
            a, b = self._build()
            if channel == "web":
                r = self.client.post(reverse("tasks:stats_delete_series", args=[a.series_id]))
                self.assertEqual(r.status_code, 302)
            else:
                r = self.client.delete(reverse("api:stats_delete_series", args=[a.series_id]))
                self.assertEqual(r.status_code, 200)
            self.assertEqual(Occurrence.objects.filter(series_id=a.series_id).count(), 0, channel)
            self.assertEqual(Occurrence.objects.filter(series_id=b.series_id).count(), 1, channel)
            self.assertTrue(Task.objects.filter(series_id=a.series_id).exists(), "borrar estadísticas no borra tareas")

    def test_deleting_everything(self):
        for channel in ("web", "api"):
            Task.all_objects.all().delete()
            Occurrence.objects.all().delete()
            self._build()
            if channel == "web":
                self.client.post(reverse("tasks:stats_delete_all"))
            else:
                self.client.delete(reverse("api:stats_delete_all"))
            self.assertEqual(Occurrence.objects.count(), 0, channel)

    def test_deletes_need_the_right_http_method(self):
        a, _ = self._build()
        self.assertEqual(self.client.get(reverse("tasks:stats_delete_all")).status_code, 405)
        self.assertEqual(self.client.get(reverse("tasks:stats_delete_series", args=[a.series_id])).status_code, 405)
        self.assertEqual(self.client.get(reverse("api:stats_delete_all")).status_code, 405)
        self.assertEqual(Occurrence.objects.count(), 2)

    def test_stats_pages_after_deleting_do_not_break(self):
        a, _ = self._build()
        self.client.post(reverse("tasks:stats_delete_series", args=[a.series_id]))
        self.assertEqual(self.client.get(reverse("tasks:stats_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("api:stats_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("tasks:stats_detail", args=[a.series_id])).status_code, 302)


class MobileUpdateTests(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        patcher = mock.patch("tasks.utils.MOBILE_RELEASES_DIR", self.tmp)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _publish(self, version="7", apk="libreta-v7.apk", write_apk=True, notes="Mejoras"):
        (self.tmp / "latest.json").write_text(
            json.dumps({"version": version, "apk_filename": apk, "notes": notes}), encoding="utf-8")
        if write_apk:
            (self.tmp / Path(apk).name).write_bytes(b"PK\x03\x04 apk")

    def test_without_a_published_build_nothing_is_announced_and_the_download_is_404(self):
        self.assertNotIn("mobile_app", self.client.get(reverse("api:meta")).json())
        self.assertEqual(self.client.get(reverse("mobile_apk_download")).status_code, 404)

    def test_a_published_build_is_announced_and_downloadable(self):
        self._publish()
        info = self.client.get(reverse("api:meta")).json()["mobile_app"]
        self.assertEqual((info["version"], info["download_url"], info["notes"]),
                         ("7", reverse("mobile_apk_download"), "Mejoras"))
        r = self.client.get(info["download_url"])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/vnd.android.package-archive")
        self.assertIn("libreta-v7.apk", r["Content-Disposition"])
        self.assertEqual(b"".join(r.streaming_content), b"PK\x03\x04 apk")

    def test_only_get_is_allowed(self):
        self._publish()
        self.assertEqual(self.client.post(reverse("mobile_apk_download")).status_code, 405)

    def test_a_release_that_points_to_a_missing_or_foreign_file_is_ignored(self):
        self._publish(write_apk=False)
        self.assertNotIn("mobile_app", self.client.get(reverse("api:meta")).json())
        outside = self.tmp.parent / f"secreto-{self.tmp.name}.txt"   # FUERA de mobile_releases/
        outside.write_text("no", encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        self._publish(apk=f"../{outside.name}", write_apk=False)
        r = self.client.get(reverse("mobile_apk_download"))
        self.assertEqual(r.status_code, 404, "una ruta con .. no puede sacar archivos de mobile_releases/")

    def test_broken_or_incomplete_latest_json_is_ignored(self):
        (self.tmp / "latest.json").write_text("{no es json", encoding="utf-8")
        self.assertNotIn("mobile_app", self.client.get(reverse("api:meta")).json())
        (self.tmp / "latest.json").write_text(json.dumps({"version": "", "apk_filename": "x.apk"}), encoding="utf-8")
        self.assertNotIn("mobile_app", self.client.get(reverse("api:meta")).json())


# ─────────────────────────────────────────────────────────────────────────────
# Playlist: por dónde vas se guarda MIENTRAS ves (web y app), no se pierde al
# editar el plan, y Lectura nunca abre un vídeo.
# ─────────────────────────────────────────────────────────────────────────────
def _fake_cache(n):
    return [{"video_id": f"v{i:010d}", "duration_seconds": 300} for i in range(n)]


class PlaylistPositionTests(TestCase):
    """Antes la posición solo se guardaba al TERMINAR la sesión entera: cerrar a
    medias, o ver más vídeos de los que pedía el objetivo, hacía volver a empezar
    por donde empezó el día."""

    CHANNELS = ("web", "api")

    def _loose(self, n=6, **kw):
        base = dict(
            title="Curso", category=Task.CATEGORY_STUDY, youtube_playlist_id="PLabcdefghijklmnop",
            target_video_count=2, due_date=date.today(), repeat=Task.REPEAT_DAILY, user=get_current_user(),
            playlist_videos_cache=_fake_cache(n),
        )
        base.update(kw)
        return Task.objects.create(**base)

    def _plan(self, n_videos=6, **item_fields):
        with _fake_playlist(n_videos):
            self.client.post(reverse("tasks:plan_create"), _study_post(**item_fields))
        return Plan.objects.get()

    def _pending(self, plan):
        self.client.get(reverse("tasks:task_list"))  # lo que hace la lista al abrirse: sync_all_tasks
        return Task.objects.get(series_id=plan.task_series_id, is_done=False)

    def _ping(self, task, index, channel):
        if channel == "web":
            return _post_json(self.client, reverse("tasks:task_video_position", args=[task.pk]), {"index": index})
        return _post_json(self.client, reverse("api:video_position", args=[task.uuid]), {"index": index})

    def _finish(self, task, channel, **body):
        if channel == "web":
            return _post_json(self.client, reverse("tasks:task_video_save", args=[task.pk]), body)
        return _post_json(self.client, reverse("api:video_save", args=[task.uuid]), body)

    def _next_pending(self, task):
        return Task.objects.get(series_id=task.series_id, is_done=False)

    # -- tarea suelta ---------------------------------------------------------
    def test_the_position_is_saved_and_the_player_opens_there(self):
        for channel in self.CHANNELS:
            with self.subTest(channel=channel):
                Task.all_objects.all().delete()
                t = self._loose()
                r = self._ping(t, 3, channel)
                self.assertEqual(r.status_code, 200, r.content)
                self.assertEqual(r.json(), {"ok": True, "index": 3})
                t.refresh_from_db()
                self.assertEqual(t.playlist_start_index, 3)
                if channel == "web":
                    page = self.client.get(reverse("tasks:task_video", args=[t.pk]))
                    self.assertContains(page, "var playlistStartIndex = 3;")
                else:
                    data = self.client.get(reverse("api:task_detail", args=[t.uuid])).json()["task"]
                    self.assertEqual(data["playlist_start_index"], 3)

    def test_the_last_position_wins_when_you_skip_around(self):
        for channel in self.CHANNELS:
            with self.subTest(channel=channel):
                Task.all_objects.all().delete()
                t = self._loose()
                for idx in (0, 1, 2, 1):
                    self._ping(t, idx, channel)
                t.refresh_from_db()
                self.assertEqual(t.playlist_start_index, 1)

    def test_a_position_past_the_end_means_the_list_is_seen(self):
        for channel in self.CHANNELS:
            with self.subTest(channel=channel):
                Task.all_objects.all().delete()
                t = self._loose(n=6)
                self.assertEqual(self._ping(t, 99, channel).json()["index"], 6)
                t.refresh_from_db()
                self.assertEqual(t.playlist_start_index, 5, "el reproductor nunca abre por un vídeo que no existe")

    def test_garbage_positions_are_a_clean_400_and_change_nothing(self):
        self.client.raise_request_exception = False
        for channel in self.CHANNELS:
            t = self._loose(playlist_start_index=2)
            for bad in (-1, "2", None, True, [], {}, 1e999):
                with self.subTest(channel=channel, bad=bad):
                    r = self._ping(t, bad, channel)
                    self.assertEqual(r.status_code, 400, f"{bad!r} → {r.status_code}")
            url = (reverse("tasks:task_video_position", args=[t.pk]) if channel == "web"
                   else reverse("api:video_position", args=[t.uuid]))
            for raw in ('{"index": NaN}', "no es json", "[]", ""):
                with self.subTest(channel=channel, raw=raw):
                    r = self.client.post(url, data=raw, content_type="application/json")
                    self.assertEqual(r.status_code, 400, f"{raw!r} → {r.status_code}")
            t.refresh_from_db()
            self.assertEqual(t.playlist_start_index, 2)

    def test_a_task_without_playlist_has_no_position(self):
        for channel in self.CHANNELS:
            with self.subTest(channel=channel):
                t = Task.objects.create(title="Vídeo", category=Task.CATEGORY_STUDY, youtube_video_id="dQw4w9WgXcQ",
                                        due_date=date.today(), user=get_current_user())
                self.assertEqual(self._ping(t, 1, channel).status_code, 400)
                t.refresh_from_db()
                self.assertIsNone(t.playlist_start_index)

    def test_finishing_counts_from_where_the_session_started_not_from_the_saved_position(self):
        """El reproductor ya fue guardando 0, 1, 2: contar los 2 vídeos vistos desde
        la guardada daría 4 (se saltaría vídeos)."""
        for channel in self.CHANNELS:
            with self.subTest(channel=channel):
                Task.all_objects.all().delete()
                t = self._loose(target_video_count=2)
                for idx in (0, 1, 2):
                    self._ping(t, idx, channel)
                r = self._finish(t, channel, minutes=10, videos_watched=2, playlist_start=0)
                self.assertEqual(r.status_code, 200, r.content)
                self.assertEqual(self._next_pending(t).playlist_start_index, 2)

    def test_an_old_client_without_playlist_start_still_advances_as_before(self):
        for channel in self.CHANNELS:
            with self.subTest(channel=channel):
                Task.all_objects.all().delete()
                t = self._loose(target_video_count=2, playlist_start_index=1)
                self._finish(t, channel, minutes=10, videos_watched=2)
                self.assertEqual(self._next_pending(t).playlist_start_index, 3)

    def test_watching_the_last_video_closes_the_series(self):
        for channel in self.CHANNELS:
            with self.subTest(channel=channel):
                Task.all_objects.all().delete()
                t = self._loose(n=3, target_video_count=2, playlist_start_index=1)
                self._ping(t, 3, channel)           # acabó el último vídeo
                r = self._finish(t, channel, minutes=10, videos_watched=2, playlist_start=1)
                self.assertEqual(r.status_code, 200, r.content)
                self.assertEqual(Task.objects.filter(series_id=t.series_id, is_done=False).count(), 0,
                                 "con la lista entera vista no debe quedar tarea pendiente")

    def test_changing_the_playlist_of_a_loose_task_starts_it_over(self):
        t = self._loose(playlist_start_index=3)
        url = reverse("api:task_detail", args=[t.uuid])
        with _fake_playlist(4):
            r = _patch_json(self.client, url, {"title": "Otro título"})
            self.assertEqual(r.status_code, 200, r.content)
            t.refresh_from_db()
            self.assertEqual(t.playlist_start_index, 3, "editar otra cosa no reinicia la lista")
            r = _patch_json(self.client, url, {"youtube_playlist_id": "PLzzzzzzzzzzzzzz"})
            self.assertEqual(r.status_code, 200, r.content)
        t.refresh_from_db()
        self.assertIsNone(t.playlist_start_index, "otra playlist empieza por el principio")
        self.assertEqual(t.youtube_playlist_id, "PLzzzzzzzzzzzzzz")

    # -- tarea de un plan -----------------------------------------------------
    def test_closing_midway_keeps_the_place_in_a_plan(self):
        for channel in self.CHANNELS:
            with self.subTest(channel=channel):
                Plan.objects.all().delete()
                Task.all_objects.all().delete()
                plan = self._plan(target_video_count="2")
                task = self._pending(plan)
                self.assertEqual(task.playlist_start_index, 0)
                self.assertEqual(self._ping(task, 1, channel).status_code, 200)
                self.assertEqual(plan.items.get().playlist_position, 1)
                # Lo que hace la lista al abrirse (sync_all_tasks) NO debe pisarlo.
                self.assertEqual(self._pending(plan).playlist_start_index, 1)
                self.assertFalse(Occurrence.objects.exists(), "cerrar a medias no cumple el día")

    def test_watching_more_than_the_goal_asks_moves_the_start_further(self):
        for channel in self.CHANNELS:
            with self.subTest(channel=channel):
                Plan.objects.all().delete()
                Task.all_objects.all().delete()
                Occurrence.objects.all().delete()
                plan = self._plan(target_video_count="2")
                task = self._pending(plan)
                for idx in (0, 1, 2, 3):
                    self._ping(task, idx, channel)
                r = self._finish(task, channel, minutes=20, videos_watched=3, playlist_start=0)
                self.assertEqual(r.status_code, 200, r.content)
                self.assertEqual(self._pending(plan).playlist_start_index, 3,
                                 "vio 3 vídeos: mañana toca el cuarto (antes volvía al tercero)")

    def test_finishing_the_whole_list_closes_the_plan(self):
        for channel in self.CHANNELS:
            with self.subTest(channel=channel):
                Plan.objects.all().delete()
                Task.all_objects.all().delete()
                Occurrence.objects.all().delete()
                plan = self._plan(n_videos=3, target_video_count="2")
                task = self._pending(plan)
                self._finish(task, channel, minutes=15, videos_watched=3, playlist_start=0)
                plan.refresh_from_db()
                self.assertIsNotNone(plan.closed_at)

    def test_saving_the_plan_again_keeps_the_place_but_a_new_playlist_restarts(self):
        plan = self._plan(target_video_count="2")
        task = self._pending(plan)
        self._ping(task, 3, "web")
        item = plan.items.get()
        synced_at = item.playlist_synced_at
        self.assertEqual(item.playlist_cache_id, "PLabcdefghijklmnop")
        with _fake_playlist(6):
            r = self.client.post(reverse("tasks:plan_edit", args=[plan.pk]), _study_post(target_video_count="2"))
            self.assertEqual(r.status_code, 302, r.content)
        item.refresh_from_db()
        self.assertEqual(item.playlist_position, 3, "volver a guardar el plan no debe reiniciar la playlist")
        self.assertEqual(item.playlist_synced_at, synced_at)
        self.assertEqual(self._pending(plan).playlist_start_index, 3)
        with _fake_playlist(6):
            r = self.client.post(reverse("tasks:plan_edit", args=[plan.pk]),
                                 _study_post(target_video_count="2", youtube_playlist_id="PLzzzzzzzzzzzzzz"))
            self.assertEqual(r.status_code, 302, r.content)
        item.refresh_from_db()
        self.assertIsNone(item.playlist_position, "otra playlist empieza por el principio")
        self.assertEqual(item.playlist_cache_id, "PLzzzzzzzzzzzzzz")
        self.assertGreater(item.playlist_synced_at, synced_at)
        self.assertEqual(self._pending(plan).playlist_start_index, 0)

    def test_objectives_synced_before_this_change_do_not_restart_on_the_first_save(self):
        """Un objetivo que ya tenía caché (migración 0123 le pone su playlist en
        playlist_cache_id) no pierde el avance en el primer guardado."""
        plan = self._plan(target_video_count="2")
        item = plan.items.get()
        old = item.playlist_synced_at
        PlanItem.objects.filter(pk=item.pk).update(playlist_cache_id="")  # como antes de la migración
        from django.db.migrations.executor import MigrationExecutor
        from django.db import connection
        migration = MigrationExecutor(connection).loader.get_migration("tasks", "0123_planitem_playlist_position")
        fill = [op for op in migration.operations if op.__class__.__name__ == "RunPython"][0].code
        from django.apps import apps
        fill(apps, None)
        item.refresh_from_db()
        self.assertEqual(item.playlist_cache_id, "PLabcdefghijklmnop")
        with _fake_playlist(6):
            item.sync_playlist_videos()
        item.refresh_from_db()
        self.assertEqual(item.playlist_synced_at, old)

    def test_removing_the_playlist_clears_the_progress(self):
        plan = self._plan(target_video_count="2")
        self._ping(self._pending(plan), 2, "api")
        item = plan.items.get()
        item.youtube_playlist_id = ""
        item.save()
        item.sync_playlist_videos()
        item.refresh_from_db()
        self.assertEqual((item.playlist_videos_cache, item.playlist_position, item.playlist_cache_id, item.playlist_synced_at),
                         ([], None, "", None))

    def test_ping_of_a_task_whose_plan_has_another_playlist_is_not_stored_in_the_plan(self):
        plan = self._plan(target_video_count="2")
        task = self._pending(plan)
        Task.objects.filter(pk=task.pk).update(youtube_playlist_id="PLotralistaotralis")
        task.refresh_from_db()
        self._ping(task, 2, "web")
        self.assertIsNone(plan.items.get().playlist_position)


class LecturaNeverOpensAVideoTests(TestCase):
    """Lectura no lleva vídeo (eran de las tareas de Enfoque, que ya no existen):
    una tarea vieja de esa categoría que aún conserve uno no debe seguir abriendo
    YouTube."""

    def _legacy(self, **kw):
        base = dict(title="Antigua", category=Task.CATEGORY_WORK, subcategory=Task.SUBCATEGORY_READING,
                    due_date=date.today(), user=get_current_user())
        base.update(kw)
        return Task.objects.create(**base)

    def test_a_reading_task_with_a_leftover_video_opens_the_timer(self):
        cases = {
            "vídeo": dict(youtube_video_id="dQw4w9WgXcQ"),
            "playlist": dict(youtube_playlist_id="PLabcdefghijklmnop"),
            "archivo local": dict(has_local_video=True),
        }
        for label, kw in cases.items():
            with self.subTest(label):
                Task.all_objects.all().delete()
                t = self._legacy(**kw)
                self.assertEqual(t.workout_kind, "focus")
                page = self.client.get(reverse("tasks:task_list") + "?range=all")
                self.assertContains(page, reverse("tasks:task_focus", args=[t.pk]))
                self.assertNotContains(page, reverse("tasks:task_video", args=[t.pk]))
                data = self.client.get(reverse("api:task_detail", args=[t.uuid])).json()["task"]
                self.assertEqual(data["workout_kind"], "focus")

    def test_study_and_sport_videos_are_untouched(self):
        study = Task.objects.create(title="Vídeo", category=Task.CATEGORY_STUDY, youtube_video_id="dQw4w9WgXcQ",
                                    due_date=date.today(), user=get_current_user())
        self.assertEqual(study.workout_kind, "video")
        sport = Task.objects.create(title="Rutina", category=Task.CATEGORY_SPORT,
                                    subcategory=Task.SUBCATEGORY_UPPER_BODY, sport_mode=Task.SPORT_MODE_VIDEO,
                                    youtube_video_id="dQw4w9WgXcQ", due_date=date.today(), user=get_current_user())
        self.assertEqual(sport.workout_kind, "video")

    def test_a_reading_plan_and_a_keyword_reading_keep_their_own_screens(self):
        plan = self._legacy(reading_mode=Task.READING_MODE_PLAN, reading_first_page=1, reading_last_page=100,
                            reading_target_weeks=4, reading_started_on=date.today())
        self.assertEqual(plan.workout_kind, "reading")
        kw = self._legacy(title="Con palabra", watch_keyword="clean-code", target_minutes=20)
        self.assertEqual(kw.workout_kind, "auto")
