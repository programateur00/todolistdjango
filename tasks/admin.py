from django.contrib import admin

from .models import (
    Exercise, Occurrence, Plan, PlanExercise, Routine, RoutineItem, Task, WorkoutSession,
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


class PlanExerciseInline(admin.TabularInline):
    model = PlanExercise
    extra = 1


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "started_on", "weeks", "ends_on", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    inlines = [PlanExerciseInline]
