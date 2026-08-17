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
- **Planes** con progresión (deporte, estudio o un hábito general) y, dentro
  de un plan, **generar un plan con IA** describiéndolo en una frase — la IA
  propone objetivos medibles (ej. "3×8 dominadas la semana 1, 3×9 la semana
  2...") a partir del catálogo de ejercicios y de cuántas semanas/días
  elijas tú; siempre se enseña un borrador para revisar antes de guardar
  nada. Ver "IA para generar planes" más abajo.
- **Cursos de idioma**: un subtipo de plan de Estudio con vídeos reales de
  YouTube, del catálogo curado y filtrados por tu idioma nativo — sin IA de
  por medio, ver "Cursos de idiomas · YouTube" más abajo. Cada cierto número
  de vídeos (a elegir) sale un **test de repaso** corto, generado con IA, con
  su propia racha — no bloquea el curso, es un empujón aparte para prestar
  atención de verdad.

## Cómo ejecutarlo

```bash
pip install django
python3 manage.py migrate
python3 manage.py runserver
```

Abre http://127.0.0.1:8000/ en el navegador.

(Opcional) Para gestionar tareas desde el panel de admin de Django:
```bash
python3 manage.py createsuperuser
```
y entra en http://127.0.0.1:8000/admin/

## IA para generar planes

El botón "✨ Generar con IA" de la pantalla de Planes usa **Google Gemini**
(modelos Flash/Flash-Lite, gratis sin tarjeta) para proponer un plan a
partir de una frase. Sin configurar nada, ese botón simplemente falla con
un aviso legible — el resto de la app funciona igual.

Para activarlo:
1. Pide una clave gratis en https://aistudio.google.com/apikey.
2. Defínela como variable de entorno antes de arrancar el servidor:
   ```bash
   export GEMINI_API_KEY="tu-clave-aqui"
   python3 manage.py runserver
   ```
   (En el hosting, añádela en la sección de variables de entorno de siempre,
   junto a `DJANGO_SECRET_KEY` etc.)

No añade ninguna dependencia nueva: `tasks/ai.py` habla con la API de
Gemini con `urllib` (ya viene en Python), así que `requirements.txt` no
cambia y el proyecto se sigue pudiendo alojar gratis.

## Cursos de idiomas · YouTube

Los planes de Estudio tienen un subtipo "Idiomas": en vez de un hábito
diario con siempre el mismo vídeo, un curso de verdad con vídeos reales
de YouTube ordenados de nivel MCER más bajo a más alto (ver
`Plan.study_subtype` y el modelo `CourseModule` en `tasks/models.py`).
El flujo está implementado de punta a punta: desde "Planes" → "✨
Generar con IA" eliges idioma, nivel de partida y de llegada, y **la
propia app asigna, SIN IA**, qué cursos del catálogo verificado de
abajo tocan — es una decisión mecánica entre opciones ya curadas a
mano, no algo que necesite un LLM (ver `api.build_language_plan_draft`
en `tasks/api.py`). Se previsualiza y se confirma igual que un plan
con IA, y el plan queda con el curso programado y una barra de
progreso en su pantalla de detalle.

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
`api._catalog_entries_for_language`).

**Filtrado por idioma nativo**: cada `CoursePlaylist` del catálogo
lleva un `native_language` (en qué idioma están las explicaciones —
ej. un curso de francés "para hispanohablantes" lleva
`native_language="español"`) o se deja en blanco si es neutro (vale
para cualquiera). Al crear el plan, el PRIMER idioma que escribas en
"Idiomas que ya sabes" decide qué cursos se ofrecen: los explicados en
ese idioma tienen prioridad, luego los neutros, y los pensados para un
idioma nativo distinto quedan excluidos del todo — nunca un curso
genérico para cualquiera si hay uno mejor pensado para ti.

**Lo único que hace falta antes de poder usarlo es poblar el catálogo**
(ver los dos comandos más abajo) — sin ninguna `CoursePlaylist`
verificada para el idioma (e idioma nativo) que pidas, la asignación
falla con un aviso legible en vez de inventarse un curso.

Dos límites a tener en cuenta mientras tanto:
- El idioma se escribe como texto libre y la búsqueda en el catálogo
  ignora mayúsculas pero NO ignora acentos — usa siempre la misma
  grafía con la que lo guardaste con `add_course_playlist` (ej.
  siempre "francés", nunca a veces "frances"). Lo mismo aplica al
  idioma nativo.
- Por ahora este flujo solo está disponible desde la web; la app móvil
  todavía no sabe generar ni reproducir un curso de idioma — un plan
  creado en la web se vería vacío si lo abres en el móvil.

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
idioma/nivel/idioma nativo que pidas, "Generar con IA" falla con un
aviso claro en vez de devolver algo inventado.

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
- `tasks/ai.py` — el cliente de Gemini: la traducción de "en cuántas
  semanas quiero llegar" a la progresión escalón a escalón de un
  `PlanItem` (Deporte/Estudio general), y `generate_quiz` para los
  tests de repaso de idioma. La asignación de cursos de idioma en sí
  (`tasks/api.py`) NO pasa por aquí — es determinista, sin IA.
- `tasks/youtube_search.py` — cliente de la YouTube Data API v3 (ver
  sección de arriba). `CoursePlaylist` en `models.py` es el catálogo
  curado a mano (con su `native_language`); `CourseModule` es el
  temario ya curado de cada plan de idioma, generado por
  `api.expand_language_selection` a partir de lo que
  `api.build_language_plan_draft` asigna del catálogo. `CourseQuiz` es
  cada test de repaso generado, con su racha (`Plan.quiz_streak_stats`).
- `tasks/templates/tasks/` — plantillas de tareas, planes (incluidos
  los de idioma), circuitos y entrenos. `task_list.html` es la vista
  principal; `plan_detail.html`/`plan_ai_form.html`/`plan_ai_preview.html`
  cubren el flujo de planes con y sin IA.
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
