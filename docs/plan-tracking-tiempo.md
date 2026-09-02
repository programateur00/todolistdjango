# Plan: tiempo en Udemy + estadísticas/logros de tiempo acumulado

Resumen de lo hablado, partido en piezas pequeñas para ir pidiéndolas una a
una. El orden importa poco salvo donde se dice explícitamente "depende de".

## Fase 1 — Capa de estadísticas/logros (no depende de nada, ya hay datos)

`WorkoutSession.session_duration_seconds` y `TimerSession.minutes` ya
guardan tiempo real por sesión con `recorded_at` y `user`. No hace falta
trackear nada nuevo para Deporte/Enfoque — solo sumarlo.

- Función/servicio de agregación: total de tiempo por categoría/subcategoría,
  con ventana de fechas (histórico total, este año, plan actual).
- Vista o endpoint que la enseñe (ej. en el perfil): "Has estado 200h
  estudiando", "10.000h haciendo deporte".
- Modelo simple de logros/insignias: umbrales por categoría (100h, 500h,
  1000h, 10.000h...) calculados sobre esos totales — sin tabla propia de
  eventos si no hace falta, se puede derivar en caliente de la suma.

## Fase 2 — Backend para el tracking de Udemy (depende de: nada, pero antes de Fase 3/4)

- Nuevo subtipo en `Task.STUDY_SUBCATEGORY_CHOICES`: `"udemy"` → "Curso de
  Udemy" (junto a `"language"`).
- Campo nuevo en `Task`: `watch_keyword` (palabra clave a buscar en el
  título de la pestaña). Dominio fijo `udemy.com` en la lógica, sin campo
  para el usuario.
- Nuevo valor en `TimerSession.SOURCE_CHOICES`: `"pc_usage"` (tiempo real en
  el PC, vía extensión — paralelo a `SOURCE_APP_USAGE` que es el del móvil).
- Endpoint API: `GET` — tareas activas de subtipo "Curso de Udemy" con su
  `watch_keyword`, para que la extensión sepa qué buscar.
- Endpoint API: `POST` — acumular segundos vistos hoy (crea/actualiza la
  `TimerSession` del día para esa tarea).
- Endpoint API: `POST` — "curso completado al 100%" → marca la tarea
  recurrente como terminada del todo (no solo el día).
- Autenticación de la extensión contra la API (reusar `basic_auth.py` o un
  token simple).

## Fase 3 — Formulario de tarea (depende de: Fase 2)

- Al elegir subtipo "Curso de Udemy" en el formulario de crear/editar tarea,
  mostrar el campo `watch_keyword`.

## Fase 4 — Extensión de Chrome (depende de: Fase 2)

- Scaffold Manifest V3.
- Background/content script: lee el título de la pestaña activa en
  `udemy.com`, compara contra las palabras clave traídas del endpoint de
  Fase 2.
- Detección de foreground real (`chrome.windows`/`chrome.tabs`) +
  `chrome.idle` para pausar si no hay actividad.
- Acumula segundos y los manda periódicamente al endpoint de progreso.
- En la página del curso, detecta el "100% completado" / todas las
  secciones hechas (scrape puntual, tolerante a fallo — si no lo encuentra,
  simplemente no marca nada y se sigue contando tiempo normal) y avisa al
  endpoint correspondiente.
- Login/token de la extensión (popup u opciones).

## Fase 5 — Integración final (depende de: todo lo anterior)

- Confirmar que las `TimerSession` con `source="pc_usage"` entran solas en
  la agregación de la Fase 1, sin tocar esa capa.
- Prueba de extremo a extremo: crear tarea "Curso de Udemy", ver una
  lección, comprobar que sube el contador del día y que al llegar al 100%
  se marca la tarea como hecha.

---

Decisiones ya tomadas (para no repetir la conversación):
- Nada de sumar horas totales/ya vistas a mano — el corte de "curso
  terminado" es el 100% que reporta Udemy, no un umbral de horas (por los
  vídeos vistos a x2 velocidad).
- El objetivo diario sigue siendo tiempo real medido (no afectado por la
  velocidad, es solo "cuánto te has sentado a estudiar hoy").
- Nada de campo de dominio genérico — este subtipo es específico de Udemy.
  YouTube ya tiene su propio mecanismo (`CoursePlaylist`/`CourseModule`).
