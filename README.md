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

## Estructura
- `tasks/models.py` — modelos `Task` y `Occurrence` (historial de hechos/no
  hechos), y toda la lógica de recurrencia con intervalo personalizado.
  También `Plan`/`PlanItem` (planes con progresión).
- `tasks/views.py` — vistas para listar, crear, editar, eliminar y
  marcar tareas, y las dos vistas de estadísticas.
- `tasks/ai.py` — el cliente de Gemini y la traducción de "en cuántas
  semanas quiero llegar" a la progresión escalón a escalón de un `PlanItem`.
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
