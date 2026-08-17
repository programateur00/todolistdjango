from django.contrib import admin

from .models import (
    CourseModule, CoursePlaylist, CourseQuiz, Exercise, Occurrence, Plan, PlanItem, Routine,
    RoutineItem, SavedVideo, Task, WorkoutSession,
)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "title", "user", "category", "is_avoid", "due_date", "due_time",
        "repeat", "is_done", "is_important", "expired",
    )
    list_filter = ("category", "is_done", "is_important", "expired", "repeat")
    search_fields = ("title", "notes")
    list_per_page = 50


@admin.register(Occurrence)
class OccurrenceAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "result", "due_date", "recorded_at", "auto_expired")
    list_filter = ("result", "auto_expired")
    search_fields = ("title",)
    list_per_page = 50


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "mode", "counter_key", "is_active", "order")
    list_filter = ("mode", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    list_per_page = 50


@admin.register(SavedVideo)
class SavedVideoAdmin(admin.ModelAdmin):
    list_display = ("title", "scope", "youtube_video_id", "user", "created_at")
    list_filter = ("scope",)
    search_fields = ("title", "youtube_video_id")


class RoutineItemInline(admin.TabularInline):
    model = RoutineItem
    extra = 1


@admin.register(Routine)
class RoutineAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "subcategory", "default_work_seconds", "default_rest_seconds")
    list_filter = ("subcategory",)
    search_fields = ("name",)
    inlines = [RoutineItemInline]


@admin.register(WorkoutSession)
class WorkoutSessionAdmin(admin.ModelAdmin):
    list_display = (
        "exercise", "user", "routine", "total_reps", "total_sets", "added_weight_kg",
        "distance_km", "steps", "recorded_at",
    )
    list_filter = ("exercise",)
    list_per_page = 50


class PlanItemInline(admin.TabularInline):
    model = PlanItem
    extra = 1
    fields = (
        "is_headline", "order", "exercise", "series_id", "label", "progression",
        "start_sets", "start_reps", "start_seconds", "start_weight_kg",
        "goal_sets", "goal_reps", "goal_seconds", "goal_weight_kg",
        "rep_range_low", "weight_increment_kg", "reps_increment",
        "sessions_per_step", "deload_after_failures",
    )


class CourseModuleInline(admin.TabularInline):
    model = CourseModule
    extra = 0
    fields = ("order", "scheduled_week", "level", "youtube_video_id", "title", "has_captions")


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "name", "user", "started_on", "weeks", "is_active", "has_task",
        "plan_type", "study_subtype", "language_name",
    )
    list_filter = ("is_active", "plan_type", "study_subtype")
    search_fields = ("name",)
    inlines = [PlanItemInline, CourseModuleInline]

    @admin.display(boolean=True, description="Tarea creada")
    def has_task(self, obj):
        return obj.task is not None

    def save_related(self, request, form, formsets, change):
        """
        Crear o actualizar la tarea del plan también al guardar desde el
        admin. Sin esto, un plan creado aquí existía pero nunca aparecía
        en la lista de tareas — y desde fuera parecía que el plan no
        funcionaba.

        Va en save_related y no en save_model porque los objetivos
        (PlanItem) se guardan después del propio Plan, y la tarea solo
        tiene sentido cuando ya se sabe qué ejercicios lleva.
        """
        super().save_related(request, form, formsets, change)
        form.instance.sync_task()


@admin.register(CourseModule)
class CourseModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "plan", "level", "order", "scheduled_week", "has_captions", "watched_at")
    list_filter = ("level", "has_captions")
    search_fields = ("title", "youtube_video_id", "plan__name")
    list_per_page = 50


@admin.register(CoursePlaylist)
class CoursePlaylistAdmin(admin.ModelAdmin):
    list_display = (
        "title", "language", "level_label", "native_language", "channel_title", "is_active", "order", "added_at",
    )
    list_filter = ("language", "level", "native_language", "is_active")
    search_fields = ("title", "channel_title", "youtube_playlist_id", "notes")
    list_per_page = 50


@admin.register(CourseQuiz)
class CourseQuizAdmin(admin.ModelAdmin):
    list_display = ("plan", "up_to_order", "total", "score", "passed", "created_at", "answered_at")
    list_filter = ("passed",)
    search_fields = ("plan__name", "plan__language_name")
    readonly_fields = ("topics", "questions", "answers")
    list_per_page = 50
