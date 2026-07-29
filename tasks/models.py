import datetime as _dt
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
    def workout_kind(self):
        """
        Qué clase de sesión abre esta tarea, para que el botón de la lista
        no prometa algo que no va a pasar.

        Antes cualquier tarea de Deporte enseñaba el icono de cámara,
        aunque fuera un circuito de abdominales a cronómetro o una salida
        a correr que se rellena a mano. Enseñar una cámara ahí es
        incongruente.
        """
        if self.category != self.CATEGORY_SPORT:
            return None
        if self.subcategory == self.SUBCATEGORY_RUNNING:
            return "distance"      # se anota a mano
        if self.subcategory == self.SUBCATEGORY_LOWER_BODY:
            return "timer"         # circuitos cronometrados
        return "camera"            # tren superior: conteo con cámara

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

    def plan_entry(self, user=None):
        """
        El ejercicio dentro de un plan activo, si lo hay.

        Es lo que permite convivir plan y "freestyle": si este ejercicio
        forma parte de un plan en marcha, manda el plan; si no, mandan los
        objetivos fijos del circuito y entrenas a tu aire.
        """
        owner = user or self.routine.user
        return (
            PlanItem.objects
            .filter(
                exercise=self.exercise,
                plan__is_active=True,
                plan__deleted_at__isnull=True,
                plan__user=owner,
            )
            .select_related("plan")
            .order_by("-plan__started_on")
            .first()
        )

    def resolved_target(self, user=None):
        """
        Lo que toca hacer hoy en este ejercicio, mire quien lo mire.

        Devuelve también de dónde sale el número (`source`), porque en
        pantalla no es lo mismo "3x8 porque lo pusiste en el circuito"
        que "3x9 porque tu plan va por ahí" — y el usuario necesita
        entender por qué le pide eso.
        """
        entry = self.plan_entry(user)
        if entry:
            target = entry.current_target()
            successes, _ = entry.successes_and_streak()
            return {
                "sets": target["sets"],
                "reps": target["reps"],
                "seconds": target["seconds"] or self.effective_work_seconds,
                "weight_kg": target.get("weight_kg") or 0,
                "source": "plan",
                "plan_name": entry.plan.name,
                "plan_uuid": str(entry.plan.uuid),
                "session_index": successes + 1,
                "sessions_to_goal": entry.sessions_to_goal(),
            }
        return {
            "sets": self.target_sets,
            "reps": self.target_reps,
            "seconds": self.effective_work_seconds,
            "weight_kg": 0,
            "source": "routine",
            "plan_name": None,
            "plan_uuid": None,
            "session_index": None,
            "sessions_to_goal": None,
        }


class Plan(models.Model):
    """
    Un objetivo con progresión: "ponerme en forma", "preparar el DALF".

    Cuelga del OBJETIVO, no de un circuito, porque es lo que la gente
    quiere de verdad — nadie se propone "hacer 8 repeticiones", se
    propone estar más en forma. Los circuitos y ejercicios son las
    tácticas; el plan es hacia dónde van.

    Puede abarcar varios ejercicios de varios circuitos a la vez.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name="plans",
    )
    name = models.CharField(max_length=80)
    notes = models.TextField(blank=True)
    started_on = models.DateField(default=_dt.date.today)
    weeks = models.PositiveIntegerField(
        default=12, help_text="Duración prevista. 12 semanas por defecto (12 Week Year).",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-is_active", "-started_on"]

    def __str__(self):
        return self.name

    @property
    def ends_on(self):
        return self.started_on + timedelta(weeks=self.weeks)

    @property
    def week_number(self):
        """En qué semana del plan estamos (1 = la primera)."""
        days = (timezone.localtime(timezone.now()).date() - self.started_on).days
        return max(1, days // 7 + 1)


class PlanItem(models.Model):
    """
    Una cosa que se persigue dentro de un plan.

    Puede ser un EJERCICIO (dominadas, plancha) o una TAREA cualquiera
    (estudiar francés, no fumar), porque un plan de verdad mezcla las dos
    cosas: "ponerme en forma" y "aprender francés" caben en el mismo
    trimestre.

    Y sobre todo: no todo progresa igual. Estudiar 2 horas no se
    convierte en 2 horas y media hasta el infinito — lo que se mide es si
    lo cumpliste. Por eso hay tres formas de avanzar:

      - cumplimiento: objetivo fijo. Se mide cuántas veces lo cumpliste.
        Para estudiar, antitareas, hábitos.
      - repeticiones: sube hasta un techo y ahí se queda.
        Para abdominales, plancha, resistencia.
      - doble: sube repeticiones dentro de un rango y, al llegar arriba,
        AÑADE PESO y vuelve abajo del rango.
        Para fuerza: dominadas, fondos, sentadillas.

    La progresión doble es la que evita el disparate. Una progresión
    lineal siempre diverge: subiendo 1 repetición cada 2 sesiones, a los
    seis meses el plan pediría 3x47 dominadas. Con la doble, las
    repeticiones vuelven siempre al suelo del rango y lo que sube es la
    carga — que es como se progresa de verdad.
    """
    PROG_COMPLETION = "completion"
    PROG_REPS = "reps"
    PROG_DOUBLE = "double"

    PROGRESSION_CHOICES = [
        (PROG_COMPLETION, "Cumplimiento (objetivo fijo)"),
        (PROG_REPS, "Repeticiones (sube hasta un techo)"),
        (PROG_DOUBLE, "Doble (repeticiones y luego peso)"),
    ]

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="items")

    # Una de las dos: a qué se refiere este objetivo.
    exercise = models.ForeignKey(
        Exercise, on_delete=models.CASCADE, null=True, blank=True,
        help_text="Para objetivos de ejercicio.",
    )
    series_id = models.UUIDField(
        null=True, blank=True,
        help_text="Para objetivos de tarea (estudiar, no fumar). Es la serie de la tarea.",
    )
    label = models.CharField(
        max_length=80, blank=True,
        help_text="Cómo llamarlo. En blanco usa el nombre del ejercicio o la tarea.",
    )

    progression = models.CharField(
        max_length=12, choices=PROGRESSION_CHOICES, default=PROG_REPS,
    )

    # Punto de partida
    start_sets = models.PositiveIntegerField(default=3)
    start_reps = models.PositiveIntegerField(default=8)
    start_seconds = models.PositiveIntegerField(default=40)
    start_weight_kg = models.FloatField(default=0)

    # Destino: hasta dónde quieres llegar. Sin esto el plan no sabría
    # cuándo ha terminado y subiría para siempre.
    goal_sets = models.PositiveIntegerField(null=True, blank=True)
    goal_reps = models.PositiveIntegerField(null=True, blank=True)
    goal_seconds = models.PositiveIntegerField(null=True, blank=True)
    goal_weight_kg = models.FloatField(null=True, blank=True)

    # Cómo avanza
    sessions_per_step = models.PositiveIntegerField(
        default=2, help_text="Cada cuántas sesiones cumplidas se sube un escalón.",
    )
    reps_increment = models.PositiveIntegerField(default=1)
    weight_increment_kg = models.FloatField(
        default=2.5, help_text="Solo en progresión doble: cuánto peso se añade al completar el rango.",
    )
    rep_range_low = models.PositiveIntegerField(
        default=6, help_text="Solo en progresión doble: a cuántas repeticiones se vuelve al subir peso.",
    )

    # El toque de entrenador
    deload_after_failures = models.PositiveIntegerField(
        default=3,
        help_text="Tras estas sesiones seguidas sin llegar al objetivo, se baja un escalón. "
                   "0 lo desactiva.",
    )

    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.plan.name}: {self.display_name}"

    @property
    def display_name(self):
        if self.label:
            return self.label
        if self.exercise:
            return self.exercise.name
        occ = Occurrence.objects.filter(series_id=self.series_id).first()
        return occ.title if occ else "Objetivo"

    @property
    def is_timed(self):
        return bool(self.exercise and self.exercise.mode == Exercise.MODE_TIMED)

    # ------------------------------------------------------- historial

    def _sessions(self):
        """Sesiones de este objetivo dentro del plan, en orden."""
        if not self.exercise:
            return WorkoutSession.objects.none()
        return WorkoutSession.objects.filter(
            plan=self.plan, exercise=self.exercise.slug, deleted_at__isnull=True
        ).order_by("recorded_at")

    def _occurrences(self):
        """Para objetivos de tarea: los días registrados de esa serie."""
        if not self.series_id:
            return Occurrence.objects.none()
        return Occurrence.objects.filter(
            series_id=self.series_id, deleted_at__isnull=True,
            recorded_at__date__gte=self.plan.started_on,
        ).order_by("recorded_at")

    def successes_and_streak(self):
        """
        Cuántas veces se cumplió el objetivo, y cuántos fallos seguidos
        van al final. Lo segundo es lo que dispara la bajada de escalón.
        """
        if self.progression == self.PROG_COMPLETION:
            results = [
                o.result == Occurrence.RESULT_DONE for o in self._occurrences()
            ] if self.series_id else [
                (s.achievement_pct or 0) >= 100 for s in self._sessions()
            ]
        else:
            results = [(s.achievement_pct or 0) >= 100 for s in self._sessions()]

        successes = sum(1 for r in results if r)
        streak = 0
        for r in reversed(results):
            if r:
                break
            streak += 1
        return successes, streak

    def current_step(self):
        """
        En qué escalón estás.

        Avanza con las sesiones CUMPLIDAS, no con las hechas: si te
        quedas corto, el objetivo no sube — que es justo lo que haría un
        entrenador. Y si fallas varias veces seguidas, baja uno, para no
        quedarte atascado para siempre en un número que hoy no puedes.
        """
        successes, failure_streak = self.successes_and_streak()
        step = successes // max(1, self.sessions_per_step)
        if self.deload_after_failures and failure_streak >= self.deload_after_failures:
            step = max(0, step - 1)
        return step

    # -------------------------------------------------------- objetivo

    def target_for_step(self, step):
        """El objetivo en el escalón `step` (0 = el primero)."""
        if self.progression == self.PROG_COMPLETION:
            return {
                "sets": self.start_sets, "reps": self.start_reps,
                "seconds": self.start_seconds if self.is_timed else None,
                "weight_kg": self.start_weight_kg, "done": False,
            }

        if self.progression == self.PROG_DOUBLE:
            top = self.goal_reps or (self.rep_range_low + 6)
            low = min(self.rep_range_low, top)
            span = max(1, top - low + 1)
            cycles, within = divmod(step, span)
            reps = low + within
            weight = self.start_weight_kg + cycles * self.weight_increment_kg
            if self.goal_weight_kg is not None and weight >= self.goal_weight_kg:
                # Llegado el peso objetivo, se deja de añadir carga y solo
                # quedan las repeticiones que falten para cerrar el plan.
                weight = self.goal_weight_kg
                reps = min(low + within, top)
            done = (
                self.goal_weight_kg is not None
                and weight >= self.goal_weight_kg
                and reps >= top
            )
            return {
                "sets": self.goal_sets or self.start_sets, "reps": reps,
                "seconds": None, "weight_kg": round(weight, 1), "done": done,
            }

        # PROG_REPS: sube hasta el techo y ahí se queda.
        if self.is_timed:
            seconds = self.start_seconds + step * self.reps_increment
            ceiling = self.goal_seconds
            if ceiling:
                seconds = min(seconds, ceiling)
            return {
                "sets": self.goal_sets or self.start_sets, "reps": None,
                "seconds": seconds, "weight_kg": self.start_weight_kg,
                "done": bool(ceiling and seconds >= ceiling),
            }

        reps = self.start_reps + step * self.reps_increment
        ceiling = self.goal_reps
        if ceiling:
            reps = min(reps, ceiling)
        return {
            "sets": self.goal_sets or self.start_sets, "reps": reps,
            "seconds": None, "weight_kg": self.start_weight_kg,
            "done": bool(ceiling and reps >= ceiling),
        }

    def current_target(self):
        return self.target_for_step(self.current_step())

    def schedule(self, count=12):
        """La tabla de progresión, para ver el camino antes de empezar."""
        rows = []
        for i in range(count):
            row = dict(step=i + 1, **self.target_for_step(i))
            rows.append(row)
            if row["done"]:
                break      # llegado el destino, no hay más que enseñar
        return rows

    def sessions_to_goal(self, limit=200):
        """Cuántas sesiones cumplidas faltan para el destino, o None si
        el objetivo no tiene final definido."""
        for i in range(self.current_step(), limit):
            if self.target_for_step(i)["done"]:
                return max(0, (i - self.current_step()) * self.sessions_per_step)
        return None


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
    plan = models.ForeignKey(
        Plan, on_delete=models.SET_NULL, null=True, blank=True, related_name="workout_sessions",
        help_text="Plan al que contaba esta sesión, si había uno activo.",
    )
    # Objetivo que estaba vigente en ESE momento. Se guarda en la sesión
    # en vez de recalcularlo después, porque el objetivo sube con las
    # sesiones: si se recalculara, el historial de hace un mes se
    # compararía con el objetivo de hoy y saldría un porcentaje falso.
    target_reps = models.PositiveIntegerField(null=True, blank=True)
    target_sets = models.PositiveIntegerField(null=True, blank=True)
    target_seconds = models.PositiveIntegerField(null=True, blank=True)
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
    def achievement_pct(self):
        """
        Qué porcentaje del objetivo se cumplió, o None si no había.

        Se compara el TOTAL hecho contra el TOTAL pedido (series ×
        repeticiones), no serie por serie. Si el objetivo era 3×10 y
        hiciste 4×8, eso son 32 de 30 — lo hiciste, aunque repartido
        distinto. Contar serie a serie penalizaría una forma de entrenar
        que es igual de válida.
        """
        if self.target_sets and self.target_reps:
            objetivo = self.target_sets * self.target_reps
            hecho = self.total_reps
        elif self.target_sets and self.target_seconds:
            objetivo = self.target_sets * self.target_seconds
            hecho = self.session_duration_seconds
        else:
            return None
        if not objetivo:
            return None
        return round(100 * hecho / objetivo)

    @property
    def target_label(self):
        """El objetivo en texto, para enseñarlo junto al resultado."""
        if self.target_sets and self.target_reps:
            return f"{self.target_sets} × {self.target_reps}"
        if self.target_sets and self.target_seconds:
            return f"{self.target_sets} × {self.target_seconds}s"
        return ""

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
