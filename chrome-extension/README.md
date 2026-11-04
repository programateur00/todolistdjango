# Libreta — Tiempo en webs (extensión de Chrome)

Cuenta el tiempo real que pasas con una pestaña "trackeable" en primer
plano (ventana con foco, sin inactividad), y manda esa sesión a
`/api/tasks/<uuid>/focus/` — igual que ya hace el plugin de lectura de
la app móvil, con `source=pc_usage` en vez de `app_usage`. Hay tres
tipos de pestaña trackeable, cada uno emparejado con un tipo de tarea:

- **Udemy** — tarea de categoría Estudio, subtipo "Curso de Udemy".
  Solo cuenta dentro del **reproductor del curso** (URL con `/learn/`): la
  portada de Udemy, el buscador, la ficha del curso o el carrito no suman
  nada aunque estén en primer plano y muevas el ratón.
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
- **Tiempo en una web** — tarea de categoría Estudio, subtipo "Tiempo en
  una web" (o plan de Estudio → "Tiempo en una web"). Sirve para CUALQUIER
  web que elijas (Ilerna, Hyperskill, un campus, la documentación de lo que
  estés aprendiendo…) y sustituye a las antiguas "Clases de Ilerna": las
  que ya tenías se convirtieron solas en una web con `ilernaonline.zoom.us`
  y el sonido contando, como funcionaban. Se configura con:
  - **Dirección de la web (un trozo)**: la pestaña cuenta si su URL
    CONTIENE ese texto, sin distinguir mayúsculas y sin importar https, www
    o la subpágina. `hyperskill.org` vale para todo Hyperskill;
    `ilernaonline.zoom.us/rec` solo para las grabaciones. Puedes poner
    varios separados por comas (vale cualquiera). Los trozos de menos de 3
    letras se ignoran. Al guardar se limpia lo que pegues de más
    (`https://www.hyperskill.org/learn` → `hyperskill.org/learn`).
  - **Palabra en el título (opcional)**: además tiene que salir en el
    título de la pestaña (p. ej. una asignatura). Si encajan varias
    tareas con la misma pestaña, gana la que pide palabra del título y,
    luego, la de trozo de URL más largo.
  - **Condición anti-AFK** (ver abajo): minutos sin tocar ratón/teclado a
    partir de los cuales deja de contar (el número que quieras, de 1 a 30; por defecto 3),
    y si el sonido de la pestaña también cuenta como "estoy aquí".
  Sin curso que terminar: la tarea del día se da por cumplida al llegar a
  los minutos objetivo (obligatorios), y el plan se cierra por semanas como
  cualquier hábito de Estudio. Para ver por qué una pestaña cuenta o no,
  abre el popup de la extensión (panel de diagnóstico: dice si la web
  encaja y si ahora mismo cuenta).
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

Para "Tiempo en una web" hace falta además la migración `0128_tiempo_en_una_web`
(campos `watch_url`, `watch_idle_seconds`, `watch_audio_counts`; convierte
también las clases de Ilerna que ya tenías). Después de desplegar: ejecuta
`python manage.py migrate` y, en `chrome://extensions`, pulsa el botón de
recargar de esta extensión (cambió el manifest a la 1.3.0).

## Uso

### Cursos de Udemy

1. Crea una tarea de categoría "Estudio" → subtipo "Curso de Udemy",
   con una palabra clave que aparezca en el título del curso en Udemy
   (ej. "Linux" para un curso que se llame "Curso completo de Linux").
2. Ponte a ver el curso en Chrome, con esa pestaña en primer plano.
   No hace falta hacer nada más — la extensión cuenta sola.

### Tiempo en una web (Ilerna, Hyperskill, la que quieras)

1. Crea una tarea de categoría "Estudio" → subtipo "Tiempo en una web" (o
   un plan de Estudio → "Tiempo en una web") y rellena:
   - la dirección: un trozo que tenga la URL (`hyperskill.org`),
   - los minutos al día (obligatorios),
   - opcional: una palabra del título de la pestaña,
   - tras cuántos minutos sin tocar ratón/teclado deja de contar,
   - opcional: si el sonido de la pestaña también cuenta.
2. Ponte con la web en Chrome, con esa pestaña en primer plano. La
   extensión cuenta sola mientras estés usándola.
3. Si te vas con el ordenador encendido: pasado el tiempo que elegiste sin
   tocar nada (o al bloquear la pantalla) deja de contar, y esos minutos de
   espera no se suman. Para saber por qué una pestaña cuenta o no, abre el
   popup → "Diagnóstico".

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

### En todos los casos

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
  - **Tiempo en una web**: cuenta SOLO con actividad de ratón/teclado en
    los últimos N minutos (el que elijas por tarea, de 1 a 30; 3 por defecto). Con la
    pantalla bloqueada nunca cuenta. Si activas "contar también si la
    pestaña suena", suena = presente (para clases grabadas que ves sin
    tocar nada) — a cambio, irte con el sonido puesto sigue contando; con
    la pantalla bloqueada tampoco. Sea cual sea el caso, cuando te vas, el
    rato de espera hasta detectarlo NO se suma.
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
