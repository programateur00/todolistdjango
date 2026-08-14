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

## Cursos de idiomas · YouTube (en construcción)

Los planes de Estudio van a tener un subtipo "Idiomas": en vez de un
hábito diario con siempre el mismo vídeo, un curso de verdad con vídeos
reales de YouTube ordenados de nivel MCER más bajo a más alto (ver
`Plan.study_subtype` y el modelo `CourseModule` en `tasks/models.py`).

Gemini no puede navegar YouTube ni comprobar que un vídeo existe — así
que la búsqueda de vídeos reales la hace la propia **YouTube Data API
v3**, no la IA. Y probando esto en la práctica (con francés) apareció
algo más importante todavía: cuando un nivel no tiene curso gratis de
verdad (sobre todo C1/C2), YouTube no dice "no hay nada" — devuelve lo
más parecido por relevancia genérica, casi siempre cursos de
principiantes reetiquetados. Así que la IA tampoco puede fiarse
directamente de una búsqueda en caliente.

La solución es un **catálogo curado a mano**, igual que ya existe para
Deporte (`Exercise`): una persona decide qué playlist es de verdad de
qué idioma y nivel, y la IA (cuando exista esa fase) solo elige y
ordena entre lo ya verificado — nunca descubre ni decide por su cuenta.

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
   python3 manage.py add_course_playlist francés B1 "https://www.youtube.com/playlist?list=PL..."
   ```

Los planes de idioma (todavía no implementados) elegirán solo de este
catálogo, nunca de una búsqueda sin revisar.

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
- `tasks/ai.py` — el cliente de Gemini y la traducción de "en cuántas
  semanas quiero llegar" a la progresión escalón a escalón de un `PlanItem`.
- `tasks/youtube_search.py` — cliente de la YouTube Data API v3 (ver
  sección de arriba). `CoursePlaylist` en `models.py` es el catálogo
  curado a mano; `CourseModule` es donde se guardará el temario ya
  curado de cada plan (Fase 2, todavía no implementada).
- `tasks/templates/tasks/` — `task_list.html` (vista principal),
  `task_form.html` (crear/editar), `stats_list.html` y `stats_detail.html`.
- `static/css/styles.css` — toda la identidad visual ("libreta" cálida,
  tonos crema/coral/sage/mostaza).

## Notas técnicas sobre la recurrencia personalizada
Cada tarea recurrente guarda un `series_id` (compartido por todas sus
ocurrencias) y un `series_start_date` (la fecha de la primera ocurrencia,
usada como "ancla" del ciclo). Así, "cada 2 semanas en lunes y jueves"
sabe exactamente qué semanas son las "activas" del ciclo, en vez de
repetirse todas las semanas.

## Siguiente paso
Esta es la base web. El siguiente paso (cuando quieras) es adaptarla a
mobile: ya está pensada con un layout de una sola columna y botones
grandes táctiles, así que el salto a PWA instalable o a una webview
en una app nativa será sencillo.
