import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone


class Task(models.Model):
    REPEAT_NONE = "none"
    REPEAT_DAILY = "daily"
    REPEAT_WEEKLY = "weekly"
    REPEAT_MONTHLY = "monthly"
    REPEAT_YEARLY = "yearly"
    REPEAT_CUSTOM = "custom"

    REPEAT_CHOICES = [
        (REPEAT_NONE, "No se repite"),
        (REPEAT_DAILY, "Cada día"),
        (REPEAT_WEEKLY, "Cada semana"),
        (REPEAT_MONTHLY, "Cada mes"),
        (REPEAT_YEARLY, "Cada año"),
        (REPEAT_CUSTOM, "Personalizado"),
    ]

    # Tipos / categorías de tarea. Sirve para:
    # - agrupar / filtrar visualmente
    # - decidir qué tipo de "extras" se enganchan (timer para study,
    #   MediaPipe para sport, etc.). Se mantiene como CharField con choices
    #   para que añadir un tipo nuevo sea solo tocar esta lista.
    CATEGORY_GENERAL = "general"
    CATEGORY_STUDY = "study"
    CATEGORY_SPORT = "sport"
    CATEGORY_WORK = "work"
    CATEGORY_PERSONAL = "personal"
    CATEGORY_OTHER = "other"

    CATEGORY_CHOICES = [
        (CATEGORY_GENERAL, "General"),
        (CATEGORY_STUDY, "Estudio"),
        (CATEGORY_SPORT, "Deporte"),
        (CATEGORY_WORK, "Trabajo"),
        (CATEGORY_PERSONAL, "Personal"),
        (CATEGORY_OTHER, "Otro"),
    ]

    # Metadatos que describen qué "extras" admite cada categoría.
    # Útil para que la UI sepa si mostrar el botón de iniciar timer,
    # el panel de cámara de MediaPipe, etc. Sin construir esos extras hoy.
    CATEGORY_CAPABILITIES = {
        CATEGORY_GENERAL: [],
        CATEGORY_STUDY: ["timer", "pomodoro"],
        CATEGORY_SPORT: ["timer", "pose_tracking"],
        CATEGORY_WORK: ["timer", "pomodoro"],
        CATEGORY_PERSONAL: [],
        CATEGORY_OTHER: [],
    }

    WEEKDAYS = [
        ("0", "Lunes"),
        ("1", "Martes"),
        ("2", "Miércoles"),
        ("3", "Jueves"),
        ("4", "Viernes"),
        ("5", "Sábado"),
        ("6", "Domingo"),
    ]

    title = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    category = models.CharField(
        max_length=16,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_GENERAL,
        db_index=True,
        help_text="Tipo de tarea. Define qué extras tendrá disponibles (timer, pose tracking, etc).",
    )
    due_date = models.DateField(null=True, blank=True)
    due_time = models.TimeField(null=True, blank=True,
        help_text="Hora límite. Si pasa sin marcarla, se auto-marca como no hecha.")
    repeat = models.CharField(max_length=10, choices=REPEAT_CHOICES, default=REPEAT_NONE)
    interval = models.PositiveIntegerField(default=1)
    custom_days = models.CharField(max_length=20, blank=True)
    is_important = models.BooleanField(default=False)

    series_id = models.UUIDField(default=uuid.uuid4, editable=False)
    series_start_date = models.DateField(null=True, blank=True, editable=False)

    is_done = models.BooleanField(default=False)
    expired = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["is_done", "due_date", "due_time", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def category_capabilities(self):
        """Lista de extras disponibles para esta categoría."""
        return self.CATEGORY_CAPABILITIES.get(self.category, [])

    def has_capability(self, capability):
        return capability in self.category_capabilities

    def custom_days_list(self):
        if not self.custom_days:
            return []
        return [d.strip() for d in self.custom_days.split(",") if d.strip()]

    def custom_days_labels(self):
        labels = dict(self.WEEKDAYS)
        return [labels[d] for d in sorted(self.custom_days_list(), key=int)]

    def repeat_summary(self):
        n = self.interval or 1
        if self.repeat == self.REPEAT_NONE:
            return ""
        if self.repeat == self.REPEAT_DAILY:
            return "Cada día" if n == 1 else f"Cada {n} días"
        if self.repeat == self.REPEAT_WEEKLY:
            return "Cada semana" if n == 1 else f"Cada {n} semanas"
        if self.repeat == self.REPEAT_MONTHLY:
            return "Cada mes" if n == 1 else f"Cada {n} meses"
        if self.repeat == self.REPEAT_YEARLY:
            return "Cada año" if n == 1 else f"Cada {n} años"
        if self.repeat == self.REPEAT_CUSTOM:
            days = ", ".join(self.custom_days_labels())
            prefix = "Cada semana" if n == 1 else f"Cada {n} semanas"
            return f"{prefix} ({days})" if days else prefix
        return ""

    def deadline_datetime(self):
        """Devuelve el datetime naive del deadline, o None."""
        if self.due_date and self.due_time:
            import datetime
            return datetime.datetime.combine(self.due_date, self.due_time)
        return None

    def is_overdue(self):
        """True si la hora límite ya pasó y la tarea sigue pendiente."""
        if self.is_done or self.expired:
            return False
        dl = self.deadline_datetime()
        if dl is None:
            return False
        now = timezone.localtime(timezone.now()).replace(tzinfo=None)
        return now > dl

    def minutes_remaining(self):
        """Minutos hasta el deadline (negativo = ya pasó)."""
        dl = self.deadline_datetime()
        if dl is None:
            return None
        now = timezone.localtime(timezone.now()).replace(tzinfo=None)
        return int((dl - now).total_seconds() / 60)

    def next_due_date(self):
        if not self.due_date:
            return None
        base = self.due_date
        n = self.interval or 1

        if self.repeat == self.REPEAT_CUSTOM:
            marked_days = sorted(int(d) for d in self.custom_days_list())
            if not marked_days:
                return None
            anchor = self.series_start_date or base
            anchor_monday = anchor - timedelta(days=anchor.weekday())
            base_monday = base - timedelta(days=base.weekday())
            week_index = (base_monday - anchor_monday).days // 7
            current_weekday = base.weekday()
            if week_index % n == 0:
                for candidate in marked_days:
                    if candidate > current_weekday:
                        return base + timedelta(days=candidate - current_weekday)
            weeks_left = n - (week_index % n)
            next_monday = base_monday + timedelta(weeks=weeks_left)
            return next_monday + timedelta(days=marked_days[0])

        if self.repeat == self.REPEAT_DAILY:
            return base + timedelta(days=n)
        if self.repeat == self.REPEAT_WEEKLY:
            return base + timedelta(weeks=n)
        if self.repeat == self.REPEAT_MONTHLY:
            total = (base.month - 1) + n
            year = base.year + total // 12
            month = total % 12 + 1
            try:
                return base.replace(year=year, month=month)
            except ValueError:
                return base.replace(year=year, month=month, day=28)
        if self.repeat == self.REPEAT_YEARLY:
            try:
                return base.replace(year=base.year + n)
            except ValueError:
                return base.replace(year=base.year + n, day=28)
        return None

    def save(self, *args, **kwargs):
        if self.series_start_date is None and self.due_date is not None:
            self.series_start_date = self.due_date
        super().save(*args, **kwargs)

    def _spawn_next(self):
        if self.repeat != self.REPEAT_NONE and self.due_date:
            Task.objects.create(
                title=self.title, notes=self.notes,
                category=self.category,
                due_date=self.next_due_date(), due_time=self.due_time,
                repeat=self.repeat, interval=self.interval,
                custom_days=self.custom_days, is_important=self.is_important,
                series_id=self.series_id, series_start_date=self.series_start_date,
            )

    def mark_done(self):
        self.is_done = True
        self.expired = False
        self.completed_at = timezone.now()
        self.save()
        Occurrence.objects.create(
            task=self, series_id=self.series_id, title=self.title,
            result=Occurrence.RESULT_DONE, due_date=self.due_date,
        )
        self._spawn_next()

    def mark_not_done(self):
        self.is_done = False
        self.expired = False
        self.completed_at = None
        self.save()
        Occurrence.objects.create(
            task=self, series_id=self.series_id, title=self.title,
            result=Occurrence.RESULT_NOT_DONE, due_date=self.due_date,
        )

    def mark_expired(self):
        """Llamado cuando pasa la hora límite sin completarse."""
        self.is_done = True
        self.expired = True
        self.completed_at = timezone.now()
        self.save()
        Occurrence.objects.create(
            task=self, series_id=self.series_id, title=self.title,
            result=Occurrence.RESULT_NOT_DONE, due_date=self.due_date,
            auto_expired=True,
        )
        self._spawn_next()

    @classmethod
    def expire_overdue(cls, dry_run=False):
        """
        Revisa las tareas pendientes con hora límite y marca como
        expiradas las que ya han pasado esa hora.

        Se llama "en caliente" desde la vista de la lista cada vez que
        se abre la página — así funciona sin depender de un cron
        externo (útil en hostings gratuitos que no lo ofrecen).
        Devuelve la lista de tareas expiradas en esta pasada.
        """
        import datetime as _dt

        now_local = timezone.localtime(timezone.now()).replace(tzinfo=None)
        now_time = now_local.time()

        candidates = cls.objects.filter(is_done=False, expired=False, due_time__isnull=False)

        expired_tasks = []
        for task in candidates:
            if task.due_date is None:
                should_expire = task.due_time < now_time
            else:
                deadline = _dt.datetime.combine(task.due_date, task.due_time)
                should_expire = now_local > deadline

            if should_expire:
                if not dry_run:
                    task.mark_expired()
                expired_tasks.append(task)

        return expired_tasks


class WorkoutSession(models.Model):
    """
    Estadísticas de una sesión de entreno grabada con la cámara
    (MediaPipe, en el navegador). No se guarda ningún vídeo, solo
    los números que salen del conteo.
    """
    EXERCISE_PULLUP = "pullup"
    EXERCISE_CHOICES = [
        (EXERCISE_PULLUP, "Dominadas"),
    ]

    task = models.ForeignKey(
        Task, on_delete=models.SET_NULL, null=True, blank=True, related_name="workout_sessions"
    )
    series_id = models.UUIDField(null=True, blank=True)
    exercise = models.CharField(max_length=32, choices=EXERCISE_CHOICES, default=EXERCISE_PULLUP)
    total_reps = models.PositiveIntegerField(default=0)
    session_duration_seconds = models.PositiveIntegerField(default=0)
    avg_rep_seconds = models.FloatField(null=True, blank=True)
    rest_alerts_triggered = models.PositiveIntegerField(default=0)
    rep_durations = models.JSONField(default=list, blank=True)  # [1.1, 1.3, ...] segundos por rep
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"{self.get_exercise_display()} — {self.total_reps} reps ({self.recorded_at:%Y-%m-%d %H:%M})"


class Occurrence(models.Model):
    RESULT_DONE = "done"
    RESULT_NOT_DONE = "not_done"
    RESULT_CHOICES = [
        (RESULT_DONE, "Hecho"),
        (RESULT_NOT_DONE, "No hecho"),
    ]

    task = models.ForeignKey(
        Task, on_delete=models.SET_NULL, null=True, blank=True, related_name="occurrences"
    )
    series_id = models.UUIDField()
    title = models.CharField(max_length=255)
    result = models.CharField(max_length=10, choices=RESULT_CHOICES)
    due_date = models.DateField(null=True, blank=True)
    auto_expired = models.BooleanField(default=False)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"{self.title} — {self.get_result_display()} ({self.recorded_at:%Y-%m-%d})"

    @classmethod
    def streak_stats(cls, series_id):
        """
        Calcula racha actual y máxima histórica para una serie.
        La racha se rompe en cuanto aparece un not_done.
        """
        occs = list(cls.objects.filter(series_id=series_id).order_by("-recorded_at"))

        # Racha actual: contar done consecutivos desde el más reciente
        current = 0
        for occ in occs:
            if occ.result == cls.RESULT_DONE:
                current += 1
            else:
                break

        # Racha máxima: recorrer todo en orden cronológico
        max_s = 0
        running = 0
        for occ in reversed(occs):
            if occ.result == cls.RESULT_DONE:
                running += 1
                max_s = max(max_s, running)
            else:
                running = 0

        return {"current_streak": current, "max_streak": max_s}
