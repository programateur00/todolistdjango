from django.contrib import admin

from .models import Occurrence, Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "title", "category", "due_date", "due_time",
        "repeat", "is_done", "is_important", "expired",
    )
    list_filter = ("category", "is_done", "is_important", "expired", "repeat")
    search_fields = ("title", "notes")
    list_per_page = 50


@admin.register(Occurrence)
class OccurrenceAdmin(admin.ModelAdmin):
    list_display = ("title", "result", "due_date", "recorded_at", "auto_expired")
    list_filter = ("result", "auto_expired")
    search_fields = ("title",)
    list_per_page = 50
