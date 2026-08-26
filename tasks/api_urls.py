"""
Rutas de la API JSON (para la app móvil). Se montan bajo /api/ — ver
todoapp/urls.py. Ese prefijo es también el que usa CORS_URLS_REGEX en
settings, así que si mueves esto de sitio, acuérdate de cambiarlo allí.
"""
from django.urls import path

from . import api

app_name = "api"

urlpatterns = [
    path("meta/", api.meta, name="meta"),

    path("tasks/", api.task_list, name="task_list"),
    path("tasks/create/", api.task_create, name="task_create"),
    path("tasks/<uuid:uuid>/", api.task_detail, name="task_detail"),
    path("tasks/<uuid:uuid>/mark/<str:action>/", api.task_mark, name="task_mark"),
    path("series/<uuid:series_id>/mark/<str:action>/", api.task_mark_by_series, name="task_mark_by_series"),

    path("exercises/", api.exercise_list, name="exercise_list"),
    path("exercises/<slug:slug>/target/", api.exercise_target, name="exercise_target"),

    path("routines/", api.routine_list, name="routine_list"),
    path("routines/<uuid:uuid>/", api.routine_detail, name="routine_detail"),

    path("tasks/<uuid:uuid>/workout/", api.workout_save, name="workout_save"),
    path("tasks/<uuid:uuid>/workout-manual/", api.workout_save_manual, name="workout_save_manual"),
    path("tasks/<uuid:uuid>/running-import/", api.running_import, name="running_import"),
    path("tasks/<uuid:uuid>/circuit/<uuid:routine_uuid>/", api.routine_result, name="routine_result"),
    path("tasks/<uuid:uuid>/focus/", api.focus_save, name="focus_save"),
    path("tasks/<uuid:uuid>/video/", api.video_save, name="video_save"),
    path("videos/", api.saved_video_list, name="saved_video_list"),
    path("videos/<uuid:uuid>/", api.saved_video_delete, name="saved_video_delete"),

    path("plans/", api.plan_list, name="plan_list"),
    path("plans/create/", api.plan_create, name="plan_create"),
    path("plans/generate/", api.plan_generate, name="plan_generate"),
    path("plans/<uuid:uuid>/", api.plan_detail, name="plan_detail"),
    path("plans/<uuid:uuid>/close/", api.plan_close, name="plan_close"),
    path("plans/<uuid:uuid>/items/", api.plan_item_create, name="plan_item_create"),
    path("plans/<uuid:uuid>/items/<int:item_id>/", api.plan_item_detail, name="plan_item_detail"),
    path("review/weekly/", api.weekly_review, name="weekly_review"),
    path("tasks/<uuid:uuid>/plan/<uuid:plan_uuid>/", api.plan_session, name="plan_session"),
    path("tasks/<uuid:uuid>/plan/<uuid:plan_uuid>/save/", api.plan_session_save, name="plan_session_save"),

    path("stats/", api.stats_list, name="stats_list"),
    path("stats/<uuid:series_id>/", api.stats_detail, name="stats_detail"),
]
