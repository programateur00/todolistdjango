# Libreta — to-do list estilo Microsoft To Do

App web hecha con Django, HTML y CSS (sin frameworks JS), pensada para
convertirse después en mobile-friendly / PWA.

## Funcionalidades
- Crear tareas con título, notas, fecha de vencimiento.
- Recurrencia: ninguna, diaria, semanal, mensual, anual, o **personalizada**
  (elige los días de la semana concretos, ej. lunes y jueves).
  Además, cualquier recurrencia admite un **intervalo** ("cada 2 semanas",
  "cada 3 meses", "cada 2 semanas en lunes y jueves", etc.).
  Al marcar una tarea recurrente como hecha, se genera automáticamente
  la siguiente ocurrencia con la fecha recalculada respetando el intervalo.
- Marcar tarea como **importante**.
- Dos botones de estado por tarea:
  - ✔ Hecho
  - ✘ No hecho
  Cada clic queda registrado en el historial de esa tarea (no son
  contadores globales de la app, sino por tarea).
- **Estadísticas por tarea**: una pantalla aparte (icono de gráfico arriba)
  donde ves, para cada tarea (o serie de tareas recurrentes), cuántas veces
  la cumpliste y cuántas no, el % de cumplimiento, y el historial completo
  con fechas — para tener accountability real de tus hábitos.
- Listado separado de tareas pendientes y hechas, con tachado.
- Eliminar tareas.
- **Planes** con progresión: Deporte, Estudio (con dos subtipos, ver abajo)
  o General (un hábito simple sin catálogo detrás). Los de Deporte se
  pueden crear a mano o **generar automáticamente**: eliges nivel físico,
  foco corporal, equipamiento y cuántas semanas/días entrenas, y la app
  elige los ejercicios que tocan para ese nivel y calcula la progresión
  (ej. "3×8 dominadas la semana 1, 3×9 la semana 2...") con matemáticas
  fijas — sin IA, sin llamada de red, sin límite de peticiones. Siempre se
  enseña un borrador para revisar (y tocar cualquier número) antes de
  guardar nada. Ver "Generar plan automáticamente" más abajo.
- **Estudio** tiene dos subtipos, y ninguno de los dos usa IA para
  crearse: "Hábito simple" (una tarea diaria comprobable, con vídeo,
  playlist o minutos objetivo si los rellenas — ya quedan puestos desde el
  momento en que creas el plan, sin ningún paso aparte) y **"Idioma"**
  (vídeos reales de YouTube del catálogo curado, filtrados por tu idioma
  nativo — ver "Cursos de idiomas · YouTube" más abajo). Para el subtipo
  Idioma, cada cierto número de vídeos (a elegir) sale un **test de
  repaso** corto, generado con IA, con su propia racha — no bloquea el
  curso, es un empujón aparte para prestar atención de verdad.

## Cómo ejecutarlo

```bash
pip install -r requirements.txt
python3 manage.py migrate
python3 manage.py runserver
```

Abre http://127.0.0.1:8000/ en el navegador.

Para las claves de IA/YouTube (opcional, ver más abajo), copia
`.env.example` como `.env` y rellénalo — `settings.py` lo carga solo
con tenerlo ahí, no hace falta tocar variables de entorno de Windows/Mac
a mano ni reiniciar nada cada vez que cambias una clave.

(Opcional) Para gestionar tareas desde el panel de admin de Django:
```bash
python3 manage.py createsuperuser
```
y entra en http://127.0.0.1:8000/admin/

## Seguridad y despliegue en producción

Variables de entorno: ver `.env.example` en la raíz del proyecto — documenta
las 9 que existen (clave secreta, DEBUG, hosts permitidos, CORS extra,
candado Basic Auth, claves de Gemini/YouTube) y cómo cargarlas en
PythonAnywhere (con `python-dotenv` desde el archivo WSGI, que vive fuera
del repo y no lo toca `git pull`).

`DJANGO_DEBUG` sigue con default `"True"` a propósito, no al revés: en este
hosting el valor real de producción se fija explícitamente en el archivo
WSGI, así que invertir el default no añade seguridad aquí y sí rompería
`runserver` en local sin la variable definida (se perderían los
`ALLOWED_HOSTS` locales y los tracebacks detallados de desarrollo).

Cookies de sesión y CSRF: con `DEBUG=False`, `SESSION_COOKIE_SECURE` y
`CSRF_COOKIE_SECURE` fuerzan a que esas cookies solo viajen por HTTPS, y
`CSRF_COOKIE_HTTPONLY` evita que JavaScript pueda leer la cookie CSRF (el
token se lee de la plantilla, no de la cookie, así que esto no rompe nada).
En local (`DEBUG=True`) no cambia nada de esto.

Forzar HTTPS (redirigir toda visita `http://` a `https://`): no se hace
desde Django con `SECURE_SSL_REDIRECT` — PythonAnywhere lo desaconseja,
porque puede acabar en un bucle de redirección si el proxy no comunica
bien el esquema. Se activa en su lugar desde su panel: pestaña "Web" → tu
sitio → sección "Security" → toggle de forzar HTTPS.

Copia de seguridad de la base de datos (`db.sqlite3`):
```bash
python manage.py backup_db            # copia a backups/, con marca de tiempo
python manage.py backup_db --keep 30  # conserva las últimas 30 (por defecto 14)
python manage.py backup_db --dry-run  # enseña qué haría, sin tocar nada
```
`backups/` no se sube a git. Para que corra sola, prográmala en la pestaña
"Tasks" de PythonAnywhere (las cuentas gratuitas creadas antes del
15-01-2026 incluyen 1 tarea diaria):
```
cd /home/tu_usuario/tu_proyecto && python manage.py backup_db
```
Esto protege de un borrado accidental o una migración que sale mal — no de
perder la cuenta entera, porque la copia queda en el mismo disco. Si algún
día hay datos que de verdad importe no perder, conviene bajarse `backups/`
de vez en cuando a otro sitio.

## Generar plan automáticamente

El botón "⚡ Generar automáticamente" de la pantalla de Planes crea un
plan de **Deporte** sin IA de por medio y sin llamada de red — solo
matemáticas fijas, así que no depende de ninguna cuota gratis ni tiene
límite de peticiones. Rellenas un cuestionario corto (nivel físico, foco
corporal, equipamiento, peso máximo de lastre disponible, semanas y
días de entreno) y la app:

1. Elige los ejercicios del catálogo que tocan para ese nivel y foco —
   mismo filtro EN DURO de siempre (`ai._filter_catalog_by_level`,
   `ai._backfill_lower_tier`): un principiante nunca ve dominadas
   lastradas, un avanzado no se queda solo con flexiones.
2. Pone el punto de partida y la meta de cada ejercicio según tablas
   fijas por nivel (`ai._EXERCISE_CATEGORY_DEFAULTS` en `tasks/ai.py`) —
   dominadas/fondos a pulso empiezan más bajo que sentadillas o
   flexiones, que se hacen en tandas más largas.
3. Calcula el incremento real por escalón con `ai.apply_pacing` (la
   misma cuenta que ya usaba la calculadora del formulario manual) para
   que la exigencia suba de verdad a lo largo de las semanas elegidas.

Como siempre, antes de guardar nada se enseña un borrador
(`plan_ai_preview.html`) donde puedes tocar cualquier número o pedir
otra propuesta con los mismos filtros.

Los planes de Estudio (sus dos subtipos, Hábito simple e Idioma) y los
de General nunca pasan por aquí: no tienen catálogo de ejercicios del
que autogenerar nada, así que se crean siempre a mano, desde "+ Nuevo
plan a mano" — ver "Cursos de idiomas · YouTube" más abajo para el
subtipo Idioma.

Lo ÚNICO que sigue usando IA (**Google Gemini**, modelos Flash/Flash-Lite,
gratis sin tarjeta) en toda la app es el test de repaso corto de Estudio
· Idiomas, sobre los últimos vídeos vistos — ver la siguiente sección.
Para activarlo:
1. Pide una clave gratis en https://aistudio.google.com/apikey.
2. Dásela a la app. Más fácil: copia `.env.example` como `.env` y pon
   `GEMINI_API_KEY=tu-clave-aqui` ahí — `settings.py` lo carga solo, sin
   tocar nada más (ver "Cómo ejecutarlo" más arriba). También puedes
   definirla como variable de entorno de toda la vida si lo prefieres:
   ```bash
   export GEMINI_API_KEY="tu-clave-aqui"    # macOS/Linux, solo esa terminal
   python3 manage.py runserver
   ```
   En Windows PowerShell, `$env:GEMINI_API_KEY="tu-clave-aqui"` solo dura
   esa ventana; `setx GEMINI_API_KEY "tu-clave-aqui"` la deja fija pero
   solo la ven las terminales que abras DESPUÉS (y solo si además cierras
   y vuelves a abrir del todo VS Code — una pestaña de terminal nueva
   dentro de un VS Code que ya estaba abierto sigue viendo el entorno
   viejo). El `.env` de arriba se salta todo este lío.
   (En el hosting, sigue yendo por variables de entorno de verdad — ver
   "Cómo cargar esto en PythonAnywhere" en `.env.example`.)
   Sin esto, solo falla el test de repaso — el resto de la app (incluido
   "Generar automáticamente") funciona igual, no lo necesita.

## Cursos de idiomas · YouTube

Los planes de Estudio tienen un subtipo "Idiomas": en vez de un hábito
diario con siempre el mismo vídeo, un curso de verdad con vídeos reales
de YouTube ordenados de nivel MCER más bajo a más alto (ver
`Plan.study_subtype` y el modelo `CourseModule` en `tasks/models.py`).
El flujo está implementado de punta a punta y es **siempre manual, sin
botón de IA de por medio**: desde "Planes" → "+ Nuevo plan a mano"
eliges Estudio → Idioma (curso con vídeos por nivel), rellenas idioma,
nivel de partida y de llegada, e idiomas que ya sabes, y **la propia
app asigna, SIN IA**, qué cursos del catálogo verificado de abajo tocan
— es una decisión mecánica entre opciones ya curadas a mano, no algo
que necesite un LLM (ver `api.build_language_plan_draft` y
`api._select_language_catalog` en `tasks/api.py`). Antes de guardar
nada se enseña una pantalla de revisión (`plan_language_confirm.html`)
con qué cursos y en qué orden se van a encadenar, para confirmar o
volver atrás a cambiar idioma/nivel; al confirmar, el plan queda con el
curso programado y una barra de progreso en su pantalla de detalle. Si
por lo que sea un plan se queda sin ningún vídeo asignado (por ejemplo,
un fallo puntual de la YouTube Data API al confirmar), su pantalla de
detalle ofrece un botón para "Reintentar asignar cursos del catálogo"
sin tener que borrar el plan y volver a crearlo.

**El objetivo es terminar el temario, no acabar en un número de
semanas fijo**: al crear el plan no se pide "cuántas semanas dura"
sino qué días de la semana vas a estudiar — ese es tu ritmo real (cada
día de esos avanza un vídeo). Con eso, el plan calcula una estimación
de cuántas semanas te llevará, pero es solo orientativa: si vas más
lento de lo estimado, el plan sigue abierto en vez de cerrarse a
medias; si el temario se acaba antes (por ejemplo porque una playlist
era corta), se cierra en cuanto terminas el último vídeo en vez de
seguir enseñándotelo hasta que pasen las semanas que sobraban (ver
`Plan.auto_close_expired` en `tasks/models.py`). Y si para un mismo
nivel hay varias playlists verificadas en el catálogo, se **encadenan
todas** en vez de asignar solo una — así, si la primera se queda
corta, ya tienes la siguiente esperando en ese mismo nivel (ver
`api._select_language_catalog`).

**Filtrado por idioma nativo**: cada `CoursePlaylist` del catálogo
lleva un `native_language` (en qué idioma están las explicaciones —
ej. un curso de francés "para hispanohablantes" lleva
`native_language="español"`) o se deja en blanco si es neutro (vale
para cualquiera). Al crear el plan, se ofrecen los cursos explicados en
CUALQUIERA de los idiomas que escribas en "Idiomas que ya sabes" (no
hace falta que sea el primero de la lista) más los neutros; los
pensados para un idioma nativo que no hayas dicho que sabes quedan
excluidos del todo — nunca un curso genérico para cualquiera si hay
uno mejor pensado para ti.

**Lo único que hace falta antes de poder usarlo es poblar el catálogo**
(ver los dos comandos más abajo) — sin ninguna `CoursePlaylist`
verificada para el idioma (e idioma nativo) que pidas, la asignación
falla con un aviso legible en vez de inventarse un curso.

Un límite a tener en cuenta mientras tanto:
- Por ahora este flujo solo está disponible desde la web; la app móvil
  todavía no sabe generar ni reproducir un curso de idioma — un plan
  creado en la web se vería vacío si lo abres en el móvil.

El idioma (y el idioma nativo) se escriben como texto libre, tanto al
crear el plan como al añadir playlists con `add_course_playlist` — la
búsqueda en el catálogo (`api._language_matches`, usada por
`_select_language_catalog`) ignora mayúsculas y acentos, así que
"frances"/"Francés"/"FRANCÉS" cuentan como el mismo idioma que lo que
hayas guardado. También tolera texto de más alrededor: "curso de
francés" o "quiero aprender francés" encuentran igual el catálogo
guardado como "francés", y "Idiomas que ya sabes" puede llevar varios
("español, inglés" o "hablo español e inglés") — cualquiera de ellos
que coincida con el `native_language` de un curso cuenta. Lo que sí
tiene que coincidir es la palabra en sí: si guardaste el catálogo como
"francés" no lo vas a encontrar escribiendo "French", y "castellano" no
cuenta como lo mismo que "español" si el catálogo usa esa palabra.

Ni Gemini ni ningún LLM navega YouTube ni comprueba que un vídeo
existe — así que la búsqueda de vídeos reales la hace la propia
**YouTube Data API v3**. Y probando esto en la práctica (con francés)
apareció algo más importante todavía: cuando un nivel no tiene curso
gratis de verdad (sobre todo C1/C2), YouTube no dice "no hay nada" —
devuelve lo más parecido por relevancia genérica, casi siempre cursos
de principiantes reetiquetados. Así que tampoco se puede fiar nada
directamente de una búsqueda en caliente.

La solución es un **catálogo curado a mano**, igual que ya existe para
Deporte (`Exercise`): una persona decide qué playlist es de verdad de
qué idioma, nivel e idioma nativo, y la app solo asigna entre lo ya
verificado — nunca descubre ni decide por su cuenta.

Dos comandos, pensados para usarse en este orden:

1. **Descubrir candidatos** (no guarda nada, solo enseña qué hay):
   ```bash
   python3 manage.py search_courses francés
   python3 manage.py search_courses francés --levels A1 A2 B1
   ```
   Si la misma playlist sale repetida en varios niveles pedidos, el
   comando lo avisa con ⚠ — es la señal de que no es contenido propio
   de ninguno de esos niveles, solo relleno.

2. **Añadir al catálogo las que de verdad valen** (con vista previa real
   de los vídeos antes de guardar nada, y pidiendo confirmación):
   ```bash
   python3 manage.py add_course_playlist francés B1 "https://www.youtube.com/playlist?list=PL..." --native-language español
   ```
   Sin `--native-language`, la playlist queda **neutra** (se ofrece a
   cualquiera, ej. subtítulos en el propio idioma que se aprende, sin
   explicaciones de por medio) — no "para nadie".

   Si la playlist cubre **varios niveles seguidos sin cortes** (ej. un
   curso completo de A1 a B2 en una sola lista de YouTube — pasa más de
   lo que parece con canales grandes), añade `--level-to`:
   ```bash
   python3 manage.py add_course_playlist francés A1 "https://www.youtube.com/playlist?list=PL..." --level-to B2 --native-language inglés
   ```
   Sus vídeos se reparten en tramos iguales entre `A1` y `B2` para
   estimar en qué nivel va cada uno (no hay forma de saber el vídeo
   exacto donde cambia de nivel sin revisarla entera a mano) — y
   entra en la asignación de cualquier nivel de ese rango que se pida,
   no solo de `A1`.

Los planes de idioma se arman solo de este catálogo, nunca de una
búsqueda sin revisar — por eso, si el catálogo está vacío para el
idioma/nivel/idioma nativo que pidas, crear el plan falla con un aviso
claro ("Todavía no hay ningún curso verificado de... en el catálogo
para ese nivel") en vez de devolver algo inventado.

### Tests de repaso

Al crear un plan de idioma puedes poner "cada cuántos vídeos" quieres
un test corto (`Plan.quiz_every_n_videos`, en blanco = sin tests). Al
llegar a ese número de vídeos vistos, la app genera con IA (Gemini)
unas preguntas de opción múltiple sobre los temas de esos vídeos y te
lleva a responderlas justo después de guardar el vídeo como visto —
ver `CourseQuiz` en `tasks/models.py` y `api.maybe_trigger_quiz`.

El test **no bloquea nada**: el vídeo ya cuenta como visto lo hagas
bien o mal, o aunque no llegues a hacerlo (basta con no tocar el
enlace — no hay temporizador ni recordatorio). Lo único que se ve
afectado es su propia racha (aprobar = ≥70% de aciertos), pensada
como un empujón aparte para prestar atención de verdad, sin arriesgar
el progreso del curso en sí.

Para activar la búsqueda hace falta una clave gratis **distinta** de la
de Gemini:
1. Entra en [Google Cloud Console](https://console.cloud.google.com/),
   crea un proyecto (o usa uno que ya tengas) y activa la **"YouTube
   Data API v3"** desde la biblioteca de APIs.
2. Ve a "Credenciales" → "Crear credenciales" → "Clave de API". Es
   gratis, con una cuota diaria de 10.000 unidades (una búsqueda de
   curso completo por los 6 niveles gasta unas 600).
3. Defínela como variable de entorno antes de arrancar el servidor:
   ```bash
   export YOUTUBE_API_KEY="tu-clave-aqui"
   python3 manage.py runserver
   ```

Sin ella definida, el comando (y más adelante el generador de cursos)
falla con un aviso legible en vez de reventar — el resto de la app
funciona igual, igual que con `GEMINI_API_KEY`.

Tampoco añade dependencias nuevas: `tasks/youtube_search.py` habla con
la API igual que `tasks/ai.py` habla con Gemini, con `urllib`.

## Estructura
- `tasks/models.py` — modelos `Task` y `Occurrence` (historial de hechos/no
  hechos), y toda la lógica de recurrencia con intervalo personalizado.
  También `Plan`/`PlanItem` (planes con progresión).
- `tasks/views.py` — vistas para listar, crear, editar, eliminar y
  marcar tareas, y las dos vistas de estadísticas.
- `tasks/ai.py` — dos cosas sin relación entre sí, que comparten archivo
  por tamaño (no por diseño): la generación 100% determinista de un plan
  de Deporte (`_select_sport_exercises`, `default_item_fields`,
  `apply_pacing` — sin IA, sin llamada de red), y el cliente de Gemini
  que usa solo `generate_quiz`, para los tests de repaso de idioma. La
  asignación de cursos de idioma y la creación a mano de un plan de
  Estudio·Hábito simple (`tasks/api.py`/`tasks/views.py`) tampoco pasan
  por IA — todo el módulo de planes es determinista salvo el propio test
  de repaso.
- `tasks/youtube_search.py` — cliente de la YouTube Data API v3 (ver
  sección de arriba). `CoursePlaylist` en `models.py` es el catálogo
  curado a mano (con su `native_language`); `CourseModule` es el
  temario ya curado de cada plan de idioma, generado por
  `api.expand_language_selection` a partir de lo que
  `api.build_language_plan_draft` asigna del catálogo. `CourseQuiz` es
  cada test de repaso generado, con su racha (`Plan.quiz_streak_stats`).
- `tasks/templates/tasks/` — plantillas de tareas, planes (incluidos
  los de idioma), circuitos y entrenos. `task_list.html` es la vista
  principal; `plan_form.html` cubre la creación/edición a mano de
  cualquier tipo (Deporte, Estudio y General); `plan_ai_form.html`/
  `plan_ai_preview.html` cubren la generación automática (solo Deporte);
  `plan_language_confirm.html` es la pantalla de revisión antes de
  guardar un plan de idioma (ver "Cursos de idiomas · YouTube").
- `static/css/styles.css` — toda la identidad visual ("libreta" cálida,
  tonos crema/coral/sage/mostaza).

## Notas técnicas sobre la recurrencia personalizada
Cada tarea recurrente guarda un `series_id` (compartido por todas sus
ocurrencias) y un `series_start_date` (la fecha de la primera ocurrencia,
usada como "ancla" del ciclo). Así, "cada 2 semanas en lunes y jueves"
sabe exactamente qué semanas son las "activas" del ciclo, en vez de
repetirse todas las semanas.

## App móvil
Ya existe una app Android (Capacitor) en `mobile-app/`, que envuelve
esta misma web y habla con la API bajo `/api/` — ver
`mobile-app/README.md` para cómo compilarla. Funciona sin conexión
(caché de lecturas + cola de escrituras pendientes) salvo para
generar planes de idioma, que por ahora solo está disponible desde el
navegador (ver "Cursos de idiomas · YouTube" más arriba).

### Actualizaciones de la app móvil

En vez de pasar el APK por Drive cada vez, la app comprueba sola si
hay una versión más reciente colgada en el servidor y te deja
descargarla con un toque. No usa Play Store ni ningún servicio
externo — todo vive en tu propio hosting.

Para publicar una build nueva:

1. Compila el APK como siempre, en tu máquina.
2. En PythonAnywhere, pestaña **Files**, entra en la carpeta del
   proyecto y crea (la primera vez) la carpeta `mobile_releases/` —
   no está en git a propósito (son binarios, no código), así que hay
   que crearla a mano una vez.
3. Sube el `.apk` ahí con el botón naranja de subir archivo.
4. Crea o edita `mobile_releases/latest.json` (con el editor de texto
   de la propia pestaña Files, igual que editas el archivo WSGI) con
   este formato — ver `latest.json.ejemplo` en la raíz del repo:
   ```json
   {
     "version": "2",
     "apk_filename": "libreta-v2.apk",
     "notes": "Lo que cambió en esta versión (opcional, solo para ti)"
   }
   ```
5. Sube también `mobile-app/www/js/version.js` con `APP_VERSION`
   puesto al mismo número que `"version"` de arriba, y compila el APK
   con ese cambio ya dentro (para que la propia build compare bien
   contra la siguiente).

No hace falta reiniciar ni recargar nada — `/api/meta/` lee ese JSON
en cada petición. La próxima vez que abras la app en el móvil, si el
número no coincide con el que lleva grabado, aparece un aviso fijo con
un enlace "actualizar" que abre el navegador del sistema, descarga el
APK y Android pregunta si quieres instalarlo.

La descarga sigue detrás del candado Basic Auth de siempre — al tocar
"actualizar" el navegador te va a pedir usuario/contraseña otra vez
(es un navegador aparte del WebView de la app, no comparte el login).
Es una decisión consciente: se prefirió mantener el mismo candado que
protege el resto del sitio antes que dejar esa URL sin autenticación.
