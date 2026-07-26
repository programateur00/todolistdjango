from django.urls import path
from . import views

app_name = "tasks"

urlpatterns = [
    path("", views.task_list, name="task_list"),
    path("nueva/", views.task_create, name="task_create"),
    path("<int:pk>/editar/", views.task_edit, name="task_edit"),
    path("<int:pk>/eliminar/", views.task_delete, name="task_delete"),
    path("<int:pk>/hecho/", views.task_mark_done, name="task_mark_done"),
    path("<int:pk>/no-hecho/", views.task_mark_not_done, name="task_mark_not_done"),
    path("<int:pk>/entreno/", views.task_workout, name="task_workout"),
    path("<int:pk>/entreno/guardar/", views.task_workout_save, name="task_workout_save"),
    path("<int:pk>/entreno/guardar-manual/", views.task_workout_save_manual, name="task_workout_save_manual"),
    path("estadisticas/", views.stats_list, name="stats_list"),
    path("estadisticas/<uuid:series_id>/", views.stats_detail, name="stats_detail"),
]
