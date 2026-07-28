import uuid
from datetime import timedelta

from django.conf import settings
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
    CATEGORY_AVOID = "avoid"

    CATEGORY_CHOICES = [
        (CATEGORY_GENERAL, "General"),
        (CATEGORY_STUDY, "Estudio"),
        (CATEGORY_SPORT, "Deporte"),
        (CATEGORY_WORK, "Trabajo"),
        (CATEGORY_PERSONAL, "Personal"),
        (CATEGORY_OTHER, "Otro"),
        (CATEGORY_AVOID, "Antitarea"),
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
        CATEGORY_AVOID: [],
    }

    # Subcategorías de "Deporte". Solo tienen sentido cuando category=sport;
    # filtran qué ejercicios del catálogo (Exercise.body_area) aparecen en
    # el selector al entrenar, para no mezclar dominadas con sentadillas.
    SUBCATEGORY_UPPER_BODY = "upper_body"
    SUBCATEGORY_LOWER_BODY = "lower_body"
    SUBCATEGORY_RUNNING = "running"

    SUBCATEGORY_CHOICES = [
        (SUBCATEGORY_UPPER_BODY, "Tren superior"),
        (SUBCATEGORY_LOWER_BODY, "Tren inferior"),
        (SUBCATEGORY_RUNNING, "Running"),
    ]

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
    subcategory = models.CharField(
        max_length=16,
        choices=SUBCATEGORY_CHOICES,
        blank=True,
        help_text="Solo aplica si category='sport'. Filtra qué ejercicios se ofrecen al entrenar.",
    )
    due_date = models.DateField(null=True, blank=True)
    due_time = models.TimeField(null=True, blank=True,
        help_text="Hora límite. Si pasa sin marcarla, se auto-marca como no hecha.")
    repeat = models.CharField(max_length=10, choices=REPEAT_CHOICES, default=REPEAT_NONE)
    interval = models.PositiveIntegerField(default=1)
    custom_days = models.CharField(max_length=20, blank=True)
    is_important = models.BooleanField(default=False)
    avoid_success_label = models.CharField(
        max_length=32, blank=True,
        help_text="Antitareas: texto del botón de la notificación para \"lo he evitado\". "
                   "En blanco usa \"Sigo con la racha\".",
    )
    avoid_fail_label = models.CharField(
        max_length=32, blank=True,
        help_text="Antitareas: texto del botón para \"he caído\". En blanco usa \"Romper racha\".",
    )
    avoid_question = models.CharField(
        max_length=120, blank=True,
        help_text="Antitareas: la pregunta de la notificación. En blanco usa \"¿Has caído hoy?\".",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name="tasks",
        help_text="Dueño de la tarea. Hoy siempre es el usuario por defecto "
                   "(ver tasks/utils.py:get_current_user) — preparado para cuando haya login real.",
    )

    series_id = models.UUIDField(default=uuid.uuid4, editable=False)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Borrado suave: si se borra de verdad, el otro dispositivo no puede "
                   "enterarse al sincronizar y la resucitaría.",
    )
    series_start_date = models.DateField(null=True, blank=True, editable=False)

    is_done = models.BooleanField(default=False)
    expired = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    reopened_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Cuándo devolviste la tarea a pendientes a mano. Sirve para que el "
                   "barrido automático no vuelva a cerrarla en el acto.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["is_done", "due_date", "due_time", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def category_capabilities(self):
        """Lista de extras disponibles para esta categoría."""
        return self.CATEGORY_CAPABILITIES.get(self.category, [])

    @property
    def is_avoid(self):
        """
        True si es una antitarea (category='avoid'). Se calcula desde
        category en vez de ser un campo aparte — "antitarea" es un tipo
        de tarea más, no un check que se pone encima de otro tipo. Se
        queda como propiedad de solo lectura para no tener que tocar
        mark_expired()/mark_failed()/las plantillas, que ya comprobaban
        task.is_avoid antes de este cambio.
        """
        return self.category == self.CATEGORY_AVOID

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
        """
        Momento límite como datetime naive, o None si no hay hora.

        Si la tarea no tiene fecha, la hora se ancla al día en que se
        creó. Sin ese ancla habría que comparar horas sueltas, y eso se
        rompe al pasar la medianoche: una tarea de las 19:45 de ayer,
        mirada a las 00:45, daba "21:45 < 00:45 = falso" y no vencía
        nunca. Con el ancla hay un instante absoluto y la comparación
        funciona siempre.
        """
        if not self.due_time:
            return None
        import datetime
        day = self.due_date
        if day is None:
            if not self.created_at:
                return None
            day = timezone.localtime(self.created_at).date()
        return datetime.datetime.combine(day, self.due_time)

    # Margen que se da a una antitarea DESPUÉS de la hora límite antes de
    # darla por buena sola. La notificación salta a la hora límite; este
    # margen es el rato que tienes para contestarla. Sin él, la tarea se
    # resolvía en el mismo instante en que sonaba el aviso, y contestar no
    # servía de nada.
    AVOID_GRACE_HOURS = 2

    def resolve_datetime(self):
        """Momento a partir del cual la tarea se resuelve sola.

        Para una tarea normal es la hora límite. Para una antitarea es la
        hora límite MÁS el margen: a la hora límite salta el aviso, y solo
        si no contestas en ese rato se da por evitada.
        """
        dl = self.deadline_datetime()
        if dl is None:
            return None
        if self.is_avoid:
            return dl + timedelta(hours=self.AVOID_GRACE_HOURS)
        return dl

    def is_overdue(self):
        """True si ya toca resolverla sola y sigue pendiente."""
        if self.is_done or self.expired:
            return False
        limit = self.resolve_datetime()
        if limit is None:
            return False
        now = timezone.localtime(timezone.now()).replace(tzinfo=None)
        return now > limit

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
        if self.repeat == self.REPEAT_NONE or not self.due_date:
            return
        next_date = self.next_due_date()
        # Idempotente a propósito: marcar, desmarcar y volver a marcar
        # llamaba aquí dos veces y dejaba DOS tareas idénticas en el
        # futuro. Si ya existe la de esa fecha en esta serie, no se crea
        # otra.
        if Task.objects.filter(series_id=self.series_id, due_date=next_date).exists():
            return
        Task.objects.create(
            title=self.title, notes=self.notes,
            category=self.category, subcategory=self.subcategory,
            due_date=next_date, due_time=self.due_time,
            repeat=self.repeat, interval=self.interval,
            custom_days=self.custom_days, is_important=self.is_important,
            avoid_success_label=self.avoid_success_label,
            avoid_fail_label=self.avoid_fail_label,
            avoid_question=self.avoid_question,
            series_id=self.series_id, series_start_date=self.series_start_date,
            user=self.user,
        )

    def _record_occurrence(self, result, auto_expired=False):
        """
        Registra el resultado del día en Occurrence, de forma idempotente.

        Si la tarea tiene due_date, el resultado de ESE día es un hecho
        único que se puede corregir, no un registro que se apila: marcar
        hecha, desmarcar y volver a marcar deja UNA sola ocurrencia con el
        último valor, no tres. Antes se creaba una fila cada vez, lo que
        descuadraba las rachas (ya había un duplicado real en la BD).

        Además es lo que permite que web y móvil resuelvan el mismo día
        por separado sin duplicarlo: los dos hacen update_or_create sobre
        la misma clave y el resultado final es el mismo.

        Sin due_date (tareas sueltas de "cuando pueda") no hay día al que
        anclarlo, así que ahí sí se crea una fila normal.
        """
        if self.due_date is None:
            return Occurrence.objects.create(
                task=self, series_id=self.series_id, title=self.title,
                result=result, due_date=None, auto_expired=auto_expired,
                user=self.user,
            )
        obj, _ = Occurrence.objects.update_or_create(
            series_id=self.series_id, due_date=self.due_date,
            defaults=dict(
                task=self, title=self.title, result=result,
                auto_expired=auto_expired, user=self.user,
            ),
        )
        return obj

    def mark_done(self):
        self.is_done = True
        self.expired = False
        self.completed_at = timezone.now()
        self.reopened_at = None
        self.save()
        self._record_occurrence(Occurrence.RESULT_DONE)
        self._spawn_next()

    def reopen(self, delete_sessions=False):
        """
        Deshace el haber marcado la tarea, dejándolo TODO como estaba.

        Es distinto de mark_not_done(), que registra un "no la hice" (y
        por tanto cuenta como fallo en la racha). Esto es "me equivoqué al
        marcarla", así que hay que revertir las tres cosas que provocó
        marcarla:

          1. La tarea vuelve a pendiente.
          2. Se BORRA la ocurrencia de ese día — no se cambia a "no
             hecha", se elimina. Si no, la racha seguiría contando ese día
             como registrado y las estadísticas no volverían a su sitio.
          3. Se borra la instancia siguiente que se generó al marcarla
             (mañana, la semana que viene...), siempre que nadie la haya
             tocado todavía. Sin esto quedaría una tarea duplicada
             flotando en el futuro.

        Las sesiones de entreno se conservan por defecto: las
        repeticiones las hiciste de verdad aunque te equivocaras al
        marcar la tarea.
        """
        # 3. La instancia futura de la serie, si sigue intacta.
        if self.repeat != self.REPEAT_NONE and self.due_date:
            (
                Task.objects.filter(
                    series_id=self.series_id,
                    due_date__gt=self.due_date,
                    is_done=False,
                    expired=False,
                )
                .exclude(pk=self.pk)
                .delete()
            )

        # 2. La ocurrencia de este día.
        if self.due_date is not None:
            Occurrence.objects.filter(series_id=self.series_id, due_date=self.due_date).delete()
        else:
            Occurrence.objects.filter(series_id=self.series_id, task=self).delete()

        if delete_sessions:
            self.workout_sessions.all().delete()

        # 1. La tarea vuelve a estar disponible.
        self.is_done = False
        self.expired = False
        self.completed_at = None
        self.reopened_at = timezone.now()
        self.save()

    def mark_not_done(self):
        """
        Se usa para "Desmarcar" una tarea ya hecha (volver a pendiente) y
        también para loguear un "no" desde pendientes sin resolver el día.
        A propósito NO genera la siguiente ocurrencia — si lo hiciera,
        "Desmarcar" ya no podría deshacer nada (is_done volvería a True
        en el mismo instante). Para antitareas, el botón "he caído hoy"
        usa mark_failed() en su lugar, que sí resuelve el día.
        """
        self.is_done = False
        self.expired = False
        self.completed_at = None
        self.reopened_at = timezone.now()
        self.save()
        self._record_occurrence(Occurrence.RESULT_NOT_DONE)

    def mark_failed(self):
        """
        Para antitareas: "he caído hoy". A diferencia de mark_not_done()
        (que deja is_done=False porque también sirve para deshacer una
        tarea ya hecha), esto SÍ resuelve el día como mark_done() —
        is_done=True y genera la siguiente ocurrencia si se repite. Sin
        esto, una antitarea diaria se quedaría colgada la primera vez que
        cayeras, en vez de seguir pidiéndote el check-in cada noche.
        """
        self.is_done = True
        self.expired = False
        self.completed_at = timezone.now()
        self.reopened_at = None
        self.save()
        self._record_occurrence(Occurrence.RESULT_NOT_DONE)
        self._spawn_next()

    def mark_expired(self):
        """
        Llamado cuando pasa la hora límite sin que se haya marcado nada.

        Para una tarea normal, silencio = no lo hiciste (fallo). Para una
        antitarea (is_avoid=True) es justo al revés: silencio = no caíste,
        así que cuenta como éxito. La única diferencia está en qué
        resultado se guarda; is_done/expired se comportan igual en ambos
        casos (la tarea se resuelve sola, sin que tengas que tocar nada).
        """
        self.is_done = True
        self.expired = True
        self.completed_at = timezone.now()
        self.reopened_at = None
        self.save()
        result = Occurrence.RESULT_DONE if self.is_avoid else Occurrence.RESULT_NOT_DONE
        self._record_occurrence(result, auto_expired=True)
        self._spawn_next()

    @classmethod
    def expire_overdue(cls, dry_run=False):
        """
        Cierra las tareas vencidas y registra su resultado.

        Se repite hasta que no quede nada por cerrar: al cerrar una tarea
        repetida se genera la siguiente, y si esa TAMBIÉN está vencida hay
        que cerrarla igual. Sin este bucle, pasar cuatro días sin abrir la
        app registraba un solo día en vez de cuatro — justo lo contrario
        de lo que se busca, porque los huecos aparecían cuando peor lo
        habías hecho.

        El tope de vueltas es una red de seguridad: si algo hiciera que
        una tarea nunca deje de estar vencida, esto se para en vez de
        colgar la página.
        """
        expired_tasks = []
        for _ in range(400):   # ~un año de tareas diarias atrasadas
            done_this_round = cls._expire_pass(dry_run=dry_run)
            expired_tasks.extend(done_this_round)
            # En dry_run no se marca nada, así que la siguiente vuelta
            # encontraría lo mismo: una pasada es suficiente.
            if not done_this_round or dry_run:
                break
        return expired_tasks

    @classmethod
    def _expire_pass(cls, dry_run=False):
        """
        Una sola pasada. Revisa las tareas pendientes con hora límite y
        marca como expiradas las que ya han pasado esa hora.

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
            # Ahora TODAS las tareas con hora tienen un momento límite
            # absoluto (las que no llevan fecha se anclan a su día de
            # creación — ver deadline_datetime), así que no hace falta la
            # comparación de horas sueltas que fallaba al pasar la
            # medianoche.
            limit = task.resolve_datetime()
            if limit is None:
                continue

            # Si devolviste la tarea a pendientes DESPUÉS de su hora
            # límite, es que ya decidiste tú: no se auto-resuelve.
            #
            # Se usa una marca explícita (reopened_at) y no "cuándo se
            # modificó por última vez", porque una tarea CREADA después
            # de su hora límite también se habría modificado después, y
            # nunca llegaría a expirar.
            if task.reopened_at is not None:
                reopened = timezone.localtime(task.reopened_at).replace(tzinfo=None)
                if reopened > limit:
                    continue

            # resolve_datetime ya incluye el margen de las antitareas: a
            # la hora límite salta el aviso, y solo pasado ese rato sin
            # respuesta se resuelve sola.
            if now_local > limit:
                if not dry_run:
                    task.mark_expired()
                expired_tasks.append(task)

        return expired_tasks


class Exercise(models.Model):
    """
    Catálogo de ejercicios disponibles. Es la pieza base para poder montar
    rutinas (ej. "Upper body" = dominadas + fondos + abdominales) sin tener
    que crear una Task por cada ejercicio.

    `mode` dice qué tipo de seguimiento necesita:
      - pose:     la cámara cuenta las reps (MediaPipe). Necesita counter_key.
      - manual:   el usuario escribe las reps/peso a mano (ej. mancuernas).
      - timed:    solo se mide duración (ej. plancha).
      - distance: cardio — distancia + tiempo (ej. correr).

    `counter_key` identifica qué contador de workout.js usar cuando mode es
    "pose" (ej. "pullup"). Varios ejercicios pueden compartir contador con
    distinta config: "dominadas" y "dominadas anchas" usan el mismo
    contador de dominadas, solo cambia `config` (umbrales, etc.).
    """
    MODE_POSE = "pose"
    MODE_MANUAL = "manual"
    MODE_TIMED = "timed"
    MODE_DISTANCE = "distance"

    MODE_CHOICES = [
        (MODE_POSE, "Cámara (pose tracking)"),
        (MODE_MANUAL, "Manual (reps a mano)"),
        (MODE_TIMED, "Cronometrado"),
        (MODE_DISTANCE, "Distancia (cardio)"),
    ]

    name = models.CharField(max_length=64)
    slug = models.SlugField(max_length=64, unique=True)
    mode = models.CharField(max_length=16, choices=MODE_CHOICES, default=MODE_MANUAL)
    body_area = models.CharField(
        max_length=16,
        choices=Task.SUBCATEGORY_CHOICES,
        blank=True,
        db_index=True,
        help_text="A qué subcategoría de Deporte pertenece (tren superior/inferior/running). "
                   "Vacío = aparece en el selector pase lo que pase.",
    )
    counter_key = models.CharField(
        max_length=32, blank=True,
        help_text="Qué contador de workout.js usar (solo aplica si mode='pose'). Ej: 'pullup'.",
    )
    config = models.JSONField(
        default=dict, blank=True,
        help_text="Umbrales/ajustes propios de este ejercicio para el contador (opcional).",
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Routine(models.Model):
    """
    Circuito reutilizable de ejercicios cronometrados (ej. "Abdominales
    completo"): una lista ordenada de Exercise con su tiempo de trabajo y
    descanso, para no tener que montarlo cada vez desde cero. Pensada para
    ejercicios mode='timed' (plancha, crunch…), aunque no se fuerza aquí —
    quien monta la rutina decide qué mete.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name="routines",
    )
    name = models.CharField(max_length=64)
    subcategory = models.CharField(
        max_length=16, choices=Task.SUBCATEGORY_CHOICES, blank=True,
        help_text="Para poder ofrecer esta rutina desde el selector de esa subcategoría de Deporte.",
    )
    default_work_seconds = models.PositiveIntegerField(default=40)
    default_rest_seconds = models.PositiveIntegerField(default=20)
    created_at = models.DateTimeField(auto_now_add=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def total_seconds(self):
        """Duración estimada del circuito completo, en orden (sin contar
        que el usuario pueda saltarse o repetir ejercicios).

        Los ejercicios de cámara no tienen duración fija — dependen de lo
        rápido que hagas las reps — así que se estiman a 4 segundos por
        repetición, solo para dar una idea del tamaño del circuito.
        """
        items = list(self.items.select_related("exercise"))
        total = 0
        for i, item in enumerate(items):
            if item.exercise.mode == Exercise.MODE_POSE:
                total += item.target_sets * item.target_reps * 4
            else:
                total += item.effective_work_seconds
            if i < len(items) - 1:
                total += item.effective_rest_seconds
        return total


class RoutineItem(models.Model):
    """Un ejercicio dentro de una Routine, con su orden y tiempos propios
    (si se dejan en blanco, usa los defaults de la rutina).

    Un circuito puede mezclar los dos tipos de ejercicio, y cada uno se
    mide con lo que le corresponde:
      - Cronometrados (plancha, crunch): work_seconds / rest_seconds.
      - De cámara (dominadas, fondos): target_sets x target_reps. Contar
        segundos de dominadas no dice nada; lo que importa son las reps.

    Los objetivos son además la base del "planning" progresivo: subir de
    3x8 a 3x9 la semana siguiente es cambiar un número aquí.
    """
    routine = models.ForeignKey(Routine, on_delete=models.CASCADE, related_name="items")
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)
    work_seconds = models.PositiveIntegerField(null=True, blank=True)
    rest_seconds = models.PositiveIntegerField(null=True, blank=True)
    target_sets = models.PositiveIntegerField(
        default=3, help_text="Solo para ejercicios de cámara: series objetivo."
    )
    target_reps = models.PositiveIntegerField(
        default=8, help_text="Solo para ejercicios de cámara: repeticiones por serie."
    )

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.routine.name} #{self.order}: {self.exercise.name}"

    @property
    def effective_work_seconds(self):
        return self.work_seconds if self.work_seconds is not None else self.routine.default_work_seconds

    @property
    def effective_rest_seconds(self):
        return self.rest_seconds if self.rest_seconds is not None else self.routine.default_rest_seconds


class WorkoutSession(models.Model):
    """
    Estadísticas de una sesión de entreno. La mayoría se graban con la
    cámara (MediaPipe, en el navegador) — no se guarda ningún vídeo, solo
    los números que salen del conteo. Las de running (mode=distance) se
    escriben a mano (cinta, reloj, Samsung Health…): ahí total_reps se
    queda a 0 y lo que importa es distance_km / steps.
    """
    EXERCISE_PULLUP = "pullup"  # se usa como valor por defecto y de respaldo

    task = models.ForeignKey(
        Task, on_delete=models.SET_NULL, null=True, blank=True, related_name="workout_sessions"
    )
    routine = models.ForeignKey(
        Routine, on_delete=models.SET_NULL, null=True, blank=True, related_name="workout_sessions",
        help_text="Si esta sesión vino de un circuito (Routine), cuál. En blanco para ejercicios sueltos.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name="workout_sessions",
        help_text="Dueño de la sesión. Ver Task.user para el mismo criterio.",
    )
    series_id = models.UUIDField(null=True, blank=True)
    # Guarda el slug del Exercise (ej. "pullup", "squat"). Antes tenía
    # choices=EXERCISE_CHOICES, una lista aparte que había que mantener a
    # mano sincronizada con la tabla Exercise — si añadías un ejercicio
    # desde /admin, no aparecía aquí y el nombre salía en crudo (el slug).
    # Ahora el nombre se resuelve en caliente contra el catálogo, ver
    # exercise_name más abajo: un único sitio de verdad.
    exercise = models.CharField(max_length=32, default=EXERCISE_PULLUP)
    total_reps = models.PositiveIntegerField(default=0)
    total_sets = models.PositiveIntegerField(default=0)
    sets = models.JSONField(default=list, blank=True)  # [{"reps": 8, "durations": [1.1, ...]}, ...]
    session_duration_seconds = models.PositiveIntegerField(default=0)
    avg_rep_seconds = models.FloatField(null=True, blank=True)
    rest_alerts_triggered = models.PositiveIntegerField(default=0)
    rep_durations = models.JSONField(default=list, blank=True)  # [1.1, 1.3, ...] segundos por rep
    added_weight_kg = models.FloatField(
        null=True, blank=True,
        help_text="Peso extra usado (ej. chaleco lastrado en dominadas con peso). No lo mide la cámara, se anota a mano.",
    )
    distance_km = models.FloatField(null=True, blank=True, help_text="Solo running: km recorridos.")
    steps = models.PositiveIntegerField(null=True, blank=True, help_text="Solo running: pasos, si los tienes (cinta, reloj…).")
    recorded_at = models.DateTimeField(auto_now_add=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-recorded_at"]

    @property
    def exercise_name(self):
        """Nombre legible del ejercicio, resuelto contra el catálogo
        Exercise. Si el slug no está en el catálogo (ej. se borró desde
        /admin después de guardar esta sesión), cae al slug en crudo en
        vez de romper."""
        ex = Exercise.objects.filter(slug=self.exercise).first()
        return ex.name if ex else self.exercise

    def __str__(self):
        if self.distance_km is not None:
            return f"{self.exercise_name} — {self.distance_km}km ({self.recorded_at:%Y-%m-%d %H:%M})"
        return f"{self.exercise_name} — {self.total_reps} reps ({self.recorded_at:%Y-%m-%d %H:%M})"


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
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name="occurrences",
        help_text="Dueño de la ocurrencia. Ver Task.user para el mismo criterio.",
    )
    series_id = models.UUIDField()
    title = models.CharField(max_length=255)
    result = models.CharField(max_length=10, choices=RESULT_CHOICES)
    due_date = models.DateField(null=True, blank=True)
    auto_expired = models.BooleanField(default=False)
    recorded_at = models.DateTimeField(auto_now_add=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-recorded_at"]
        constraints = [
            # Un único resultado por día y serie. Ver Task._record_occurrence:
            # el resultado de un día es un hecho corregible, no un log que se
            # apila. Solo aplica cuando hay due_date — las tareas sueltas sin
            # fecha no tienen "día" al que anclarse.
            models.UniqueConstraint(
                fields=["series_id", "due_date"],
                condition=models.Q(due_date__isnull=False),
                name="unique_occurrence_per_series_day",
            ),
        ]

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
