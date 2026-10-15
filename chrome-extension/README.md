# Libreta — Tiempo en Udemy y Lectura (extensión de Chrome)

Cuenta el tiempo real que pasas con una pestaña "trackeable" en primer
plano (ventana con foco, sin inactividad), y manda esa sesión a
`/api/tasks/<uuid>/focus/` — igual que ya hace el plugin de lectura de
la app móvil, con `source=pc_usage` en vez de `app_usage`. Hay dos
tipos de pestaña trackeable, cada uno emparejado con un tipo de tarea:

- **Udemy** — tarea de categoría Estudio, subtipo "Curso de Udemy".
  Hay dos modos de contar el tiempo, elegidos por curso (ver abajo) y que
  nunca se mezclan. Por defecto es **"por vídeos vistos"**: cuenta SOLO
  mientras el vídeo suena (chrome.tabs.audible) o se está reproduciendo
  (un `<video>` de la lección sin pausa, también con el sonido
  silenciado). Estar en el Q&A, las reseñas o el temario, o tener el
  vídeo en pausa, NO cuenta aunque muevas el ratón; se tolera una pausa
  de hasta 60 s (`VIDEO_PAUSE_GRACE_SECONDS`, para apuntar algo) y pasado
  ese tiempo la cuenta para. Hay dos formas de tener una tarea
  de Udemy: **con palabra clave** (viene de un Plan) — cuenta solo ESE
  curso, y cada minuto comprueba si Udemy lo reporta al 100% para
  cerrar la tarea entera (no solo el día) en cuanto se termina; **sin
  palabra clave** (tarea suelta / freestyle) — hábito genérico, cuenta
  el tiempo en CUALQUIER pestaña de udemy.com, sin curso concreto ni
  cierre automático. Si las dos existen a la vez, la palabra clave
  específica siempre gana sobre el hábito genérico, para que nunca se
  pisen ni sumen el mismo rato dos veces.

  Un curso con **palabra clave** puede además ponerse **"por tiempo en la
  página"** (Task.watch_requires_audio=False, selector al editar el
  objetivo del Plan — pensado para cursos de ejercicios, sin apenas
  vídeo): ahí no se mira el sonido ni el vídeo, solo que la pestaña esté
  en primer plano y que hayas tocado ratón/teclado en los últimos 5
  minutos (chrome.idle), igual que Lectura de PDF más abajo. Cuando te
  vas, esos 5 minutos de inactividad que hicieron falta para detectarlo
  NO se suman.
- **Clases de Ilerna (Zoom)** — tarea de categoría Estudio, subtipo
  "Clases de Ilerna (Zoom)" (o plan de Estudio → "Clases de Ilerna").
  Cuenta tiempo mientras tienes una grabación de `ilernaonline.zoom.us`
  en primer plano y suena (o tocas ratón/teclado; para tras 5 min
  inactivo Y en silencio). Sin curso que terminar: la tarea del día se da
  por cumplida al llegar a los minutos objetivo, y el plan se cierra por
  semanas como cualquier hábito de Estudio. La palabra clave (asignatura)
  es opcional — si la pones, tiene que aparecer en el título de la
  pestaña de Zoom; si no, cuenta cualquier clase de Ilerna. Para ver qué
  título tiene la pestaña, abre el popup de la extensión (panel de
  diagnóstico).
- **Lectura de un PDF (modo Freestyle)** — tarea de categoría
  "Lectura". Si el título de la pestaña activa es un `.pdf` (local o
  de una web) y coincide con la palabra clave de la tarea, cuenta
  tiempo igual que Udemy. Aquí no hay detección de "página final" —
  el visor de PDF nativo de Chrome no es inspeccionable desde una
  extensión — así que la tarea se completa sola cuando llegas al
  objetivo en minutos del día (si la tarea tiene uno puesto), igual
  que ya hace cualquier tarea de Lectura con temporizador. Esto es
  distinto del "Plan de lectura" (visor propio pdf.js con página
  exacta, desde la pestaña Planes) — el Freestyle no sabe en qué
  página vas, solo cuenta tiempo.

No está pensada para publicarse en la Chrome Web Store — es de uso
personal, se carga "sin empaquetar".

## Instalar

1. Abre `chrome://extensions` en Chrome.
2. Activa "Modo de desarrollador" (esquina superior derecha).
3. "Cargar descomprimida" → elige esta carpeta (`chrome-extension/`).
4. Haz clic en el icono de la extensión → "Ajustes" (o clic derecho →
   Opciones) y rellena:
   - **URL de tu Libreta**: la misma que usas en el navegador, sin barra
     final (ej. `https://tuusuario.pythonanywhere.com`).
   - **Usuario/Contraseña**: las de `BASIC_AUTH_USER`/`BASIC_AUTH_PASSWORD`
     — las mismas que ya usas en la app móvil.
5. Al pulsar "Guardar", Chrome te pedirá permiso para que la extensión
   hable con ese dominio — acéptalo, si no la extensión no podrá mandar
   nada. "Probar conexión" comprueba que las credenciales son correctas.

## Requisitos en el backend

Necesitas la Fase 2 (backend del tracking de Udemy) desplegada: subtipo
"Curso de Udemy" en Estudio, `TimerSession.SOURCE_PC_USAGE`, y las
acciones `focus_save`/`course-complete` en `tasks/api.py` — todo ya en
`main` de este repo. Sin eso desplegado, "Probar conexión" avisa de que
falta el subtipo.

## Uso

### Cursos de Udemy

1. Crea una tarea de categoría "Estudio" → subtipo "Curso de Udemy",
   con una palabra clave que aparezca en el título del curso en Udemy
   (ej. "Linux" para un curso que se llame "Curso completo de Linux").
2. Ponte a ver el curso en Chrome, con esa pestaña en primer plano.
   No hace falta hacer nada más — la extensión cuenta sola.

### Lectura de un PDF (libro, apuntes...)

1. **Solo la primera vez**: abre `chrome://extensions`, busca esta
   extensión, entra en "Detalles" y activa "Permitir acceso a las
   URLs de archivo". Sin esto Chrome no deja que ninguna extensión
   sepa qué archivo local tienes abierto — es un permiso que hay que
   dar a mano, no hay forma de activarlo desde el código. Si se te
   olvida, el propio icono de la extensión te avisa con un botón que
   te lleva directo a esa pantalla.
2. Crea una tarea de categoría "Lectura" (modo Freestyle, no Plan de
   lectura), con una palabra clave que aparezca en el nombre del
   archivo o el título de la pestaña (ej. "clean-code" para
   `clean-code.pdf`).
3. Abre el PDF en una pestaña de Chrome (arrastra el archivo a una
   ventana de Chrome, o pégalo en la barra de direcciones) y déjalo en
   primer plano mientras lees. También funciona con un PDF alojado en
   una web (no hace falta que sea un archivo local).

### En ambos casos

- Si cambias de pestaña, minimizas la ventana o dejas de cumplir la
  condición de tu modo, esa sesión se cierra y se manda; al volver,
  empieza una sesión nueva. Resumen de cada modo:
  - **Udemy "por vídeos vistos"** (por defecto): cuenta con el vídeo
    sonando o reproduciéndose, más una pausa de hasta 60 s. Con el
    vídeo parado más tiempo, para — aunque muevas el ratón.
  - **Udemy "por tiempo en la página"** y **PDF**: cuenta con la pestaña
    en primer plano y actividad de ratón/teclado en los últimos 5
    minutos; si te vas, la sesión acaba en el instante en que dejaste de
    tocar (no se suman los 5 minutos de espera).
  - **Clases de Ilerna (Zoom)**: cuenta si suena O hay actividad de
    ratón/teclado; para al estar en silencio Y 5 minutos inactivo.
- Los segundos sueltos de cada trozo no se pierden: lo que sobra (o
  falta) para el minuto entero se arrastra al siguiente trozo de esa
  tarea el mismo día (`takeWholeMinutes`), así que salir y volver varias
  veces no hace perder minutos.
- El icono de la extensión (clic izquierdo) enseña qué se está
  contando ahora mismo, si algo.

## Cómo se detecta el "100% completado"

Es una comprobación tolerante a fallo, no una fuente de verdad exacta:
busca el texto "100%" cerca de "completado"/"finalizado" en la página, y
mira si hay alguna barra de progreso (`role="progressbar"` o
`<progress>`) con valor 100. Si Udemy cambia su maquetación y deja de
detectarlo, simplemente no se marca nada — la tarea sigue pendiente como
si esto no existiera, no rompe nada.

## Notas de diseño

- Si mandar una sesión falla (sin red, servidor caído), se guarda en
  `chrome.storage.local` y se reintenta cada 5 minutos — no se pierde
  tiempo trackeado por un corte puntual.
- Para un curso de Udemy (con o sin palabra clave) hay que poner siempre
  los minutos al día: sin ellos la primera sesión de 1 minuto daría el
  día por cumplido.
- Las sesiones de menos de 1 minuto no se mandan sueltas: los segundos
  sobrantes se acumulan al siguiente trozo del mismo día.
- Los reintentos nunca duplican un envío (hay un cerrojo) y un envío que
  el servidor rechaza con un error 4xx (p. ej. tarea borrada) se descarta
  en vez de reintentarse eternamente; el resto caduca a los 14 días.
- La lista de tareas "Curso de Udemy" se cachea 2 minutos — crear o
  editar una tarea puede tardar hasta ese rato en reflejarse aquí.
