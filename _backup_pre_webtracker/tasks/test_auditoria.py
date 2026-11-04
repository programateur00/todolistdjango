"""
Tests de regresión de la auditoría de octubre 2026: cada uno cubre algo que
la app DECÍA hacer y no hacía. Ver los comentarios de cada caso.
"""
import json
import uuid as uuid_mod
from datetime import date

from django.test import TestCase
from django.urls import reverse

from .models import CourseModule, Plan, PlanItem, Task, TimerSession
from .utils import get_current_user


def _spawned(task):
    return Task.objects.exclude(pk=task.pk).get(series_id=task.series_id)


class RepeatKeepsFieldsTests(TestCase):
    """Al marcar hecha una tarea que se repite, la del día siguiente nace
    como copia: antes perdía campos que el usuario había configurado."""

    def _daily(self, **kw):
        return Task.objects.create(
            title="Repite", due_date=date.today(), repeat=Task.REPEAT_DAILY,
            user=get_current_user(), **kw,
        )

    def test_general_task_keeps_its_timer(self):
        t = self._daily(category=Task.CATEGORY_GENERAL, wants_timer=True)
        self.assertEqual(t.workout_kind, "focus")
        t.mark_done()
        nxt = _spawned(t)
        self.assertTrue(nxt.wants_timer)
        self.assertEqual(nxt.workout_kind, "focus")

    def test_language_task_keeps_language_and_level(self):
        t = self._daily(
            category=Task.CATEGORY_STUDY, subcategory=Task.SUBCATEGORY_LANGUAGE,
            language_name="Alemán", level="B1", youtube_video_id="dQw4w9WgXcQ",
        )
        t.mark_done()
        nxt = _spawned(t)
        self.assertEqual(nxt.language_name, "Alemán")
        self.assertEqual(nxt.level, "B1")

    def test_course_keeps_watch_mode(self):
        t = self._daily(
            category=Task.CATEGORY_STUDY, subcategory=Task.SUBCATEGORY_UDEMY,
            watch_keyword="Excel", watch_requires_audio=False, target_minutes=30,
        )
        t.mark_done()
        self.assertFalse(_spawned(t).watch_requires_audio)

    def test_reading_seconds_not_yet_flushed_are_carried_over(self):
        t = self._daily(
            category=Task.CATEGORY_WORK, subcategory=Task.SUBCATEGORY_READING,
            reading_pending_seconds=45,
        )
        t.mark_done()
        self.assertEqual(_spawned(t).reading_pending_seconds, 45)


class UdemyNeedsMinutesTests(TestCase):
    """Sin minutos al día, focus_save daba el día por cumplido con la primera
    sesión de 1 minuto (Ilerna ya lo exigía; Udemy no)."""

    def test_one_minute_closes_a_udemy_day_without_target_is_no_longer_creatable(self):
        r = self.client.post(reverse("tasks:task_create"), {
            "title": "Udemy sin objetivo", "category": "study", "subcategory": "udemy",
            "due_date": "2026-09-10", "due_time": "20:00", "repeat": "daily",
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Task.objects.filter(title="Udemy sin objetivo").exists())

    def test_web_create_with_minutes_still_works(self):
        r = self.client.post(reverse("tasks:task_create"), {
            "title": "Udemy con objetivo", "category": "study", "subcategory": "udemy",
            "target_minutes": "30", "due_date": "2026-09-10", "due_time": "20:00", "repeat": "daily",
        })
        self.assertEqual(r.status_code, 302, r.content)
        self.assertEqual(Task.objects.get(title="Udemy con objetivo").target_minutes, 30)

    def test_api_create_without_minutes_is_rejected(self):
        r = self.client.post(
            reverse("api:task_create"),
            data=json.dumps({"title": "Udemy API", "category": "study", "subcategory": "udemy"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("minutos", r.json()["error"])

    def test_plan_with_udemy_course_needs_minutes(self):
        r = self.client.post(reverse("tasks:plan_create"), {
            "plan_type": "study", "study_subtype": "general", "is_active": "on",
            "name": "Curso Excel", "study_source": "udemy", "watch_keyword": "Excel",
            "due_time": "20:00", "repeat": "daily", "custom_days": ["0", "2", "4"], "weeks": "8",
        })
        # Error de validación: vuelve al formulario y NO se guarda nada (ni el
        # plan ni su tarea diaria).
        self.assertEqual(r.status_code, 200)
        self.assertFalse(PlanItem.objects.filter(watch_keyword="Excel").exists())
        self.assertFalse(Plan.objects.filter(name="Curso Excel").exists())
        self.assertFalse(Task.objects.filter(title="Curso Excel").exists())

    def test_plan_with_udemy_course_and_minutes_is_created(self):
        r = self.client.post(reverse("tasks:plan_create"), {
            "plan_type": "study", "study_subtype": "general", "is_active": "on",
            "name": "Curso Excel", "study_source": "udemy", "watch_keyword": "Excel",
            "target_minutes": "40", "due_time": "20:00", "repeat": "daily",
            "custom_days": ["0", "2", "4"], "weeks": "8",
        })
        self.assertEqual(r.status_code, 302)
        item = PlanItem.objects.get(watch_keyword="Excel")
        self.assertEqual(item.target_minutes, 40)

    def test_extension_session_below_target_does_not_close_the_day(self):
        t = Task.objects.create(
            title="Curso", category=Task.CATEGORY_STUDY, subcategory=Task.SUBCATEGORY_UDEMY,
            target_minutes=30, due_date=date.today(), repeat=Task.REPEAT_DAILY, user=get_current_user(),
        )
        post = lambda m: self.client.post(
            reverse("api:focus_save", args=[t.uuid]),
            data=json.dumps({"minutes": m, "source": "pc_usage", "app_package": "udemy.com"}),
            content_type="application/json",
        )
        post(1)
        t.refresh_from_db()
        self.assertFalse(t.is_done)
        post(29)
        t.refresh_from_db()
        self.assertTrue(t.is_done)


class VideoSaveParityTests(TestCase):
    """api.video_save (móvil) tiene que hacer lo mismo que
    views.task_video_save (web)."""

    def _post(self, task, **body):
        return self.client.post(
            reverse("api:video_save", args=[task.uuid]),
            data=json.dumps(body), content_type="application/json",
        )

    def _study(self, **kw):
        return Task.objects.create(
            title="Estudio", category=Task.CATEGORY_STUDY, due_date=date.today(),
            repeat=Task.REPEAT_DAILY, user=get_current_user(), **kw,
        )

    def test_standalone_single_video_closes_the_series(self):
        t = self._study(youtube_video_id="dQw4w9WgXcQ")
        r = self._post(t, minutes=5, videos_watched=1)
        self.assertEqual(r.status_code, 200, r.content)
        t.refresh_from_db()
        self.assertTrue(t.is_done)
        self.assertEqual(t.repeat, Task.REPEAT_NONE)
        self.assertEqual(Task.objects.filter(series_id=t.series_id).count(), 1)

    def test_standalone_playlist_advances_by_videos_watched(self):
        t = self._study(youtube_playlist_id="PLabcdefghijklmnop", target_video_count=2)
        t.playlist_videos_cache = [{"id": f"v{i:010d}"} for i in range(6)]
        t.save()
        r = self._post(t, videos_watched=2)
        self.assertEqual(r.status_code, 200, r.content)
        nxt = _spawned(t)
        self.assertEqual(nxt.playlist_start_index, 2)
        self.assertNotEqual(nxt.repeat, Task.REPEAT_NONE)

    def test_standalone_playlist_closes_on_last_video(self):
        t = self._study(youtube_playlist_id="PLabcdefghijklmnop", target_video_count=2)
        t.playlist_videos_cache = [{"id": f"v{i:010d}"} for i in range(4)]
        t.playlist_start_index = 2
        t.save()
        self._post(t, videos_watched=2)
        t.refresh_from_db()
        self.assertEqual(t.repeat, Task.REPEAT_NONE)
        self.assertEqual(Task.objects.filter(series_id=t.series_id).count(), 1)

    # ------------------------------------------------------ curso de idioma

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
        return plan, Task.objects.get(series_id=plan.task_series_id)

    def test_task_detail_exposes_the_course_queue_for_language_plans(self):
        plan, task = self._language_plan()
        r = self.client.get(reverse("api:task_detail", args=[task.uuid]))
        queue = r.json()["task"]["course_queue"]
        self.assertEqual(len(queue), 5)
        self.assertEqual(queue[0]["video_id"], "vid00000000")

    def test_task_detail_has_empty_queue_for_other_tasks(self):
        t = self._study(youtube_video_id="dQw4w9WgXcQ")
        r = self.client.get(reverse("api:task_detail", args=[t.uuid]))
        self.assertEqual(r.json()["task"]["course_queue"], [])

    def test_language_video_save_advances_as_many_modules_as_watched(self):
        plan, task = self._language_plan()
        r = self._post(task, minutes=15, videos_watched=3)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(plan.course_modules.filter(watched_at__isnull=False).count(), 3)

    def test_language_video_save_with_zero_videos_does_not_eat_a_half_watched_one(self):
        plan, task = self._language_plan()
        self._post(task, minutes=10, videos_watched=0)
        self.assertEqual(plan.course_modules.filter(watched_at__isnull=False).count(), 0)

    def test_language_video_save_without_count_advances_one(self):
        plan, task = self._language_plan()
        self._post(task, minutes=5)
        self.assertEqual(plan.course_modules.filter(watched_at__isnull=False).count(), 1)

    def test_finishing_the_last_module_closes_the_plan_right_away(self):
        plan, task = self._language_plan(modules=2)
        self._post(task, minutes=10, videos_watched=2)
        plan.refresh_from_db()
        self.assertIsNotNone(plan.closed_at)

    def test_sport_video_still_needs_the_cooldown(self):
        t = Task.objects.create(
            title="Rutina", category=Task.CATEGORY_SPORT, youtube_video_id="dQw4w9WgXcQ",
            user=get_current_user(),
        )
        r = self._post(t, minutes=20)
        self.assertTrue(r.json().get("needs_cooldown"))
        t.refresh_from_db()
        self.assertFalse(t.is_done)


class LanguageQuizTriggerTests(TestCase):
    """El test de repaso cada N vídeos tiene que salir aunque una sesión
    encadene varios vídeos y se salte el múltiplo exacto de N."""

    def _plan(self, n_every=3, modules=9):
        plan = Plan.objects.create(
            user=get_current_user(), name="Alemán", plan_type=Plan.PLAN_TYPE_STUDY,
            study_subtype=Plan.STUDY_SUBTYPE_LANGUAGE, language_name="Alemán",
            level_from="A1", level_to="A2", language_daily_minutes=30, weeks=8,
            quiz_every_n_videos=n_every, repeat="daily", started_on=date.today(),
        )
        for i in range(modules):
            CourseModule.objects.create(
                plan=plan, order=i, level="A1", youtube_video_id=f"vid{i:08d}",
                title=f"Tema {i}", duration_seconds=300,
            )
        return plan

    def _run(self, plan, watched_now):
        from unittest import mock
        from . import api
        plan.mark_current_module_watched(count=watched_now)
        fake = {"questions": [{"question": "?", "options": ["a", "b", "c", "d"], "correct_index": 0}]}
        with mock.patch.object(api.ai, "generate_quiz", return_value=fake) as gen:
            quiz = api.maybe_trigger_quiz(plan)
        return quiz, gen

    def test_quiz_on_exact_multiple(self):
        plan = self._plan()
        quiz, _ = self._run(plan, 3)
        self.assertIsNotNone(quiz)
        self.assertEqual(quiz.up_to_order, 2)
        self.assertEqual(quiz.topics, ["Tema 0", "Tema 1", "Tema 2"])

    def test_no_quiz_before_the_first_block_is_complete(self):
        plan = self._plan()
        quiz, gen = self._run(plan, 2)
        self.assertIsNone(quiz)
        gen.assert_not_called()

    def test_quiz_when_a_session_jumps_over_the_multiple(self):
        plan = self._plan()
        self._run(plan, 2)
        quiz, _ = self._run(plan, 2)  # 2 -> 4 vistos: se cruzó el 3
        self.assertIsNotNone(quiz)
        self.assertEqual(quiz.up_to_order, 2)

    def test_no_duplicate_quiz_for_the_same_block(self):
        plan = self._plan()
        self._run(plan, 3)
        quiz, gen = self._run(plan, 1)  # 4 vistos: mismo tramo ya cubierto
        self.assertIsNone(quiz)
        gen.assert_not_called()
        self.assertEqual(plan.quizzes.count(), 1)

    def test_second_block_gets_its_own_quiz(self):
        plan = self._plan()
        self._run(plan, 3)
        quiz, _ = self._run(plan, 3)
        self.assertIsNotNone(quiz)
        self.assertEqual(quiz.up_to_order, 5)
        self.assertEqual(plan.quizzes.count(), 2)


class MobileDeleteRespectedByWebTests(TestCase):
    """Borrar una tarea desde la app es un borrado suave (deleted_at). La
    web, las estadísticas y el cierre de vencidas tienen que respetarlo."""

    def _task(self, **kw):
        defaults = dict(title="Borrame", due_date=date.today(), repeat=Task.REPEAT_DAILY,
                        user=get_current_user())
        defaults.update(kw)
        return Task.objects.create(**defaults)

    def test_task_deleted_from_the_app_disappears_from_the_web_list(self):
        t = self._task()
        r = self.client.delete(reverse("api:task_detail", args=[t.uuid]))
        self.assertEqual(r.status_code, 200)
        page = self.client.get(reverse("tasks:task_list") + "?range=all")
        self.assertNotContains(page, "Borrame")

    def test_task_deleted_from_the_app_is_not_expired_into_a_missed_day(self):
        from datetime import timedelta
        t = self._task(due_date=date.today() - timedelta(days=2), due_time=None)
        self.client.delete(reverse("api:task_detail", args=[t.uuid]))
        Task.expire_overdue()
        from .models import Occurrence
        self.assertEqual(Occurrence.objects.filter(series_id=t.series_id).count(), 0)
        self.assertEqual(Task.all_objects.filter(series_id=t.series_id).count(), 1)  # no se generó ninguna más

    def test_deleting_a_reading_plan_day_from_the_app_keeps_the_plan_going(self):
        t = self._task(
            title="Libro", category=Task.CATEGORY_WORK, subcategory=Task.SUBCATEGORY_READING,
            reading_mode=Task.READING_MODE_PLAN, reading_first_page=1, reading_last_page=300,
            reading_target_weeks=10, reading_started_on=date.today(),
        )
        self.client.delete(reverse("api:task_detail", args=[t.uuid]))
        self.assertEqual(Task.objects.filter(series_id=t.series_id, is_done=False).count(), 1)


class ReopenAndStreakOrderTests(TestCase):
    """Reabrir una tarea ANTIGUA (desde Esta semana / Este mes / Todas) no
    puede llevarse por delante la pendiente de hoy, y la racha se cuenta
    por día, no por cuándo se escribió cada fila."""

    def test_reopening_an_old_task_does_not_delete_todays_pending(self):
        import datetime as dt
        from unittest import mock
        from django.utils import timezone

        clock = [timezone.make_aware(dt.datetime(2026, 3, 2, 8, 0))]
        with mock.patch("django.utils.timezone.now", lambda: clock[0]):
            t = Task.objects.create(
                title="Habito", due_date=dt.date(2026, 3, 2), repeat=Task.REPEAT_DAILY,
                user=get_current_user(),
            )
            t.mark_done()                                    # lunes hecha -> martes
            clock[0] = timezone.make_aware(dt.datetime(2026, 3, 4, 10, 0))
            Task.expire_overdue()                            # martes caduca -> miércoles pendiente
            wed = Task.objects.get(series_id=t.series_id, is_done=False)
            self.assertEqual(wed.due_date, dt.date(2026, 3, 4))
            self.client.post(reverse("tasks:task_reopen", args=[t.pk]))  # reabre el del lunes
            self.assertTrue(
                Task.objects.filter(series_id=t.series_id, due_date=dt.date(2026, 3, 4), is_done=False).exists(),
                "la pendiente de hoy desapareció",
            )
            t.refresh_from_db()
            t.mark_done()  # vuelve a marcarlo
            self.assertTrue(Task.objects.filter(series_id=t.series_id, is_done=False).exists())
            dups = Task.objects.filter(series_id=t.series_id, is_done=False, due_date=dt.date(2026, 3, 4)).count()
            self.assertEqual(dups, 1)

    def test_streak_follows_calendar_days_not_row_creation_order(self):
        import datetime as dt
        from .models import Occurrence
        sid = uuid_mod.uuid4()
        user = get_current_user()
        # Se escriben en orden "raro": el día 3 primero, luego los demás.
        for day, result in ((3, "done"), (1, "done"), (2, "not_done")):
            Occurrence.objects.create(
                series_id=sid, title="X", result=result, user=user,
                due_date=dt.date(2026, 3, day),
            )
        st = Occurrence.streak_stats(sid)
        self.assertEqual(st["current_streak"], 1)  # el día más reciente (3) es 'hecho'
        self.assertEqual(st["max_streak"], 1)


class MonthlyYearlyAnchorTests(TestCase):
    """Una tarea 'el 31 de cada mes' no puede quedarse para siempre en el 28."""

    def _chain(self, start, repeat, n):
        out, d = [start], start
        for _ in range(n):
            t = Task(due_date=d, repeat=repeat, interval=1, series_start_date=start)
            d = t.next_due_date()
            out.append(d)
        return out

    def test_monthly_on_the_31st_comes_back_to_the_31st(self):
        got = self._chain(date(2026, 1, 31), Task.REPEAT_MONTHLY, 5)
        self.assertEqual(got, [
            date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31),
            date(2026, 4, 30), date(2026, 5, 31), date(2026, 6, 30),
        ])

    def test_yearly_on_feb_29_returns_in_leap_years(self):
        got = self._chain(date(2024, 2, 29), Task.REPEAT_YEARLY, 4)
        self.assertEqual(got, [
            date(2024, 2, 29), date(2025, 2, 28), date(2026, 2, 28),
            date(2027, 2, 28), date(2028, 2, 29),
        ])

    def test_a_date_the_user_picked_on_purpose_is_respected(self):
        # Empezó el 15 y el usuario movió una instancia al 20: sigue el 20.
        t = Task(due_date=date(2026, 3, 20), repeat=Task.REPEAT_MONTHLY, interval=1,
                 series_start_date=date(2026, 1, 15))
        self.assertEqual(t.next_due_date(), date(2026, 4, 20))


class EditingARecurringTaskReanchorsItTests(TestCase):
    """Cambiar la repetición de una tarea la re-ancla a la fecha nueva."""

    def _biweekly(self):
        # Serie original: lunes 2-mar, cada 2 semanas (martes y jueves).
        return Task.objects.create(
            title="Quincenal", due_date=date(2026, 3, 2), repeat=Task.REPEAT_CUSTOM,
            custom_days="1,3", interval=2, user=get_current_user(),
        )

    def test_web_edit_moves_the_anchor(self):
        t = self._biweekly()
        r = self.client.post(reverse("tasks:task_edit", args=[t.pk]), {
            "title": "Quincenal", "repeat": "custom", "interval": "2",
            "due_date": "2026-03-10", "due_time": "20:00", "custom_days": ["1", "3"],
        })
        self.assertEqual(r.status_code, 302, r.content[:300])
        t.refresh_from_db()
        self.assertEqual(t.series_start_date, date(2026, 3, 10))
        # martes 10 -> el jueves de ESA misma semana, no el martes siguiente
        self.assertEqual(t.next_due_date(), date(2026, 3, 12))

    def test_api_patch_moves_the_anchor(self):
        t = self._biweekly()
        r = self.client.patch(
            reverse("api:task_detail", args=[t.uuid]),
            data=json.dumps({"due_date": "2026-03-10"}), content_type="application/json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        t.refresh_from_db()
        self.assertEqual(t.series_start_date, date(2026, 3, 10))
        self.assertEqual(t.next_due_date(), date(2026, 3, 12))

    def test_editing_only_the_title_keeps_the_anchor(self):
        t = self._biweekly()
        self.client.patch(
            reverse("api:task_detail", args=[t.uuid]),
            data=json.dumps({"title": "Otro nombre", "due_date": "2026-03-02", "repeat": "custom", "interval": 2}),
            content_type="application/json",
        )
        t.refresh_from_db()
        self.assertEqual(t.series_start_date, date(2026, 3, 2))

    def test_garbage_interval_does_not_crash_the_web_form(self):
        t = self._biweekly()
        for bad in ("abc", "0", "-3", ""):
            r = self.client.post(reverse("tasks:task_edit", args=[t.pk]), {
                "title": "Quincenal", "repeat": "daily", "interval": bad,
                "due_date": "2026-03-02", "due_time": "20:00",
            })
            self.assertEqual(r.status_code, 302, f"interval={bad!r}")
            t.refresh_from_db()
            self.assertEqual(t.interval, 1)

    def test_invalid_date_is_a_form_error_not_a_500(self):
        t = self._biweekly()
        r = self.client.post(reverse("tasks:task_edit", args=[t.pk]), {
            "title": "Quincenal", "repeat": "daily", "due_date": "no-es-fecha", "due_time": "20:00",
        })
        self.assertEqual(r.status_code, 200)


class StatsDetailOrderTests(TestCase):
    def test_stats_detail_lists_days_newest_first_even_if_written_out_of_order(self):
        import datetime as dt
        from .models import Occurrence
        sid = uuid_mod.uuid4()
        user = get_current_user()
        for day, result in ((3, "done"), (1, "done"), (2, "not_done")):
            Occurrence.objects.create(
                series_id=sid, title="X", result=result, user=user, due_date=dt.date(2026, 3, day),
            )
        r = self.client.get(reverse("api:stats_detail", args=[sid]))
        days = [o["due_date"] for o in r.json()["occurrences"]]
        self.assertEqual(days, ["2026-03-03", "2026-03-02", "2026-03-01"])
        self.assertEqual(r.json()["current_streak"], 1)
        points = [p["date"] for p in r.json()["chart_points"]]
        self.assertEqual(points, sorted(points))


class PlanDaysChangeMovesPendingTaskTests(TestCase):
    """Si cambias los días de un plan, la tarea pendiente no puede quedarse
    en un día que ya no es del plan."""

    def test_pending_task_moves_to_the_next_marked_day(self):
        import datetime as dt
        from unittest import mock
        from django.utils import timezone

        wed = timezone.make_aware(dt.datetime(2026, 3, 4, 9, 0))  # miércoles
        with mock.patch("django.utils.timezone.now", lambda: wed):
            plan = Plan.objects.create(
                user=get_current_user(), name="Habito plan", plan_type=Plan.PLAN_TYPE_GENERAL,
                started_on=dt.date(2026, 3, 4), repeat="custom", custom_days="0,2,4",
                due_time=dt.time(20, 0),
            )
            plan.sync_task()
            task = Task.objects.get(series_id=plan.task_series_id, is_done=False)
            self.assertEqual(task.due_date, dt.date(2026, 3, 4))  # miércoles: toca
            plan.custom_days = "1,3"                              # ahora martes y jueves
            plan.save()
            plan.sync_task()
            task.refresh_from_db()
            self.assertEqual(task.due_date, dt.date(2026, 3, 5))  # jueves, no el miércoles
            self.assertEqual(Task.objects.filter(series_id=plan.task_series_id).count(), 1)


class ClosedPlanApiTests(TestCase):
    """La app móvil enseña un plan cerrado con el % que tenía AL CERRARLO
    (igual que la web), no con el de ahora: la API tiene que mandarlo."""

    def _plan(self):
        import datetime as dt
        return Plan.objects.create(
            user=get_current_user(), name="Curso cerrado", plan_type=Plan.PLAN_TYPE_GENERAL,
            started_on=dt.date(2026, 3, 2), repeat="custom", custom_days="0,2,4",
            due_time=dt.time(20, 0),
        )

    def test_closed_plan_reports_the_percentage_it_had_when_closed(self):
        from unittest import mock
        plan = self._plan()
        with mock.patch.object(Plan, "progress_pct", lambda self: 80):
            r = self.client.post(reverse("api:plan_close", args=[plan.uuid]))
        self.assertEqual(r.status_code, 200, r.content)
        # Después el progreso «de ahora» es otro, pero el cierre se guardó con 80.
        with mock.patch.object(Plan, "progress_pct", lambda self: 10):
            p = self.client.get(reverse("api:plan_detail", args=[plan.uuid])).json()["plan"]
            listed = {x["uuid"]: x for x in self.client.get(reverse("api:plan_list")).json()["plans"]}
        self.assertEqual(p["final_progress_pct"], 80)
        self.assertEqual(p["progress_pct"], 10)
        self.assertTrue(p["is_completed"])
        self.assertEqual(listed[str(plan.uuid)]["final_progress_pct"], 80)
        self.assertIsNotNone(listed[str(plan.uuid)]["closed_at"])

    def test_open_plan_has_no_final_percentage(self):
        plan = self._plan()
        p = self.client.get(reverse("api:plan_detail", args=[plan.uuid])).json()["plan"]
        self.assertIsNone(p["final_progress_pct"])
        self.assertIsNone(p["closed_at"])


class CategorySubtypeRulesTests(TestCase):
    """Cada categoría solo admite sus subtipos, Lectura es siempre «reading» y
    sin vídeo (las tareas de Enfoque ya no existen), y editar desde la app
    móvil no borra el subtipo de Estudio (Udemy / Ilerna / Idiomas)."""

    def setUp(self):
        self.user = get_current_user()

    def _task(self, **kw):
        base = dict(title="T", user=self.user, due_date=date(2026, 3, 2), repeat=Task.REPEAT_NONE)
        base.update(kw)
        return Task.objects.create(**base)

    def _patch(self, task, data):
        return self.client.patch(
            reverse("api:task_detail", args=[task.uuid]), data=json.dumps(data), content_type="application/json"
        )

    def _post_api(self, data):
        return self.client.post(reverse("api:task_create"), data=json.dumps(data), content_type="application/json")

    # ---- API (lo que usa la app móvil)

    def test_editing_a_udemy_task_from_the_app_keeps_its_subtype(self):
        t = self._task(category="study", subcategory="udemy", target_minutes=30, repeat=Task.REPEAT_DAILY)
        # lo que manda el formulario del móvil: no conoce los subtipos de Estudio y manda ""
        r = self._patch(t, {"title": "Excel editado", "category": "study", "subcategory": "",
                            "target_minutes": 30, "youtube_video_id": "", "due_time": "20:00", "repeat": "daily"})
        self.assertEqual(r.status_code, 200, r.content)
        t.refresh_from_db()
        self.assertEqual(t.subcategory, "udemy")
        self.assertEqual(t.workout_kind, "auto")  # sigue contándola la extensión
        self.assertEqual(t.title, "Excel editado")

    def test_ilerna_and_language_subtypes_survive_an_app_edit_too(self):
        for sub, extra in (("ilerna", dict(target_minutes=60)),
                           ("language", dict(youtube_video_id="dQw4w9WgXcQ"))):
            t = self._task(category="study", subcategory=sub, **extra)
            r = self._patch(t, {"title": "X", "subcategory": ""})
            self.assertEqual(r.status_code, 200, (sub, r.content))
            t.refresh_from_db()
            self.assertEqual(t.subcategory, sub)

    def test_reading_is_always_reading_and_never_has_a_video(self):
        r = self._post_api({"title": "Leer", "category": "work", "subcategory": "",
                            "youtube_video_id": "dQw4w9WgXcQ", "youtube_playlist_id": "PLabc",
                            "target_video_count": 3, "target_minutes": 40})
        self.assertEqual(r.status_code, 201, r.content)
        t = Task.objects.get(uuid=r.json()["task"]["uuid"])
        self.assertEqual(t.subcategory, "reading")
        self.assertEqual((t.youtube_video_id, t.youtube_playlist_id, t.target_video_count), ("", "", None))
        self.assertFalse(t.has_local_video)
        self.assertEqual(t.target_minutes, 40)
        self.assertEqual(t.workout_kind, "focus")

    def test_old_focus_task_with_a_video_becomes_a_plain_reading_task_when_edited(self):
        t = self._task(category="work", subcategory="", youtube_video_id="dQw4w9WgXcQ", target_minutes=25)
        r = self._patch(t, {"title": "Antigua"})
        self.assertEqual(r.status_code, 200, r.content)
        t.refresh_from_db()
        self.assertEqual((t.subcategory, t.youtube_video_id), ("reading", ""))

    def test_a_subtype_of_another_category_is_dropped(self):
        t = self._task(category="sport", subcategory="upper_body", sport_mode="camera")
        self._patch(t, {"category": "general", "subcategory": "upper_body"})
        t.refresh_from_db()
        self.assertEqual((t.category, t.subcategory), ("general", ""))
        # y también si solo cambia la categoría, sin mandar subtipo
        t2 = self._task(category="sport", subcategory="lower_body", sport_mode="circuit")
        self._patch(t2, {"category": "avoid"})
        t2.refresh_from_db()
        self.assertEqual((t2.category, t2.subcategory), ("avoid", ""))
        # y un subtipo de Deporte no vale en Estudio
        t3 = self._task(category="study", youtube_video_id="dQw4w9WgXcQ")
        self._patch(t3, {"subcategory": "upper_body"})
        t3.refresh_from_db()
        self.assertEqual(t3.subcategory, "")

    def test_sport_keeps_its_subtype_unless_given_a_valid_new_one(self):
        t = self._task(category="sport", subcategory="lower_body", sport_mode="circuit")
        self._patch(t, {"title": "Piernas", "subcategory": ""})
        t.refresh_from_db()
        self.assertEqual(t.subcategory, "lower_body")
        self._patch(t, {"subcategory": "running"})
        t.refresh_from_db()
        self.assertEqual(t.subcategory, "running")
        self._patch(t, {"subcategory": "inventado"})
        t.refresh_from_db()
        self.assertEqual(t.subcategory, "running")

    def test_editing_cannot_strip_the_link_of_a_study_task(self):
        t = self._task(category="study", youtube_video_id="dQw4w9WgXcQ")
        r = self._patch(t, {"youtube_video_id": "", "youtube_playlist_id": ""})
        self.assertEqual(r.status_code, 400, r.content)
        t.refresh_from_db()
        self.assertEqual(t.youtube_video_id, "dQw4w9WgXcQ")

    def test_a_study_task_that_was_already_unlinked_can_still_be_edited(self):
        # p. ej. la tarea de un plan de Estudio con temporizador manual
        t = self._task(category="study")
        r = self._patch(t, {"title": "Otro título", "due_time": "21:00"})
        self.assertEqual(r.status_code, 200, r.content)
        t.refresh_from_db()
        self.assertEqual(t.title, "Otro título")

    # ---- web

    def _edit(self, t, **post):
        data = {"title": t.title, "category": t.category, "repeat": "none",
                "due_date": "2026-03-02", "due_time": "20:00"}
        data.update(post)
        return self.client.post(reverse("tasks:task_edit", args=[t.pk]), data)

    def test_web_youtube_radio_turns_a_udemy_task_into_a_youtube_one(self):
        t = self._task(category="study", subcategory="udemy", target_minutes=30)
        r = self._edit(t, subcategory="", youtube_video_id="dQw4w9WgXcQ", video_target_minutes="20")
        self.assertEqual(r.status_code, 302, r.content[:300])
        t.refresh_from_db()
        self.assertEqual(t.subcategory, "")
        self.assertEqual(t.youtube_video_id, "dQw4w9WgXcQ")

    def test_web_edit_keeps_the_subtype_if_the_form_does_not_send_one(self):
        t = self._task(category="study", subcategory="ilerna", target_minutes=60)
        r = self._edit(t, target_minutes="60")
        self.assertEqual(r.status_code, 302, r.content[:300])
        t.refresh_from_db()
        self.assertEqual(t.subcategory, "ilerna")

    def test_web_reading_task_is_saved_as_reading_without_video(self):
        # lo que el formulario viejo mandaba al elegir «Lectura»: sin subtipo y con vídeo
        r = self.client.post(reverse("tasks:task_create"), {
            "title": "Leer", "category": "work", "subcategory": "", "repeat": "none",
            "due_date": "2026-03-02", "due_time": "20:00", "target_minutes": "40",
            "video_target_minutes": "99", "youtube_video_id": "dQw4w9WgXcQ",
        })
        self.assertEqual(r.status_code, 302, r.content[:300])
        t = Task.objects.get(title="Leer")
        self.assertEqual((t.subcategory, t.youtube_video_id, t.target_minutes), ("reading", "", 40))

    def test_web_edit_of_an_old_reading_task_uses_the_timer_minutes(self):
        t = self._task(category="work", subcategory="reading", target_minutes=30)
        r = self._edit(t, subcategory="reading", target_minutes="50", video_target_minutes="30")
        self.assertEqual(r.status_code, 302, r.content[:300])
        t.refresh_from_db()
        self.assertEqual(t.target_minutes, 50)

    def test_web_sport_to_general_drops_the_sport_subtype(self):
        t = self._task(category="sport", subcategory="upper_body", sport_mode="camera")
        r = self._edit(t, category="general", subcategory="upper_body")
        self.assertEqual(r.status_code, 302, r.content[:300])
        t.refresh_from_db()
        self.assertEqual((t.category, t.subcategory), ("general", ""))

    def test_web_sport_without_subtype_in_the_post_keeps_it(self):
        t = self._task(category="sport", subcategory="upper_body", sport_mode="camera")
        r = self._edit(t, sport_mode="camera")
        self.assertEqual(r.status_code, 302, r.content[:300])
        t.refresh_from_db()
        self.assertEqual(t.subcategory, "upper_body")

    # ---- el formulario web: UN solo radio de subtipo marcado, y el que toca

    def _checked_subtypes(self, task=None):
        import re
        url = reverse("tasks:task_edit", args=[task.pk]) if task else reverse("tasks:task_create")
        html = self.client.get(url).content.decode()
        tags = re.findall(r'<input type="radio" name="subcategory"[^>]*>', html, flags=re.S)
        self.assertTrue(tags)
        return [re.search(r'value="([^"]*)"', t).group(1) for t in tags if "checked" in t]

    def test_edit_form_preselects_the_saved_subtype_and_only_that(self):
        cases = (
            (dict(category="sport", subcategory="upper_body", sport_mode="camera"), ["upper_body"]),
            (dict(category="sport", subcategory="running"), ["running"]),
            (dict(category="work", subcategory="reading", target_minutes=30), ["reading"]),
            (dict(category="study", subcategory="udemy", target_minutes=30), ["udemy"]),
            (dict(category="study", subcategory="ilerna", target_minutes=30), ["ilerna"]),
            (dict(category="study", youtube_video_id="dQw4w9WgXcQ"), [""]),
            (dict(category="general"), [""]),
            (dict(category="avoid", repeat="daily"), [""]),
        )
        for kw, expected in cases:
            t = self._task(**kw)
            self.assertEqual(self._checked_subtypes(t), expected, kw)

    def test_new_task_form_starts_with_no_subtype(self):
        self.assertEqual(self._checked_subtypes(None), [""])
