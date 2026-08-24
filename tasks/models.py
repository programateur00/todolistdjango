import datetime as _dt
import re
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

# Formatos aceptados al pegar un vídeo de YouTube (RoutineItem.youtube_video_id):
# enlace completo (youtube.com/watch?v=, youtu.be/, youtube.com/shorts/,
# youtube.com/embed/) o directamente el ID de 11 caracteres. Así no hay que
# ir a buscar el ID a mano cada vez que se pega un enlace.
_YOUTUBE_ID_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/))([A-Za-z0-9_-]{11})"
)

# El ID de una playlist va en el parámetro ?list=... de cualquier URL de
# YouTube (a veces junto a un vídeo concreto, a veces solo). Empieza casi
# siempre por "PL", "UU", "LL" o "FL", pero no hace falta comprobarlo — con
# que aparezca list=algo ya vale.
_YOUTUBE_PLAYLIST_ID_RE = re.compile(r"[?&]list=([A-Za-z0-9_-]+)")

# Niveles MCER (A1→C2), a nivel de módulo porque tanto Task (el nivel del
# vídeo concreto de hoy) como Plan (el rango de nivel del curso entero) lo
# necesitan, y Task se define antes que Plan en este archivo.
CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
CEFR_LEVEL_CHOICES = [(lvl, lvl) for lvl in CEFR_LEVELS]


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
        (CATEGORY_WORK, "Enfoque"),
        (CATEGORY_PERSONAL, "Personal"),
        (CATEGORY_OTHER, "Otro"),
        (CATEGORY_AVOID, "Antitarea"),
    ]

    # Metadatos que describen qué "extras" admite cada categoría.
    # Útil para que la UI sepa si mostrar el botón de iniciar timer,
    # el panel de cámara de MediaPipe, etc.
    #
    # CATEGORY_WORK ("Enfoque") era antes "Trabajo" sin ningún extra
    # construido — se reutiliza el mismo hueco (misma clave "work" en la
    # base de datos, así las tareas que ya tuvieras no se mueven de
    # categoría) para el temporizador manual: leer, estudiar, estirar…
    # cualquier cosa que quieras cronometrar sin que sea deporte.
    CATEGORY_CAPABILITIES = {
        CATEGORY_GENERAL: [],
        CATEGORY_STUDY: [],
        CATEGORY_SPORT: ["timer", "pose_tracking"],
        CATEGORY_WORK: ["timer", "app_usage"],
        CATEGORY_PERSONAL: [],
        CATEGORY_OTHER: [],
        CATEGORY_AVOID: [],
    }

    # Subcategorías de "Deporte": filtran qué ejercicios del catálogo
    # (Exercise.body_area) aparecen al entrenar.
    SUBCATEGORY_UPPER_BODY = "upper_body"
    SUBCATEGORY_LOWER_BODY = "lower_body"
    SUBCATEGORY_RUNNING = "running"
    SPORT_SUBCATEGORY_CHOICES = [
        (SUBCATEGORY_UPPER_BODY, "Tren superior"),
        (SUBCATEGORY_LOWER_BODY, "Tren inferior"),
        (SUBCATEGORY_RUNNING, "Running"),
    ]

    # Subcategorías de "Enfoque": qué se está cronometrando. Todas
    # comparten el mismo temporizador manual (ver TimerSession); solo
    # "Lectura" puede además usar el tiempo real en una app externa
    # (Adobe, Kindle…) cuando hay plugin nativo instalado — ver
    # TimerSession.SOURCE_APP_USAGE.
    SUBCATEGORY_READING = "reading"
    SUBCATEGORY_STUDY_SESSION = "study_session"
    SUBCATEGORY_STRETCH = "stretch"
    SUBCATEGORY_FOCUS_OTHER = "focus_other"
    FOCUS_SUBCATEGORY_CHOICES = [
        (SUBCATEGORY_READING, "Lectura"),
        (SUBCATEGORY_STUDY_SESSION, "Estudio"),
        (SUBCATEGORY_STRETCH, "Estiramientos"),
        (SUBCATEGORY_FOCUS_OTHER, "Otro"),
    ]

    # Subcategorías de "Estudio": de momento solo "Idiomas" — un curso con
    # vídeos organizados por nivel (ver Plan.STUDY_SUBTYPE_LANGUAGE y
    # CourseModule), en vez del hábito diario simple de siempre. En
    # blanco sigue siendo el Estudio de toda la vida, sin curso detrás.
    SUBCATEGORY_LANGUAGE = "language"
    STUDY_SUBCATEGORY_CHOICES = [
        (SUBCATEGORY_LANGUAGE, "Idiomas"),
    ]

    SUBCATEGORY_CHOICES = SPORT_SUBCATEGORY_CHOICES + FOCUS_SUBCATEGORY_CHOICES + STUDY_SUBCATEGORY_CHOICES

    # Mismo MCER que Plan.CEFR_LEVEL_CHOICES (ver constante de módulo
    # arriba) — expuesto también aquí para leer/validar Task.level sin
    # tener que importar Plan.
    CEFR_LEVEL_CHOICES = CEFR_LEVEL_CHOICES

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
    # Columna heredada de una fase muy anterior del proyecto — ya no se
    # usa para nada, pero sigue existiendo como NOT NULL en bases de
    # datos ya desplegadas (la tuya incluida), y por eso hace falta que
    # el modelo la conozca: si Django no la incluye al crear una tarea,
    # SQLite la rechaza por violar esa restricción. default=False para
    # que cualquier creación (incluida la de Plan.sync_task()) la
    # rellene sola sin que nadie tenga que acordarse de ella.
    wants_timer = models.BooleanField(default=False)
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
        help_text="Deporte → qué entrenar. Enfoque → qué cronometrar. En el resto no se usa.",
    )
    # Idioma + nivel de ESTA tarea concreta — independiente de si viene de
    # un Plan de Idiomas o se crea suelta a mano (subcategory=SUBCATEGORY_LANGUAGE
    # en cualquiera de los dos casos). Un solo nivel, no un rango como en
    # Plan.level_from/level_to: una tarea es un vídeo del día, no un curso
    # entero. Si la tarea viene de Plan.sync_task(), este nivel es el del
    # CourseModule que toca hoy — puede no coincidir con el nivel objetivo
    # del plan (level_to), que es el destino final, no dónde estás ahora.
    language_name = models.CharField(max_length=40, blank=True)
    level = models.CharField(max_length=2, blank=True, choices=CEFR_LEVEL_CHOICES)
    target_minutes = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Objetivo en minutos para tareas de Enfoque (category='work'). Ej. 60 para 'leer una hora'.",
    )
    youtube_video_id = models.CharField(
        max_length=255, blank=True,
        help_text="ID o URL de un vídeo de YouTube (ej. 'dQw4w9WgXcQ' o el enlace completo — "
                   "se limpia solo al guardar). Si está puesto, esta tarea NO pasa por el "
                   "selector de ejercicios ni por el temporizador: al darle a play se va "
                   "directa al vídeo embebido, y al terminar se marca como hecha ella sola. "
                   "Streaming en directo: no se descarga ni se guarda nada.",
    )
    youtube_playlist_id = models.CharField(
        max_length=255, blank=True,
        help_text="Alternativa a youtube_video_id: ID o URL de una playlist de YouTube "
                   "(el trozo list=... del enlace). Junto con target_minutes o "
                   "target_video_count decide cuándo se da por vista.",
    )
    target_video_count = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Solo con youtube_playlist_id: cuántos vídeos de la lista hay que ver "
                   "para dar la tarea por hecha (ej. 5). Si no se pone y tampoco hay "
                   "target_minutes, se da por hecha al terminar 1 vídeo de la lista.",
    )
    playlist_start_index = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Solo con youtube_playlist_id, en un objetivo de Estudio · Hábito simple "
                   "con seguimiento de progreso (ver PlanItem.playlist_videos_cache): en qué "
                   "posición de la lista (0 = el primero) hay que empezar a reproducir hoy, "
                   "para no volver siempre al principio de la playlist. En blanco = empezar "
                   "por el principio, como antes de que existiera esto (playlist sin "
                   "seguimiento, o un vídeo/playlist sueltos fuera de un plan).",
    )
    # Cómo se completa una tarea de Deporte. Se elige al crearla, no cada
    # vez que se entrena: es una decisión de "qué es esta tarea", no de
    # "qué me apetece hoy". Qué modos valen depende del subtipo — el
    # conteo con cámara no tiene sentido en tren inferior, y correr no
    # se hace con circuitos.
    SPORT_MODE_CAMERA = "camera"
    SPORT_MODE_CIRCUIT = "circuit"
    SPORT_MODE_VIDEO = "video"
    SPORT_MODE_CHOICES = [
        (SPORT_MODE_CAMERA, "Conteo con la cámara"),
        (SPORT_MODE_CIRCUIT, "Circuito"),
        (SPORT_MODE_VIDEO, "Vídeo"),
    ]
    # Qué modos se ofrecen en cada subtipo. Running no aparece: se
    # resuelve siempre importando la actividad (Health Connect) o a mano.
    SPORT_MODES_BY_SUBCATEGORY = {
        "upper_body": [SPORT_MODE_CAMERA, SPORT_MODE_CIRCUIT, SPORT_MODE_VIDEO],
        "lower_body": [SPORT_MODE_CAMERA, SPORT_MODE_CIRCUIT, SPORT_MODE_VIDEO],
    }
    sport_mode = models.CharField(
        max_length=20, choices=SPORT_MODE_CHOICES, blank=True, default="",
        help_text="Solo Deporte (tren superior/inferior): cómo se completa la tarea.",
    )

    has_local_video = models.BooleanField(
        default=False,
        help_text="Alternativa a youtube_video_id: el vídeo es un archivo del propio "
                   "dispositivo (elegido con el selector nativo), no de YouTube. El "
                   "archivo en sí NO vive aquí — cada aparato guarda el suyo por su "
                   "cuenta (IndexedDB en la web, el plugin nativo en la app), este campo "
                   "solo le dice al servidor 'esta tarea se resuelve con un vídeo local' "
                   "para que workout_kind la trate como 'video' igual que si tuviera uno "
                   "de YouTube. Solo para category='sport'/'work' — Estudio no lo usa.",
    )

    # Objetivos que permiten que la tarea se marque sola al importar de
    # Health Connect. Sin ninguno puesto, cualquier actividad importada
    # la da por hecha; con ellos, solo cuenta si de verdad se cumplió.
    target_steps = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Solo andar: pasos que hay que dar para darla por hecha (ej. 10000).",
    )
    target_distance_km = models.FloatField(
        null=True, blank=True,
        help_text="Solo running/andar: km que hay que recorrer para darla por hecha.",
    )
    max_pace_seconds_per_km = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Solo running: ritmo máximo permitido en segundos por km (ej. 360 = "
                   "6:00/km). Correr más lento que esto no cuenta como hecha. Se guarda "
                   "en segundos y no en minutos decimales porque 5,5 min/km se lee mal "
                   "(¿5:30 o 5:50?), mientras que 330 s/km es exacto.",
    )

    # Presets de ritmo en lenguaje llano — para quien no corre, "6:30/km"
    # no dice nada. El número entre paréntesis es solo para quien SÍ lo
    # sabe leer; la etiqueta lleva el peso para todos los demás.
    PACE_PRESETS = [
        (900, "Paseo tranquilo (15:00/km)"),
        (720, "Paseo normal (12:00/km)"),
        (600, "Andar a paso ligero (10:00/km)"),
        (480, "Trote suave (8:00/km)"),
        (390, "Correr (6:30/km)"),
        (330, "Correr a buen ritmo (5:30/km)"),
        (270, "Correr rápido (4:30/km)"),
        (210, "Correr muy rápido (3:30/km)"),
    ]
    PACE_PRESET_SECONDS = {seconds for seconds, _ in PACE_PRESETS}
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
    def current_streak(self):
        """
        Racha actual de esta serie — el mismo cálculo que ya se usa en
        Rachas, pero puesto aquí para que la tarjeta de la tarea lo
        pueda enseñar sin que haya que ir a buscarlo a otra pantalla.
        Solo tiene sentido para tareas que se repiten: una suelta no
        tiene "racha".
        """
        if self.repeat == self.REPEAT_NONE:
            return 0
        return Occurrence.streak_stats(self.series_id)["current_streak"]

    @property
    def plan(self):
        """El plan que generó esta tarea, si viene de uno."""
        return Plan.objects.filter(
            task_series_id=self.series_id, deleted_at__isnull=True
        ).first()

    @property
    def workout_kind(self):
        """
        Qué clase de sesión abre esta tarea, para que el botón de la lista
        no prometa algo que no va a pasar.

        En Deporte manda `sport_mode`, elegido al crear la tarea: cámara,
        circuito o vídeo. Antes esto se deducía del subtipo (y un vídeo
        puesto anulaba todo lo demás), lo que dejaba sin usar la cámara y
        los circuitos en cuanto había un vídeo — ahora es una elección
        explícita y no se pisan entre sí.
        """
        if self.category == self.CATEGORY_SPORT:
            if self.subcategory == self.SUBCATEGORY_RUNNING:
                return "distance"   # se importa de Health Connect, o a mano
            if self.sport_mode == self.SPORT_MODE_VIDEO:
                return "video"
            if self.sport_mode == self.SPORT_MODE_CIRCUIT:
                return "timer"
            if self.sport_mode == self.SPORT_MODE_CAMERA:
                return "camera"
            # Sin modo elegido (tareas de antes de este campo): se
            # mantiene el comportamiento que tenían, para no romperlas.
            if self.subcategory == self.SUBCATEGORY_LOWER_BODY:
                return "timer"
            return "camera"

        # Fuera de Deporte, un vídeo puesto define la tarea entera.
        if self.youtube_video_id or self.youtube_playlist_id or self.has_local_video:
            return "video"
        if self.category == self.CATEGORY_WORK:
            return "focus"          # temporizador de Enfoque: leer, estudiar, estirar…
        return None

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
        raw = (self.youtube_video_id or "").strip()
        if raw:
            m = _YOUTUBE_ID_RE.search(raw)
            self.youtube_video_id = m.group(1) if m else raw
        raw_pl = (self.youtube_playlist_id or "").strip()
        if raw_pl:
            m = _YOUTUBE_PLAYLIST_ID_RE.search(raw_pl)
            self.youtube_playlist_id = m.group(1) if m else raw_pl
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
            # Estos se añadieron después de escribir esta función, y se
            # quedaban fuera — una tarea repetida con vídeo fijo, o de
            # running con objetivo, perdía todo eso en su siguiente
            # instancia. Los planes se recomponen solos en cada carga
            # (ver Plan.sync_all_tasks), pero una tarea suelta con estos
            # campos puestos a mano solo tiene este sitio para no perderlos.
            sport_mode=self.sport_mode,
            youtube_video_id=self.youtube_video_id,
            youtube_playlist_id=self.youtube_playlist_id,
            has_local_video=self.has_local_video,
            target_minutes=self.target_minutes,
            target_video_count=self.target_video_count,
            target_steps=self.target_steps,
            target_distance_km=self.target_distance_km,
            max_pace_seconds_per_km=self.max_pace_seconds_per_km,
        )

    def _record_occurrence(self, result, auto_expired=False, minutes_watched=None):
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

        minutes_watched es opcional y solo lo mandan las tareas de vídeo
        (ver task_video.html) — se guarda tal cual para que salga en el
        historial/estadísticas, no cambia si el día cuenta como hecho o no
        (eso ya lo decidió quien llamó a mark_done()).
        """
        if self.due_date is None:
            return Occurrence.objects.create(
                task=self, series_id=self.series_id, title=self.title,
                result=result, due_date=None, auto_expired=auto_expired,
                user=self.user, minutes_watched=minutes_watched,
            )
        obj, _ = Occurrence.objects.update_or_create(
            series_id=self.series_id, due_date=self.due_date,
            defaults=dict(
                task=self, title=self.title, result=result,
                auto_expired=auto_expired, user=self.user,
                minutes_watched=minutes_watched,
            ),
        )
        return obj

    def mark_done(self, minutes_watched=None):
        self.is_done = True
        self.expired = False
        self.completed_at = timezone.now()
        self.reopened_at = None
        self.save()
        self._record_occurrence(Occurrence.RESULT_DONE, minutes_watched=minutes_watched)
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

    def _record_plan_miss(self):
        """
        Si esta tarea es la sesión de un plan y expira sin haber jugado
        nada, el día queda invisible para el plan: sin ninguna
        WorkoutSession ese día, successes_and_streak() ni se entera de
        que faltó — no cuenta como fallo, no mueve la racha, no dispara
        el deload (bajar el objetivo tras varios fallos seguidos). Aquí
        se deja constancia expresa: una sesión a 0% por cada ejercicio
        del plan, con el objetivo que tocaba ese día. Si ya hay alguna
        sesión de esta tarea (jugaste algo aunque no llegaras a marcarla
        hecha a tiempo), no se toca nada — esto es solo para el silencio
        total.
        """
        plan = self.plan
        if not plan or WorkoutSession.objects.filter(task=self).exists():
            return
        for item in plan.items.select_related("exercise").filter(exercise__isnull=False):
            t = item.current_target()
            WorkoutSession.objects.create(
                task=self, user=self.user, plan=plan, series_id=self.series_id,
                exercise=item.exercise.slug,
                total_reps=0, total_sets=0, session_duration_seconds=0,
                target_sets=t.get("sets"), target_reps=t.get("reps"),
                target_seconds=t.get("seconds"),
            )

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
        self._record_plan_miss()
        self._spawn_next()

    @classmethod
    def for_today(cls, qs=None):
        """
        Las tareas pendientes que TOCAN HOY.

        Al resolver una tarea repetida se genera ya la del día siguiente,
        y sin este filtro aparecía en la lista al instante: podías
        marcarla otra vez el mismo día y contaba doble en las
        estadísticas. Una tarea con fecha futura no es de hoy.

        Las vencidas (fecha pasada y sin resolver) sí se muestran, que
        para eso están pendientes. Y las que no tienen fecha también,
        porque son de "cuando pueda".
        """
        today = timezone.localtime(timezone.now()).date()
        base = qs if qs is not None else cls.objects.all()
        return base.filter(
            models.Q(due_date__isnull=True) | models.Q(due_date__lte=today)
        )

    @classmethod
    def completed_today(cls, qs=None):
        """
        Lo cerrado hoy.

        La lista de hechas es "lo que he hecho hoy", no un registro
        permanente: con una tarea diaria se iba acumulando una entrada
        por día hasta llenarla de ruido. El historial completo está en
        las estadísticas.
        """
        today = timezone.localtime(timezone.now()).date()
        base = qs if qs is not None else cls.objects.all()
        return base.filter(is_done=True).filter(
            models.Q(completed_at__date=today) | models.Q(completed_at__isnull=True)
        )

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
        choices=Task.SPORT_SUBCATEGORY_CHOICES,
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
        max_length=16, choices=Task.SPORT_SUBCATEGORY_CHOICES, blank=True,
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

    # Qué clase de plan es, y por tanto cómo se resuelve su tarea diaria.
    # Deporte: como siempre, objetivos de ejercicio (con cámara/circuito,
    # y ahora también running — ver PlanItem). Estudio: sin "objetivo"
    # aparte que añadir — el propio vídeo/playlist/temporizador de la
    # tarea diaria ES el objetivo, y el progreso se mide en si la
    # completaste cada día. General: igual que Estudio pero sin vídeo,
    # solo cumplimiento simple (un hábito cualquiera).
    PLAN_TYPE_SPORT = "sport"
    PLAN_TYPE_STUDY = "study"
    PLAN_TYPE_GENERAL = "general"
    PLAN_TYPE_CHOICES = [
        (PLAN_TYPE_SPORT, "Deporte"),
        (PLAN_TYPE_STUDY, "Estudio"),
        (PLAN_TYPE_GENERAL, "General"),
    ]
    plan_type = models.CharField(max_length=10, choices=PLAN_TYPE_CHOICES, default=PLAN_TYPE_SPORT)

    # Subtipo de "Estudio": 'general' es el hábito diario de siempre (un
    # vídeo/playlist fijo o un temporizador, sin más). 'language' es un
    # curso de verdad: una secuencia de vídeos reales de YouTube,
    # ordenados de nivel MCER más bajo a más alto y repartidos en las
    # semanas del plan — ver CourseModule más abajo. Solo tiene sentido
    # cuando plan_type='study'; en Deporte/General se queda en blanco.
    STUDY_SUBTYPE_GENERAL = "general"
    STUDY_SUBTYPE_LANGUAGE = "language"
    STUDY_SUBTYPE_CHOICES = [
        (STUDY_SUBTYPE_GENERAL, "Hábito simple"),
        (STUDY_SUBTYPE_LANGUAGE, "Idioma (curso con vídeos por nivel)"),
    ]
    study_subtype = models.CharField(
        max_length=10, choices=STUDY_SUBTYPE_CHOICES, blank=True, default=STUDY_SUBTYPE_GENERAL,
    )

    # Niveles del Marco Común Europeo de Referencia — mismo orden que se
    # usa para clasificar y ordenar los CourseModule de un curso de
    # idioma. Constante a nivel de módulo (ver arriba del archivo) porque
    # Task.level también la necesita y Task se define antes que Plan;
    # se deja también como atributo de clase aquí para no romper el
    # código existente que escribe Plan.CEFR_LEVELS / Plan.CEFR_LEVEL_CHOICES.
    CEFR_LEVELS = CEFR_LEVELS
    CEFR_LEVEL_CHOICES = CEFR_LEVEL_CHOICES

    # Solo con study_subtype='language'. En blanco, level_from se trata
    # como A1 (empezar desde cero) y level_to como "sin techo" (llega
    # hasta donde dé el número de semanas).
    language_name = models.CharField(
        max_length=40, blank=True,
        help_text="Solo con study_subtype='language': el idioma del curso, ej. 'francés'.",
    )
    level_from = models.CharField(max_length=2, blank=True, choices=CEFR_LEVEL_CHOICES)
    level_to = models.CharField(max_length=2, blank=True, choices=CEFR_LEVEL_CHOICES)

    # Qué idiomas ya domina el usuario, en sus propias palabras (ej.
    # "inglés, italiano"). El PRIMERO que escribe es el que se usa como
    # "idioma nativo" para filtrar el catálogo (ver
    # api._catalog_entries_for_language): solo entran cursos explicados
    # en ese idioma, o cursos neutros sin idioma de explicación fijado
    # (CoursePlaylist.native_language en blanco) — nunca uno pensado
    # para hablantes de otro idioma distinto. También da contexto a las
    # notas del plan (comparar gramática con un idioma que ya conoces).
    # Ya es obligatorio en el formulario — nunca queda en blanco.
    known_languages = models.CharField(max_length=200, blank=True)

    # Cuántos minutos de vídeo al día quiere ver el usuario — objetivo
    # DIARIO del plan, no la duración de un vídeo concreto (eso vive en
    # CourseModule.duration_seconds). Se copia tal cual a Task.target_minutes
    # en _language_target_fields(). En blanco, la tarea diaria exige ver
    # el vídeo entero (comportamiento de siempre, sin objetivo en minutos).
    language_daily_minutes = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Solo con study_subtype='language': minutos de vídeo al día. En blanco, "
                   "exige ver el vídeo del día entero.",
    )

    # Cada cuántos vídeos vistos se genera un test de repaso — lo decide
    # el usuario al crear el plan (gastar IA en un test por vídeo no es
    # lo mismo que uno cada 5). En blanco, no se generan tests
    # automáticos. El disparo vive en api.maybe_trigger_quiz(), llamado
    # desde views.task_video_save justo después de marcar el vídeo como
    # visto — ver CourseQuiz más abajo para el resultado y la racha.
    quiz_every_n_videos = models.PositiveIntegerField(null=True, blank=True)

    # Cuándo toca entrenar. El plan crea y mantiene su propia tarea con
    # estos datos, para que el usuario no tenga que crear una a mano ni
    # entender qué es un "circuito": crea el plan y le sale la tarea.
    repeat = models.CharField(max_length=10, default="custom")
    interval = models.PositiveIntegerField(default=1)
    custom_days = models.CharField(
        max_length=20, blank=True, default="0,2,4",
        help_text="Días de la semana, como en las tareas. Por defecto lunes, miércoles y viernes.",
    )
    due_time = models.TimeField(null=True, blank=True)

    # La tarea que representa este plan en la lista del día.
    task_series_id = models.UUIDField(null=True, blank=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    # Cierre del ciclo: distinto de borrar. Un plan cerrado deja de
    # generar tareas y sale de la lista de activos, pero se queda para
    # poder mirar atrás — borrar (deleted_at) es para "esto no debería
    # haber existido"; cerrar (closed_at) es para "esto terminó bien".
    closed_at = models.DateTimeField(null=True, blank=True)
    reward = models.CharField(
        max_length=200, blank=True,
        help_text="La recompensa que te prometes al empezar el ciclo (opcional). "
                   "Se enseña en la pantalla de cierre si la has puesto — y solo si "
                   "el plan llega al umbral de completado.",
    )
    # Foto del progreso en el momento de cerrar (manual o automático). No
    # se recalcula después: una vez cerrado, el plan ya no acumula más
    # sesiones, así que sería el mismo número — pero guardarlo evita
    # tener que volver a calcularlo cada vez que se enseña la lista de
    # cerrados, y dEja constancia de con qué dato se decidió.
    final_progress_pct = models.PositiveIntegerField(null=True, blank=True)

    # A partir de qué porcentaje un cierre cuenta como "completado" en
    # vez de "terminado incompleto". Un ciclo que no lo alcanza se
    # cierra igual (o se auto-cierra al pasar las semanas), pero no
    # desbloquea la recompensa ni se celebra igual.
    COMPLETION_THRESHOLD_PCT = 70

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

    @property
    def is_completed(self):
        """
        Si el cierre cuenta como éxito o como "terminado incompleto".

        Usa la foto guardada al cerrar si ya está cerrado; si todavía
        está abierto, calcula con el progreso de ahora mismo — así la
        pantalla de cierre puede avisar de antemano de en qué lado vas
        a caer antes de que confirmes.
        """
        pct = self.final_progress_pct if self.closed_at else self.progress_pct()
        return pct is not None and pct >= self.COMPLETION_THRESHOLD_PCT

    @classmethod
    def auto_close_expired(cls, user=None):
        """
        Cierra solos los planes que ya han llegado a su fin.

        Sin scheduler en este hosting, así que se comprueba de gorra
        cada vez que se abre la lista de tareas — mismo criterio que
        Task.expire_overdue(): barato, y no hace falta que nadie entre
        a "planes" para que un ciclo vencido deje de generar tareas.

        Deporte/General: "su fin" es que se cumplan las semanas
        (`ends_on`), como siempre. Estudio · Idiomas es distinto a
        propósito: el objetivo es terminar el temario asignado, no una
        fecha — `weeks` ahí es solo una ESTIMACIÓN del ritmo elegido
        (ver api.build_language_plan_draft), no un plazo. Si el ritmo
        real va más lento de lo estimado, el plan sigue abierto en vez
        de cerrarse a medias; si el temario se acaba antes de lo
        estimado (playlist corta), se cierra en cuanto se ve el último
        vídeo en vez de seguir repitiéndolo hasta que pasen las
        semanas que sobran.

        Estudio · Hábito simple con una playlist SEGUIDA (con caché de
        vídeos, ver PlanItem.playlist_videos_cache /
        Plan._study_playlist_progress): mismo criterio que Idiomas —
        se cierra al terminar la playlist entera, no al cumplir
        `weeks`. Sin playlist, o con un vídeo suelto/temporizador
        (sin seguimiento posible), sigue siendo un hábito que se repite
        y se cierra por semanas, como toda la vida.
        """
        today = timezone.localtime(timezone.now()).date()
        qs = cls.objects.filter(deleted_at__isnull=True, closed_at__isnull=True, is_active=True)
        if user is not None:
            qs = qs.filter(user=user)
        for plan in qs:
            is_language = (
                plan.plan_type == cls.PLAN_TYPE_STUDY and plan.study_subtype == cls.STUDY_SUBTYPE_LANGUAGE
            )
            head = plan.headline if plan.plan_type == cls.PLAN_TYPE_STUDY else None
            has_tracked_playlist = bool(
                head and not is_language and head.youtube_playlist_id and head.playlist_videos_cache
            )
            if is_language:
                progress = plan.course_progress()
                finished = progress["total"] > 0 and progress["pct"] >= 100
            elif has_tracked_playlist:
                progress = plan._study_playlist_progress(head)
                finished = progress["total"] > 0 and progress["finished"]
            else:
                finished = today >= plan.ends_on
            if finished:
                plan.final_progress_pct = plan.progress_pct()
                plan.closed_at = timezone.now()
                plan.is_active = False
                plan.save(update_fields=["final_progress_pct", "closed_at", "is_active", "updated_at"])
                plan.sync_task()

    def custom_days_list(self):
        if not self.custom_days:
            return []
        return [d.strip() for d in self.custom_days.split(",") if d.strip()]

    def _running_target_fields(self):
        """
        Si el objetivo principal de este plan es running, los campos que
        hay que copiar a la tarea diaria (distancia/ritmo del escalón
        actual) — o un dict vacío si no aplica. Se recalcula siempre
        desde cero en vez de guardarse aparte: el escalón sube solo con
        las sesiones cumplidas, así que "el objetivo de hoy" cambia sin
        que nadie tenga que tocar nada.
        """
        head = self.headline
        if not head or not head.exercise or head.exercise.mode != Exercise.MODE_DISTANCE:
            return {}
        t = head.current_target()
        return {
            "subcategory": Task.SUBCATEGORY_RUNNING,
            "target_distance_km": t.get("distance_km"),
            "max_pace_seconds_per_km": t.get("pace_seconds_per_km"),
        }

    def _sport_mode_fields(self):
        """
        Si el objetivo principal tiene un modo elegido (cámara, circuito,
        vídeo), lo copia a la tarea diaria — es lo que hace que
        workout_kind() sepa a qué pantalla mandar al pulsar play, en vez
        de asumir siempre circuito como pasaba antes de que esto
        existiera. Sin modo elegido (objetivos de antes de este campo),
        no se toca nada — se quedan tal como estaban, yendo al circuito.
        """
        head = self.headline
        if not head or not head.sport_mode:
            return {}
        fields = {"sport_mode": head.sport_mode}
        if head.sport_mode == PlanItem.SPORT_MODE_VIDEO:
            fields.update(
                youtube_video_id=head.youtube_video_id,
                youtube_playlist_id=head.youtube_playlist_id,
                target_minutes=head.target_minutes,
                target_video_count=head.target_video_count,
            )
        return fields

    def _study_playlist_progress(self, head):
        """
        Por dónde vas en la playlist de un objetivo de Estudio · Hábito
        simple con caché (head.playlist_videos_cache) — usado tanto por
        `_study_target_fields` (qué vídeo toca hoy) como por
        `auto_close_expired` (si ya se acabó la lista entera).

        Se mide siempre en VÍDEOS COMPLETOS consumidos, tanto si el
        objetivo es "N vídeos al día" como si es "N minutos al día":
          - con target_video_count: cada día cumplido consume esa
            cantidad de vídeos (mismo criterio que
            `_language_completed_count`, contando Occurrence, pero
            multiplicado por cuántos vídeos tocan por sesión).
          - con target_minutes (y sin target_video_count): se suman los
            minutos REALES vistos (Occurrence.minutes_watched, no un
            cálculo teórico) desde que se sincronizó la playlist, y se
            recorre la lista de vídeos acumulando su duración hasta
            gastar esos minutos — un vídeo cuenta como "consumido" solo
            si su duración entera ya cupo en lo visto hasta ahora. No
            se reanuda a mitad de vídeo (decisión explícita): el
            siguiente día siempre empieza el próximo vídeo sin ver
            desde el principio, aunque eso signifique pasarse un poco
            de los minutos exactos algunos días.

        `since` (desde cuándo cuentan las Occurrence) es
        `playlist_synced_at` si existe — así cambiar de playlist
        reinicia el avance solo, sin guardar un índice aparte — y si no,
        `started_on` del plan (compatibilidad con cachés antiguas).
        """
        videos = head.playlist_videos_cache or []
        total = len(videos)
        if not total:
            return {"total": 0, "index": 0, "finished": False}

        since = (
            timezone.localtime(head.playlist_synced_at).date()
            if head.playlist_synced_at else self.started_on
        )
        done_occurrences = Occurrence.objects.filter(
            series_id=self.task_series_id, result=Occurrence.RESULT_DONE,
            deleted_at__isnull=True, recorded_at__date__gte=since,
        ) if self.task_series_id else Occurrence.objects.none()

        if head.target_video_count:
            consumed = done_occurrences.count() * head.target_video_count
        else:
            watched_seconds = sum((o.minutes_watched or 0) for o in done_occurrences) * 60
            consumed = 0
            cumulative = 0
            for v in videos:
                cumulative += (v.get("duration_seconds") or 0)
                if cumulative > watched_seconds:
                    break
                consumed += 1

        finished = consumed >= total
        return {"total": total, "index": min(consumed, total - 1), "finished": finished}

    def _study_target_fields(self):
        """
        Si el plan es de Estudio, los campos de vídeo/playlist/temporizador
        que hay que copiar a la tarea diaria — viven en el objetivo
        (PlanItem), no en el plan, igual que el peso o las repeticiones
        viven en el objetivo de un plan de Deporte. Sin objetivo puesto
        todavía, la tarea diaria sale como Estudio simple, sin vídeo —
        no como un error, solo como "todavía no configurado".

        Con una playlist ya sincronizada (head.playlist_videos_cache,
        ver PlanItem.sync_playlist_videos), la tarea sigue embebiendo la
        PLAYLIST ENTERA (no un vídeo suelto) pero indicándole al
        reproductor por dónde empezar hoy (`playlist_start_index`, ver
        task_video.html) — así un objetivo de "2 vídeos al día" sigue
        pudiendo ver varios seguidos en la misma sesión, solo que ya no
        vuelve a repetir desde el vídeo 1 cada vez. Sin caché todavía
        (playlist recién puesta y sin guardar aún, o la sincronización
        con YouTube falló), cae al comportamiento de siempre: la
        playlist entera, siempre desde el principio.
        """
        head = self.headline
        if not head:
            return {}
        fields = {
            "youtube_video_id": head.youtube_video_id,
            "youtube_playlist_id": head.youtube_playlist_id,
            "target_minutes": head.target_minutes,
            "target_video_count": head.target_video_count,
            "playlist_start_index": None,
        }
        if head.youtube_playlist_id and head.playlist_videos_cache:
            progress = self._study_playlist_progress(head)
            if progress["total"]:
                fields["playlist_start_index"] = progress["index"]
        return fields

    def _language_completed_count(self):
        """
        Cuántas sesiones de este curso se han CUMPLIDO desde que empezó
        el plan — mismo conteo que PlanItem.successes_and_streak() usa
        para Deporte, aplicado aquí a la serie de tarea del plan. Es lo
        que decide qué CourseModule toca hoy: avanza con lo que de
        verdad has visto, no con los días que han pasado en el
        calendario — si te saltas un día no te "come" un vídeo sin
        verlo, y no hace falta que coincida con la semana en la que la
        IA lo programó al crear el curso (esa semana es solo orientativa,
        ver CourseModule.scheduled_week).
        """
        if not self.task_series_id:
            return 0
        return Occurrence.objects.filter(
            series_id=self.task_series_id, result=Occurrence.RESULT_DONE,
            deleted_at__isnull=True, recorded_at__date__gte=self.started_on,
        ).count()

    def _language_target_fields(self):
        """
        Si el plan es de Estudio · Idiomas, qué vídeo de CourseModule
        toca HOY — el siguiente sin ver según `_language_completed_count`.
        Al llegar al final del temario se queda enseñando el último
        vídeo en vez de dejar la tarea sin vídeo (más newsletter que un
        error: el curso se acabó, no hay más que "fallar" mostrando
        nada). Sin ningún CourseModule todavía (curso recién creado y
        algo falló al expandirlo, o borrado a mano), sale como Estudio
        simple sin vídeo — igual que _study_target_fields en ese caso.
        """
        # El idioma del plan se enseña siempre, aunque el temario esté
        # vacío todavía (curso recién creado a mano, sin cursos elegidos
        # aún) — es contexto barato y útil por sí solo. El nivel, en
        # cambio, es el del vídeo concreto que toca: sin CourseModule no
        # hay ninguno que enseñar.
        fields = {"language_name": self.language_name}
        modules = list(self.course_modules.all())
        if not modules:
            return fields
        index = min(self._language_completed_count(), len(modules) - 1)
        module = modules[index]
        fields.update({
            "youtube_video_id": module.youtube_video_id,
            "youtube_playlist_id": "",
            # Objetivo DIARIO del usuario (ej. "1h al día"), no la
            # duración del vídeo — task_video.html decide con esto si
            # corta al llegar al objetivo o deja terminar el vídeo (ver
            # el margen de sobra en el propio JS). En blanco, exige ver
            # el vídeo entero, como antes de que existiera este campo.
            "target_minutes": self.language_daily_minutes,
            "target_video_count": None,
            "level": module.level,
        })
        return fields

    def course_progress(self):
        """
        Para la pantalla del plan: vídeos vistos / totales y cuál toca
        ahora, calculado exactamente igual que decide la tarea diaria
        (`_language_target_fields`) — para que nunca se desincronicen.
        """
        modules = list(self.course_modules.all())
        total = len(modules)
        if not total:
            return {"total": 0, "watched": 0, "pct": 0, "next": None}
        watched = min(self._language_completed_count(), total)
        return {
            "total": total,
            "watched": watched,
            "pct": round(100 * watched / total),
            "next": modules[min(watched, total - 1)],
        }

    def mark_current_module_watched(self):
        """
        Apunta `CourseModule.watched_at` en el vídeo que se acaba de dar
        por visto — solo para poder revisarlo (auditoría, depurar un
        test raro). El avance real del curso sigue siendo
        `_language_completed_count()` sobre Occurrence, no esto: se
        llama DESPUÉS de guardar la Occurrence del día, así que el
        índice ya incluye el vídeo recién visto.
        """
        modules = list(self.course_modules.all())
        completed = self._language_completed_count()
        if not modules or completed <= 0:
            return None
        module = modules[min(completed, len(modules)) - 1]
        if not module.watched_at:
            module.watched_at = timezone.now()
            module.save(update_fields=["watched_at"])
        return module

    def quiz_streak_stats(self):
        """
        Racha de tests de idioma aprobados (ver CourseQuiz) — aparte de
        `course_progress`, que es solo vídeos vistos. Un test flojo no
        toca el progreso del curso (el vídeo ya contó como visto al
        verlo), pero SÍ rompe esta racha: es el "empujón" para que se
        preste atención de verdad, sin poder atascar el curso en sí.
        """
        return CourseQuiz.streak_stats(self.pk)

    def sync_task(self):
        """
        Crea o actualiza la tarea que representa este plan en la lista
        del día.

        Es lo que evita que el usuario tenga que aprender tres conceptos
        (tarea, circuito y plan): crea el plan y le aparece la tarea, le
        da al play y entrena. El plan ya decidió qué ejercicios y con qué
        objetivo, que es para lo que existe.

        Qué categoría lleva la tarea, y qué campos extra se copian,
        depende de plan_type — ver el comentario junto al campo.

        Si el plan se pausa o se borra, su tarea pendiente desaparece —
        pero el historial de lo ya hecho se conserva.
        """
        pending = Task.objects.filter(
            series_id=self.task_series_id, is_done=False, expired=False,
        ) if self.task_series_id else Task.objects.none()

        if not self.is_active or self.deleted_at:
            pending.delete()
            return None

        category = {
            self.PLAN_TYPE_SPORT: Task.CATEGORY_SPORT,
            self.PLAN_TYPE_STUDY: Task.CATEGORY_STUDY,
            self.PLAN_TYPE_GENERAL: Task.CATEGORY_GENERAL,
        }[self.plan_type]

        fields = dict(
            title=self.name,
            category=category,
            # Solo Estudio · Idiomas lleva subcategoría propia — el resto
            # se queda en blanco, igual que antes de que esto existiera.
            subcategory=(
                Task.SUBCATEGORY_LANGUAGE
                if self.plan_type == self.PLAN_TYPE_STUDY and self.study_subtype == self.STUDY_SUBTYPE_LANGUAGE
                else ""
            ),
            repeat=self.repeat,
            interval=self.interval,
            custom_days=self.custom_days,
            # Sin hora límite, expire_overdue() nunca la toca — se
            # quedaría pendiente indefinidamente si un día no la juegas
            # y podrías completarla días después como si tal cosa, sin
            # que cuente como fallo para el plan. Con las 23:59 de por
            # defecto, si no la juegas ese día se resuelve sola por la
            # noche (ver mark_expired). Si el plan sí tiene una hora
            # propia puesta, esa manda.
            due_time=self.due_time or _dt.time(23, 59),
            user=self.user,
            # Puestos aquí, en la base, para que cambiar de objetivo (de
            # uno con vídeo a uno sin modo elegido, o de running a
            # fuerza) LIMPIE lo que ya no aplica en vez de dejarlo
            # pegado de una sincronización anterior — _study_target_fields
            # y _sport_mode_fields solo escriben lo que SÍ aplica, así
            # que sin este reseteo de base lo viejo se quedaría ahí.
            sport_mode="",
            youtube_video_id="",
            youtube_playlist_id="",
            target_minutes=None,
            target_video_count=None,
            playlist_start_index=None,
            target_distance_km=None,
            max_pace_seconds_per_km=None,
            language_name="",
            level="",
        )

        if self.plan_type == self.PLAN_TYPE_STUDY:
            if self.study_subtype == self.STUDY_SUBTYPE_LANGUAGE:
                fields.update(self._language_target_fields())
            else:
                fields.update(self._study_target_fields())
        elif self.plan_type == self.PLAN_TYPE_SPORT:
            fields.update(self._running_target_fields())
            fields.update(self._sport_mode_fields())

        task = pending.first()
        if task:
            for k, v in fields.items():
                setattr(task, k, v)
            task.save()
        else:
            task = Task.objects.create(
                due_date=max(self.started_on, timezone.localtime(timezone.now()).date()),
                **fields,
            )
            self.task_series_id = task.series_id
            Plan.objects.filter(pk=self.pk).update(task_series_id=task.series_id)

        # General no tiene un paso aparte de "añadir objetivo": la propia
        # tarea diaria (completarla o no cada día) ES el objetivo, y no
        # hay nada más que configurar — así que se crea aquí, una vez,
        # un PlanItem de cumplimiento apuntando a esta misma serie.
        # Estudio SÍ necesita ese paso (el objetivo lleva el
        # vídeo/playlist/temporizador, hay que rellenarlo), así que ahí
        # no se crea nada solo — se añade desde el formulario de
        # objetivo, igual que en Deporte.
        if self.plan_type == self.PLAN_TYPE_GENERAL:
            PlanItem.objects.get_or_create(
                plan=self, series_id=self.task_series_id, exercise=None,
                defaults=dict(progression=PlanItem.PROG_COMPLETION, is_headline=True),
            )

        return task

    @classmethod
    def sync_all_tasks(cls, user=None):
        """
        Refresca la tarea de todos los planes activos.

        Hace falta más allá de crear/editar el plan: un plan de running
        sube de escalón con las sesiones cumplidas, y sin esto la tarea
        del día siguiente se generaría con el objetivo de ayer en vez
        del que toca hoy. Barato de llamar en cada carga de la lista,
        igual que Task.expire_overdue().
        """
        qs = cls.objects.filter(deleted_at__isnull=True, is_active=True)
        if user is not None:
            qs = qs.filter(user=user)
        for plan in qs:
            plan.sync_task()

    @property
    def task(self):
        """La tarea pendiente de este plan, si la hay."""
        if not self.task_series_id:
            return None
        return Task.objects.filter(
            series_id=self.task_series_id, is_done=False, expired=False,
        ).first()

    def session_items(self):
        """
        Los ejercicios de la sesión de hoy, en el formato que espera el
        reproductor. Sale del plan directamente: no hace falta circuito.
        """
        items = []
        for it in self.items.select_related("exercise"):
            if not it.exercise:
                continue          # los objetivos de tarea no se "entrenan"
            if it.exercise.mode == Exercise.MODE_DISTANCE:
                continue          # running no se "juega" en el circuito — se importa
            t = it.current_target()
            items.append({
                "slug": it.exercise.slug,
                "name": it.display_name,
                "mode": it.exercise.mode,
                "counter_key": it.exercise.counter_key,
                "target_sets": t["sets"],
                "target_reps": t["reps"],
                "target_weight_kg": t["weight_kg"],
                "work": t["seconds"] or 40,
                "rest": 30,
                "target_source": "plan",
                "plan_name": self.name,
                "is_headline": it.is_headline,
            })
        return items

    @property
    def headline(self):
        """
        La medida que define el plan.

        El objetivo de verdad ("estar en forma") es difuso y no se puede
        medir. Lo que sí se mide es una prueba concreta de que vas hacia
        él: llegar a 4x12 con 20 kg. Esa es la medida principal; el resto
        de ejercicios son el camino.

        Si no se ha marcado ninguna, se toma la primera por orden, para
        que la pantalla siempre tenga algo que destacar.
        """
        return self.items.filter(is_headline=True).first() or self.items.first()

    @property
    def support_items(self):
        """Los ejercicios que te llevan al objetivo, sin ser la medida."""
        head = self.headline
        qs = self.items.all()
        return qs.exclude(pk=head.pk) if head else qs

    def progress_pct(self):
        """
        Cuánto llevas del plan, medido sobre la medida principal.

        Se calcula sobre escalones conseguidos frente a escalones totales
        hasta el destino, no sobre semanas transcurridas: el plan avanza
        con lo que haces, no con lo que pasa el calendario.

        Salvo en cumplimiento (Estudio/General): ahí no hay techo
        numérico al que subir — es un hábito, no una meta con destino —
        así que el progreso se mide en cuántas veces de las que tocaba
        la cumpliste desde que empezó el plan.

        Estudio · Idiomas no tiene PlanItem (su medida es CourseModule,
        no un ejercicio con escalones) — se delega en `course_progress`,
        que ya calcula vídeos vistos/totales con el mismo criterio
        (Occurrence cumplida, no semanas pasadas). Antes de esto
        `progress_pct` devolvía None para estos planes al no tener
        `headline`, así que `is_completed`/`auto_close_expired` nunca
        los daba por completados aunque se hubiera visto el curso
        entero — quedaba corregido aparte, no es un cambio de conducta
        nuevo para el usuario, es arreglar algo que estaba roto de base.
        """
        if self.plan_type == self.PLAN_TYPE_STUDY and self.study_subtype == self.STUDY_SUBTYPE_LANGUAGE:
            return self.course_progress()["pct"]
        head = self.headline
        if not head:
            return None
        if head.progression == PlanItem.PROG_COMPLETION:
            total = head._occurrences().count()
            if not total:
                return 0
            successes = sum(1 for o in head._occurrences() if o.result == Occurrence.RESULT_DONE)
            return min(100, round(100 * successes / total))
        done = head.current_step()
        remaining = head.sessions_to_goal()
        if remaining is None:
            return None
        total_steps = done + (remaining // max(1, head.sessions_per_step))
        if total_steps <= 0:
            return 100
        return min(100, round(100 * done / total_steps))

    def weekly_completion(self):
        """
        Ejecución de ESTA semana para el plan: de las sesiones que le
        tocaban de lunes a domingo, cuántas se han resuelto y cuántas
        de esas se cumplieron.

        No es un cálculo aparte: se apoya en las mismas Occurrence que
        genera la tarea del plan (ver sync_task / task_series_id), así
        que un plan sin tarea todavía (nunca activado) no tiene nada
        que enseñar aquí.
        """
        if not self.task_series_id:
            return None
        return Occurrence.weekly_completion(self.user, series_id=self.task_series_id)


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
    PROG_DISTANCE = "distance"

    PROGRESSION_CHOICES = [
        (PROG_COMPLETION, "Cumplimiento (objetivo fijo)"),
        (PROG_REPS, "Repeticiones (sube hasta un techo)"),
        (PROG_DOUBLE, "Doble (repeticiones y luego peso)"),
        (PROG_DISTANCE, "Distancia (running: sube km y baja ritmo)"),
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

    # Solo progresión "distance" (running): partida y destino, en km y
    # en segundos por km — mismo formato que Task.max_pace_seconds_per_km,
    # para poder copiarlo tal cual a la tarea diaria sin traducir nada.
    start_distance_km = models.FloatField(default=1.0)
    start_pace_seconds_per_km = models.PositiveIntegerField(
        default=420, help_text="Ritmo de partida, en segundos por km (420 = 7:00/km).",
    )
    goal_distance_km = models.FloatField(null=True, blank=True)
    goal_pace_seconds_per_km = models.PositiveIntegerField(
        null=True, blank=True, help_text="Ritmo de destino — más bajo es más rápido.",
    )
    distance_increment_km = models.FloatField(
        default=0.5, help_text="Cuánto sube la distancia en cada escalón.",
    )
    pace_decrement_seconds = models.PositiveIntegerField(
        default=10, help_text="Cuántos segundos por km se acelera el ritmo en cada escalón.",
    )

    # Solo objetivos de Deporte: cómo se hace el ejercicio — cámara,
    # circuito, o vídeo (reutiliza los mismos campos de youtube que
    # Estudio, justo abajo). Sin esto, el ejercicio caía siempre en
    # cámara/circuito, sin poder elegir vídeo como ya podían las
    # tareas sueltas.
    SPORT_MODE_CAMERA = "camera"
    SPORT_MODE_CIRCUIT = "circuit"
    SPORT_MODE_VIDEO = "video"
    SPORT_MODE_CHOICES = [
        (SPORT_MODE_CAMERA, "Conteo con la cámara"),
        (SPORT_MODE_CIRCUIT, "Circuito"),
        (SPORT_MODE_VIDEO, "Vídeo"),
    ]
    sport_mode = models.CharField(max_length=20, choices=SPORT_MODE_CHOICES, blank=True, default="")

    # El vídeo/playlist/temporizador propiamente dicho — para un
    # objetivo de Estudio (siempre) o de Deporte con sport_mode='video'
    # (opcional). Solo YouTube, no archivo local: el vídeo local se
    # guarda por UUID de tarea, y la tarea de un plan se regenera cada
    # día con un UUID distinto — perdería el archivo a la mañana
    # siguiente, así que no tiene sentido ofrecerlo aquí.
    youtube_video_id = models.CharField(max_length=255, blank=True)
    youtube_playlist_id = models.CharField(max_length=255, blank=True)
    target_minutes = models.PositiveIntegerField(null=True, blank=True)
    target_video_count = models.PositiveIntegerField(null=True, blank=True)

    # Caché de la playlist de arriba (solo Estudio · Hábito simple, con
    # youtube_playlist_id puesto): la lista ORDENADA de vídeos que tenía
    # la playlist la última vez que se sincronizó, con su duración —
    # [{"video_id": "...", "duration_seconds": 933}, ...]. Se rellena en
    # sync_playlist_videos(), llamado SOLO al guardar el objetivo (vista
    # o API) -- NUNCA desde Plan.sync_task()/_study_target_fields(), que
    # se ejecuta en cada carga de la lista de tareas y sería demasiado
    # caro/lento si llamara a la API de YouTube ahí. Es lo que permite
    # que la tarea diaria sepa qué vídeo concreto toca hoy (ver
    # Plan._study_playlist_progress) en vez de reiniciar la playlist
    # entera cada día. Sin caché (playlist recién puesta y aún sin
    # guardar, o la API de YouTube falló al sincronizar), el plan cae al
    # comportamiento de siempre: la playlist entera, sin seguimiento.
    playlist_videos_cache = models.JSONField(default=list, blank=True)
    # Cuándo se sincronizó la caché de arriba por última vez -- también
    # marca desde cuándo cuentan las Occurrence para calcular el avance
    # (Plan._study_playlist_progress): cambiar de playlist reinicia el
    # progreso sin más estado que mantener, porque el conteo simplemente
    # empieza a contar desde esta fecha en vez de desde el inicio del plan.
    playlist_synced_at = models.DateTimeField(null=True, blank=True)

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

    is_headline = models.BooleanField(
        default=False,
        help_text="La medida que define si el plan se ha conseguido. "
                   "\"Estar en forma\" no se puede medir; \"4x12 con 20 kg\" sí — "
                   "esa es la prueba de que vas hacia el objetivo. El resto de "
                   "ejercicios son el camino, progresan pero no deciden.",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-is_headline", "order"]

    def save(self, *args, **kwargs):
        # Mismo trato que Task: si pegas la URL entera, se limpia sola a
        # la hora de guardar. Sin esto, un objetivo de Estudio guardaría
        # la URL completa en vez del id, aunque la tarea que genera el
        # plan sí saliera bien (Task.save() ya lo limpia por su lado) —
        # inconsistente y confuso si algún día se enseña este dato aquí.
        raw = (self.youtube_video_id or "").strip()
        if raw:
            m = _YOUTUBE_ID_RE.search(raw)
            self.youtube_video_id = m.group(1) if m else raw
        raw_pl = (self.youtube_playlist_id or "").strip()
        if raw_pl:
            m = _YOUTUBE_PLAYLIST_ID_RE.search(raw_pl)
            self.youtube_playlist_id = m.group(1) if m else raw_pl
        super().save(*args, **kwargs)

    def sync_playlist_videos(self):
        """
        Refresca playlist_videos_cache desde la API de YouTube — se llama
        SOLO al guardar el objetivo (vista o API), nunca desde
        Plan.sync_task()/_study_target_fields() (eso se ejecuta en cada
        carga de la lista de tareas, y una llamada a la API ahí sería
        demasiado cara/lenta). Cambiar de playlist reinicia el avance
        sin más estado que mantener: playlist_synced_at pasa a ahora, y
        Plan._study_playlist_progress() solo cuenta lo hecho desde esa
        fecha en adelante.

        Sin youtube_playlist_id, limpia la caché (por si el objetivo
        tenía una playlist antes y se ha quitado). Si la API de YouTube
        falla (sin YOUTUBE_API_KEY, cuota agotada, sin conexión...), se
        deja la caché tal cual estaba — _study_target_fields ya sabe
        caer al comportamiento de siempre (playlist entera, sin
        seguimiento) cuando no hay caché.
        """
        from .youtube_search import YouTubeSearchError, get_videos_details, list_playlist_items

        if not self.youtube_playlist_id:
            if self.playlist_videos_cache or self.playlist_synced_at:
                self.playlist_videos_cache = []
                self.playlist_synced_at = None
                self.save(update_fields=["playlist_videos_cache", "playlist_synced_at"])
            return

        try:
            items = list_playlist_items(self.youtube_playlist_id, max_results=500)
            video_ids = [it["video_id"] for it in items if it.get("video_id")]
            details = get_videos_details(video_ids) if video_ids else {}
        except YouTubeSearchError:
            return

        cache = []
        for vid in video_ids:
            d = details.get(vid) or {}
            if d.get("embeddable") is False:
                continue  # no se podría incrustar en la tarea — se salta, como en los cursos de idioma
            cache.append({"video_id": vid, "duration_seconds": d.get("duration_seconds")})

        self.playlist_videos_cache = cache
        self.playlist_synced_at = timezone.now()
        self.save(update_fields=["playlist_videos_cache", "playlist_synced_at"])

    def __str__(self):
        marca = " ★" if self.is_headline else ""
        return f"{self.plan.name}: {self.display_name}{marca}"

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

    def _sets_for_progress(self, frac):
        """
        Cuántas series tocan según lo avanzado que vas (`frac`: 0 = en
        el punto de partida, 1 = ya en el destino), interpolando en
        línea recta entre `start_sets` y `goal_sets`.

        Antes esto no existía: `target_for_step` usaba directamente
        `goal_sets or start_sets`, así que las series saltaban al
        destino desde el primer día sin importar el escalón — un plan
        de 2×5 a 4×12 enseñaba "4×5" nada más empezar. Sin meta de
        series, se quedan fijas en las de partida (no hay destino con
        el que interpolar).
        """
        if self.goal_sets is None:
            return self.start_sets
        return round(self.start_sets + frac * (self.goal_sets - self.start_sets))

    @staticmethod
    def _progress_fraction(value, start, ceiling):
        """De 0 a 1: cuánto camino hay entre `start` y `ceiling` ya
        recorrido en `value`. Sin techo definido no hay destino con el
        que medir el progreso, así que se queda en 0 (series fijas)."""
        if not ceiling:
            return 0.0
        if ceiling <= start:
            return 1.0 if value >= ceiling else 0.0
        return min(1.0, max(0.0, (value - start) / (ceiling - start)))

    def target_for_step(self, step):
        """El objetivo en el escalón `step` (0 = el primero)."""
        if self.progression == self.PROG_COMPLETION:
            return {
                "sets": self.start_sets, "reps": self.start_reps,
                "seconds": self.start_seconds if self.is_timed else None,
                "weight_kg": self.start_weight_kg, "done": False,
                "distance_km": None, "pace_seconds_per_km": None,
            }

        if self.progression == self.PROG_DISTANCE:
            distance = self.start_distance_km + step * self.distance_increment_km
            if self.goal_distance_km:
                distance = min(distance, self.goal_distance_km)
            pace = self.start_pace_seconds_per_km - step * self.pace_decrement_seconds
            if self.goal_pace_seconds_per_km:
                # Un ritmo MENOR es más rápido — "llegar" es no bajar de ahí.
                pace = max(pace, self.goal_pace_seconds_per_km)
            done = bool(
                self.goal_distance_km and distance >= self.goal_distance_km
                and self.goal_pace_seconds_per_km and pace <= self.goal_pace_seconds_per_km
            )
            return {
                "sets": None, "reps": None, "seconds": None, "weight_kg": None,
                "distance_km": round(distance, 2), "pace_seconds_per_km": pace, "done": done,
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
            # El peso es el eje que de verdad mide cuánto llevas en
            # progresión doble (las reps solo suben y bajan dentro del
            # rango una y otra vez). Sin meta de peso no hay con qué
            # medir el progreso, así que las series se quedan fijas.
            frac = self._progress_fraction(weight, self.start_weight_kg, self.goal_weight_kg)
            return {
                "sets": self._sets_for_progress(frac), "reps": reps,
                "seconds": None, "weight_kg": round(weight, 1), "done": done,
                "distance_km": None, "pace_seconds_per_km": None,
            }

        # PROG_REPS: sube hasta el techo y ahí se queda.
        if self.is_timed:
            seconds = self.start_seconds + step * self.reps_increment
            ceiling = self.goal_seconds
            if ceiling:
                seconds = min(seconds, ceiling)
            frac = self._progress_fraction(seconds, self.start_seconds, ceiling)
            return {
                "sets": self._sets_for_progress(frac), "reps": None,
                "seconds": seconds, "weight_kg": self.start_weight_kg,
                "done": bool(ceiling and seconds >= ceiling),
                "distance_km": None, "pace_seconds_per_km": None,
            }

        reps = self.start_reps + step * self.reps_increment
        ceiling = self.goal_reps
        if ceiling:
            reps = min(reps, ceiling)
        frac = self._progress_fraction(reps, self.start_reps, ceiling)
        return {
            "sets": self._sets_for_progress(frac), "reps": reps,
            "seconds": None, "weight_kg": self.start_weight_kg,
            "done": bool(ceiling and reps >= ceiling),
            "distance_km": None, "pace_seconds_per_km": None,
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

    def weekly_schedule(self, weeks, sessions_per_week):
        """
        Lo mismo que `schedule()` pero por SEMANA en vez de por escalón —
        "semana 1: tanto, semana 2: tanto más" en vez de "escalón 3".

        No toca la base de datos (como `schedule()`): sirve igual para un
        objetivo ya guardado que para uno todavía sin guardar, que es
        justo lo que hace falta para enseñar la vista previa de un plan
        generado por IA antes de confirmarlo.

        La conversión semana → escalón es la misma cuenta que ya hace la
        calculadora de "¿en cuántas semanas quieres llegar?" del
        formulario (sessions_per_step sesiones por escalón, tantas
        sesiones a la semana como días tenga el plan).
        """
        rows = []
        for week in range(1, weeks + 1):
            total_sessions = week * max(1, sessions_per_week)
            step = max(0, round(total_sessions / max(1, self.sessions_per_step)) - 1)
            row = dict(week=week, **self.target_for_step(step))
            rows.append(row)
            if row["done"]:
                break
        return rows

    def history(self, limit=20):
        """
        Lo que pasó de verdad: qué te pedía cada sesión, qué hiciste y el
        porcentaje. El objetivo sale de la propia sesión (se guardó
        entonces), no se recalcula — si se recalculara, un entreno de
        hace un mes se compararía con el objetivo de hoy.
        """
        if self.progression == self.PROG_COMPLETION and self.series_id:
            return [
                {
                    "date": o.due_date or o.recorded_at.date(),
                    "target": "cumplir",
                    "done": "sí" if o.result == Occurrence.RESULT_DONE else "no",
                    "pct": 100 if o.result == Occurrence.RESULT_DONE else 0,
                    "auto": o.auto_expired,
                }
                for o in self._occurrences().order_by("-recorded_at")[:limit]
            ]

        rows = []
        for s in self._sessions().order_by("-recorded_at")[:limit]:
            hecho = (
                f"{s.total_reps} reps" if s.total_reps
                else f"{s.session_duration_seconds}s"
            )
            rows.append({
                "date": s.recorded_at.date(),
                "target": s.target_label or "—",
                "done": hecho,
                "pct": s.achievement_pct,
                "auto": False,
            })
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
    target_distance_km = models.FloatField(null=True, blank=True)
    target_pace_seconds_per_km = models.PositiveIntegerField(null=True, blank=True)
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

    # De dónde salió el dato. Importa para dos cosas: saber si el
    # número es de fiar (un reloj mide mejor que un dedo escribiendo), y
    # poder reimportar sin duplicar.
    SOURCE_MANUAL = "manual"
    SOURCE_HEALTH_CONNECT = "health_connect"
    SOURCE_OCR = "ocr"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "A mano"),
        (SOURCE_HEALTH_CONNECT, "Health Connect"),
        (SOURCE_OCR, "Foto de la cinta"),
    ]
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    # Id que le da la fuente original a esa sesión (Health Connect da uno
    # por cada carrera). Con unique=True, reimportar el mismo periodo no
    # duplica nada — simplemente choca y se ignora.
    external_id = models.CharField(
        max_length=120, blank=True, default="",
        help_text="Id de la sesión en la app de origen, para no importarla dos veces.",
    )
    recorded_at = models.DateTimeField(auto_now_add=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-recorded_at"]

    @property
    def pace_seconds_per_km(self):
        """
        Ritmo en segundos por kilómetro, o None si no aplica.

        En segundos y no en "minutos decimales" a propósito: 5,5 min/km
        se lee mal (¿5:30 o 5:50?), mientras que 330 s/km es exacto y se
        formatea a 5:30 sin ambigüedad al enseñarlo.
        """
        if not self.distance_km or not self.session_duration_seconds:
            return None
        return self.session_duration_seconds / self.distance_km

    @property
    def pace_display(self):
        """El ritmo tal y como se dice en voz alta: 5:30/km."""
        pace = self.pace_seconds_per_km
        if pace is None:
            return ""
        minutes, seconds = divmod(int(round(pace)), 60)
        return f"{minutes}:{seconds:02d}/km"

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
        elif self.target_distance_km and self.target_pace_seconds_per_km:
            # Aquí no vale un simple "hecho/pedido": hay dos condiciones
            # a la vez (distancia Y ritmo), igual que en la importación
            # de Health Connect — andar 5 km muy despacio no completa un
            # objetivo de "5 km a 6:00/km". Si no se cumplió el ritmo, 0
            # sin más, por mucha distancia que hubiera; si se cumplió,
            # el porcentaje es cuánta distancia sacaste de la pedida (con
            # bonus si fue más).
            pace = self.pace_seconds_per_km
            if self.distance_km is None or pace is None or pace > self.target_pace_seconds_per_km:
                return 0
            return min(200, round(100 * self.distance_km / self.target_distance_km))
        else:
            return None
        if not objetivo:
            return None
        return round(100 * hecho / objetivo)

    @property
    def target_met(self):
        """
        Si esta sesión, ELLA SOLA, llegó a su objetivo.

        True tanto si no había objetivo que exigir (entreno libre, sin
        plan) como si lo hubo y se alcanzó o se superó. Solo es False
        cuando había un número que cumplir y se quedó corto — que es el
        único caso en el que una tarea de un solo ejercicio no debe
        darse por completada sola.
        """
        pct = self.achievement_pct
        return pct is None or pct >= 100

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


class TimerSession(models.Model):
    """
    Una sesión cronometrada de una tarea de Enfoque (category='work'):
    leer, estudiar, estirar… lo que sea que se apoye en un temporizador
    en vez de en la cámara o en repeticiones.

    Mismo patrón que WorkoutSession: el objetivo se guarda en la sesión
    en el momento de guardarla (target_minutes), no se recalcula después,
    para que el historial no cambie de significado si algún día editas
    el objetivo de la tarea.

    source distingue si los minutos vinieron de un cronómetro que
    controlaste a mano o del tiempo real que estuvo abierta una app
    externa (solo tiene sentido para subcategory='reading', y solo si
    hay plugin nativo instalado en la app — ver /mnt del proyecto móvil).
    """
    SOURCE_MANUAL = "manual"
    SOURCE_APP_USAGE = "app_usage"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Cronómetro manual"),
        (SOURCE_APP_USAGE, "Tiempo en la app"),
    ]

    task = models.ForeignKey(
        Task, on_delete=models.SET_NULL, null=True, blank=True, related_name="timer_sessions"
    )
    plan = models.ForeignKey(
        Plan, on_delete=models.SET_NULL, null=True, blank=True, related_name="timer_sessions",
        help_text="Para cuando esta tarea cuente para un objetivo del 12 Week Year. Sin usar todavía.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name="timer_sessions",
    )
    series_id = models.UUIDField(null=True, blank=True)

    # Copia de task.subcategory en el momento de guardar — igual que el
    # objetivo, no se recalcula después contra la tarea actual.
    subcategory = models.CharField(max_length=16, blank=True)

    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    app_package = models.CharField(
        max_length=120, blank=True,
        help_text="Paquete Android de la app leída (ej. com.adobe.reader). Solo si source=app_usage.",
    )

    minutes = models.PositiveIntegerField(default=0)
    target_minutes = models.PositiveIntegerField(null=True, blank=True)

    recorded_at = models.DateTimeField(auto_now_add=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-recorded_at"]

    @property
    def achievement_pct(self):
        """Porcentaje del objetivo cumplido, o None si la tarea no tenía uno (sesión libre)."""
        if not self.target_minutes:
            return None
        return round(100 * self.minutes / self.target_minutes)

    @property
    def target_met(self):
        """
        Igual que WorkoutSession.target_met: True si no había objetivo
        que exigir, o si lo hubo y se alcanzó. Solo False si había un
        número que cumplir y se quedó corto.
        """
        pct = self.achievement_pct
        return pct is None or pct >= 100

    @property
    def subcategory_label(self):
        return dict(Task.FOCUS_SUBCATEGORY_CHOICES).get(self.subcategory, "Enfoque")

    def __str__(self):
        return f"{self.subcategory_label} — {self.minutes} min ({self.recorded_at:%Y-%m-%d %H:%M})"


class CoursePlaylist(models.Model):
    """
    Un curso de idioma verificado A MANO: una playlist real de YouTube
    que una persona ha comprobado que de verdad es del idioma y nivel
    que dice ser.

    Por qué existe esto en vez de buscar en caliente cada vez: la
    búsqueda automática (ver `youtube_search.search_playlists`, comando
    `search_courses`) demostró en la práctica que para niveles con poco
    contenido gratis (C1, C2 sobre todo) YouTube no dice "no hay nada"
    — devuelve lo más parecido por relevancia genérica, que suele ser
    el mismo curso de principiantes repetido bajo una etiqueta de nivel
    que no le corresponde. Confiar en eso automáticamente habría colado
    lecciones de A1 como si fueran de C2.

    La solución es la misma que ya usa la app para Deporte: un catálogo
    CURADO (`Exercise` es el equivalente ahí) del que la app asigna
    directamente, sin buscar ni inventar nada por su cuenta —
    `api._catalog_entries_for_language` elige, por idioma + nivel +
    idioma nativo, sin IA de por medio (ver docstring de
    `api.build_language_plan_draft`). `search_courses` sigue siendo
    útil, pero como herramienta de DESCUBRIMIENTO para encontrar
    candidatos que un humano revisa antes de añadirlos aquí — no como
    fuente de verdad automática. Ver el comando `add_course_playlist`,
    que enseña un preview real (títulos, duración, subtítulos) antes de
    guardar nada.
    """
    language = models.CharField(max_length=40, help_text="Ej. 'francés'. En minúscula, sin acentos raros.")
    level = models.CharField(
        max_length=2, choices=Plan.CEFR_LEVEL_CHOICES,
        help_text="Nivel más bajo que cubre esta playlist (si solo cubre uno, es el único).",
    )
    # La mayoría de playlists curadas cubren un único nivel MCER — pero
    # algunas (sobre todo canales grandes, tipo curso completo en una
    # sola lista) van seguidas de A1 a B2 o similar, sin cortes. En
    # blanco = cubre solo `level`, como antes de que existiera este
    # campo (compatible con todo el catálogo ya cargado). Puesto, dice
    # el nivel más alto que cubre — ver CoursePlaylist.levels_covered()
    # y api._catalog_entries_for_language, que ya no exige coincidencia
    # exacta de nivel: basta con que el rango [level, level_to] toque
    # alguno de los niveles pedidos.
    level_to = models.CharField(
        max_length=2, blank=True, choices=Plan.CEFR_LEVEL_CHOICES,
        help_text="Si esta playlist cubre VARIOS niveles seguidos sin cortes (ej. una sola "
                   "playlist de A1 a B2), el nivel más alto que cubre. En blanco = cubre solo "
                   "`level`, como hasta ahora.",
    )
    # En qué idioma están las explicaciones del curso — no el idioma que
    # se aprende (eso es `language`), sino el del hablante al que va
    # dirigido (ej. un curso de francés "para hispanohablantes" lleva
    # native_language="español"). En blanco = neutro/inmersión (vale
    # para cualquiera, ej. subtítulos en el propio idioma que se
    # aprende, sin explicaciones de por medio). Sirve para no recomendar
    # un curso pensado para hablantes de otro idioma distinto al nativo
    # del usuario — ver Plan.known_languages y
    # api._catalog_entries_for_language.
    native_language = models.CharField(
        max_length=40, blank=True,
        help_text="Idioma en el que se explica el curso (ej. 'español'). En blanco = neutro, "
                   "vale para cualquier hablante.",
    )
    youtube_playlist_id = models.CharField(max_length=64)
    title = models.CharField(max_length=300, blank=True)
    channel_title = models.CharField(max_length=200, blank=True)
    notes = models.TextField(
        blank=True, help_text="Por qué se eligió esta playlist, qué cubre, algo a vigilar...",
    )
    is_active = models.BooleanField(
        default=True, help_text="Desactivar en vez de borrar si deja de estar disponible o resulta floja.",
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Orden dentro de su idioma+nivel+idioma nativo, si hay varias — la de menor "
                   "número es la que se asigna primero.",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["language", "level", "order"]

    def __str__(self):
        audience = f" · para {self.native_language}" if self.native_language else " · neutro"
        return f"{self.title or self.youtube_playlist_id} ({self.language} · {self.level_label}{audience})"

    @property
    def level_label(self):
        """'A1' si es de un solo nivel, 'A1 → B2' si cubre varios seguidos."""
        return self.level if not self.level_to or self.level_to == self.level else f"{self.level} → {self.level_to}"

    def levels_covered(self):
        """Todos los niveles MCER que cubre, de `level` a `level_to`
        (o solo `level` si `level_to` está en blanco) — ver CEFR_LEVELS
        al principio de este archivo."""
        start = CEFR_LEVELS.index(self.level) if self.level in CEFR_LEVELS else 0
        end = CEFR_LEVELS.index(self.level_to) if self.level_to in CEFR_LEVELS else start
        if end < start:
            start, end = end, start
        return CEFR_LEVELS[start:end + 1]


class CourseModule(models.Model):
    """
    Un vídeo concreto dentro del temario de un plan de Estudio · Idiomas
    (Plan.study_subtype='language').

    A diferencia del resto de Estudio (donde el objetivo es el mismo
    vídeo/playlist repetido cada sesión, ver PlanItem), un curso de
    idioma es una SECUENCIA: vídeos distintos, de nivel creciente, uno
    (o varios) por sesión — casi siempre de VARIAS playlists de YouTube
    encadenadas (pocas playlists gratis cubren de A1 a C2 seguido), pero
    una sola playlist puede aportar varios módulos seguidos si cubre
    más de un nivel (ver CoursePlaylist.level_to). Por eso el orden lo
    posee esta tabla, no una playlist de YouTube.

    Se rellena a partir de las `CoursePlaylist` ya verificadas para el
    idioma (y el idioma nativo) del plan — nunca de una búsqueda en
    caliente sin revisar. Ver `api._apply_language_plan_fields` /
    `api.build_language_plan_draft` / `api.expand_language_selection`
    para el flujo completo (asignación directa del catálogo →
    previsualizar → confirmar) — ya no pasa por IA, ver docstring de
    `build_language_plan_draft`.
    """
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="course_modules")
    order = models.PositiveIntegerField(default=0, help_text="Posición en el temario completo del curso.")
    scheduled_week = models.PositiveIntegerField(
        null=True, blank=True, help_text="En qué semana del plan toca ver este vídeo.",
    )
    level = models.CharField(max_length=2, blank=True, choices=Plan.CEFR_LEVEL_CHOICES)

    youtube_video_id = models.CharField(max_length=32)
    title = models.CharField(max_length=300, blank=True)
    channel_title = models.CharField(max_length=200, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    has_captions = models.BooleanField(
        default=False,
        help_text="Si YouTube reporta subtítulos disponibles — no garantiza que se puedan "
                   "descargar (ver notas de tasks/youtube_search.py), pero ayuda a priorizar.",
    )
    source_playlist = models.ForeignKey(
        CoursePlaylist, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="De qué playlist curada salió, para poder revisar la fuente.",
    )

    # Tema del bloque al que pertenece este vídeo (varios vídeos seguidos
    # suelen compartir tema, ej. "saludos y presentarse"). Hoy se deja
    # en blanco al crear el temario (nadie lo rellena todavía a mano) —
    # api.maybe_trigger_quiz() usa esto si está, y si no, cae en
    # `title` — ver CourseQuiz para el test que se genera con esto.
    topic = models.CharField(max_length=200, blank=True)

    # Cuándo se vio de verdad, para poder revisarlo — el avance real
    # (qué vídeo toca hoy) sigue basándose en Occurrence, no en esto
    # (ver Plan._language_completed_count). Lo pone
    # Plan.mark_current_module_watched(), llamado justo después de
    # guardar la Occurrence del día (ver views.task_video_save).
    watched_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.title or self.youtube_video_id} ({self.level or 'sin nivel'})"


class CourseQuiz(models.Model):
    """
    Un test corto de opción múltiple, generado con IA a partir de los
    temas de los últimos `Plan.quiz_every_n_videos` vídeos vistos de un
    curso de idioma — ver `api.maybe_trigger_quiz` (se dispara solo,
    desde `views.task_video_save`, justo después de marcar el vídeo
    como visto).

    A propósito NO bloquea nada: el vídeo ya cuenta como hecho al
    verlo (Task.mark_done), pase lo que pase aquí — este test es un
    "aparte" con su propia racha (ver `Plan.quiz_streak_stats` /
    `streak_stats` de abajo), pensado para forzar que se preste
    atención de verdad sin arriesgar el progreso del curso en sí si un
    día sale mal.
    """
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="quizzes")
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    # CourseModule.order del último vídeo cubierto por este test — solo
    # para trazabilidad y para no generar dos tests seguidos sobre
    # exactamente el mismo tramo (ver api.maybe_trigger_quiz).
    up_to_order = models.PositiveIntegerField(default=0)
    topics = models.JSONField(
        default=list, blank=True, help_text="Temas de los vídeos usados para generar este test.",
    )
    # [{"question": "...", "options": ["...", "...", "...", "..."], "correct_index": 0}, ...]
    questions = models.JSONField(default=list, blank=True)
    # Índices elegidos por el usuario, mismo orden que `questions`. En
    # blanco hasta que se responde.
    answers = models.JSONField(null=True, blank=True)
    score = models.PositiveIntegerField(null=True, blank=True)
    total = models.PositiveIntegerField(default=0)
    passed = models.BooleanField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    # ≥70% de aciertos aprueba — ni "todo perfecto o nada" (desanima sin
    # motivo por un despiste) ni "con que respondas ya vale" (no fuerza
    # a prestar atención de verdad, que es todo el propósito de esto).
    PASS_THRESHOLD = 0.7

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        estado = "sin responder" if not self.answered_at else ("aprobado" if self.passed else "no aprobado")
        return f"Test de {self.plan.language_name} — {estado}"

    def answer(self, selected):
        """
        Corrige `selected` (lista de índices elegidos, mismo orden que
        `questions`) y guarda el resultado. Un índice que falta o no es
        válido cuenta como fallo, nunca como excepción — un test a
        medio responder simplemente saca peor nota, no rompe la página.
        """
        total = len(self.questions)
        score = 0
        for i, q in enumerate(self.questions):
            chosen = selected[i] if i < len(selected) else None
            if isinstance(chosen, int) and chosen == q.get("correct_index"):
                score += 1
        self.answers = list(selected)
        self.score = score
        self.total = total
        self.passed = total > 0 and (score / total) >= self.PASS_THRESHOLD
        self.answered_at = timezone.now()
        self.save(update_fields=["answers", "score", "total", "passed", "answered_at"])
        return self

    @classmethod
    def streak_stats(cls, plan_id):
        """Misma cuenta que Occurrence.streak_stats, pero sobre tests ya
        respondidos de este plan: se rompe en cuanto uno no se aprueba."""
        quizzes = list(
            cls.objects.filter(plan_id=plan_id, answered_at__isnull=False).order_by("-answered_at")
        )
        current = 0
        for q in quizzes:
            if q.passed:
                current += 1
            else:
                break
        max_s = 0
        running = 0
        for q in reversed(quizzes):
            if q.passed:
                running += 1
                max_s = max(max_s, running)
            else:
                running = 0
        return {"current_streak": current, "max_streak": max_s}


class SavedVideo(models.Model):
    """
    Vídeos de YouTube guardados para reutilizar sin tener que pegar el
    enlace cada vez que se entrena o se estudia.

    Se eligen en el momento de hacerlo, como alternativa al modo de
    siempre (circuito, cámara, temporizador) — no van atados a una
    tarea concreta, así una tarea que se repite puede usar un vídeo
    distinto cada día, o ninguno. `scope` es solo para filtrar la lista
    y no enseñar vídeos de estudio al entrenar tren inferior.
    """
    SCOPE_LOWER_BODY = "lower_body"
    SCOPE_UPPER_BODY = "upper_body"
    SCOPE_STUDY = "study_session"
    SCOPE_CHOICES = [
        (SCOPE_LOWER_BODY, "Tren inferior"),
        (SCOPE_UPPER_BODY, "Tren superior"),
        (SCOPE_STUDY, "Estudio"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name="saved_videos",
    )
    scope = models.CharField(max_length=16, choices=SCOPE_CHOICES)
    title = models.CharField(
        max_length=120, blank=True,
        help_text="Para reconocerlo en la lista. En blanco, se enseña el ID del vídeo.",
    )
    youtube_video_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        raw = (self.youtube_video_id or "").strip()
        if raw:
            m = _YOUTUBE_ID_RE.search(raw)
            self.youtube_video_id = m.group(1) if m else raw
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title or self.youtube_video_id


class AIGenerationLog(models.Model):
    """
    Un registro por cada vez que se llama a la IA para generar un plan
    (con éxito o sin él — una llamada fallida a Gemini también gasta
    cuota gratis, así que también cuenta).

    Existe solo para poner un tope diario de generaciones y así proteger
    la cuota gratis de GEMINI_API_KEY, que hoy es una sola clave
    compartida por toda la app — si en el futuro hay más de una persona
    usándola, evita que alguien (a propósito o sin querer) se la deje a
    cero para todos los demás. En cuanto haya cuentas de usuario de
    verdad, este tope debería pasar a ser por persona en vez de global
    (ya lleva el campo `user` preparado para eso).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name="ai_generation_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def count_today(cls, user=None):
        today = timezone.localtime(timezone.now()).date()
        qs = cls.objects.filter(created_at__date=today)
        if user is not None:
            qs = qs.filter(user=user)
        return qs.count()

    @classmethod
    def record(cls, user=None):
        cls.objects.create(user=user)


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
    minutes_watched = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Solo en tareas de vídeo: minutos reales vistos en el navegador "
                   "(IFrame API de YouTube), no un dato introducido a mano.",
    )
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

    @classmethod
    def weekly_completion(cls, user, reference_date=None, series_id=None):
        """
        Porcentaje de ejecución de la semana actual (lunes a domingo).

        Primera pieza del 12 Week Year: una división simple sobre las
        ocurrencias que ya se guardan — sin modelo nuevo, sin campo
        nuevo. "Empieza por aquí" porque es barato y da una lectura
        inmediata de cómo va la semana cada vez que se abre la lista.

        Cada ocurrencia se cuenta en la semana de su due_date (el día al
        que pertenecía la tarea) si lo tiene, y si no en la semana en
        que se registró — mismo criterio que PlanItem.history() usa
        para las tareas sin due_date.

        Con `series_id` se filtra a una sola serie (ej. la tarea de un
        plan concreto) en vez del global — es lo que usa Plan.weekly_completion
        para la revisión semanal por objetivo, reutilizando exactamente
        el mismo cálculo.
        """
        today = reference_date or timezone.localtime(timezone.now()).date()
        week_start = today - timedelta(days=today.weekday())  # lunes
        week_end = week_start + timedelta(days=6)             # domingo

        occs = cls.objects.filter(user=user, deleted_at__isnull=True)
        if series_id:
            occs = occs.filter(series_id=series_id)
        occs = occs.filter(
            models.Q(due_date__gte=week_start, due_date__lte=week_end)
            | models.Q(
                due_date__isnull=True,
                recorded_at__date__gte=week_start,
                recorded_at__date__lte=week_end,
            )
        )
        total = occs.count()
        done = occs.filter(result=cls.RESULT_DONE).count()
        return {
            "week_start": week_start,
            "week_end": week_end,
            "done": done,
            "not_done": total - done,
            "total": total,
            "pct": round(100 * done / total) if total else None,
        }
