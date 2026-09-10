# Libreta — Tiempo en Udemy y Lectura (extensión de Chrome)

Cuenta el tiempo real que pasas con una pestaña "trackeable" en primer
plano (ventana con foco, sin inactividad), y manda esa sesión a
`/api/tasks/<uuid>/focus/` — igual que ya hace el plugin de lectura de
la app móvil, con `source=pc_usage` en vez de `app_usage`. Hay dos
tipos de pestaña trackeable, cada uno emparejado con un tipo de tarea:

- **Udemy** — tarea de categoría Estudio, subtipo "Curso de Udemy".
  Cuenta tiempo mientras la pestaña de udemy.com está sonando
  (chrome.tabs.audible) — estar en el Q&A, las reseñas o el temario
  del curso sin el vídeo reproduciéndose NO cuenta, solo se trackea
  mientras se oye la clase. Hay dos formas de tener una tarea de
  Udemy: **con palabra clave** (viene de un Plan) — cuenta solo ESE
  curso, y cada minuto comprueba si Udemy lo reporta al 100% para
  cerrar la tarea entera (no solo el día) en cuanto se termina; **sin
  palabra clave** (tarea suelta / freestyle) — hábito genérico, cuenta
  el tiempo en CUALQUIER pestaña de udemy.com, sin curso concreto ni
  cierre automático. Si las dos existen a la vez, la palabra clave
  específica siempre gana sobre el hábito genérico, para que nunca se
  pisen ni sumen el mismo rato dos veces.
- **Lectura de un PDF** — tarea de categoría Enfoque, subtipo
  "Lectura". Si el título de la pestaña activa es un `.pdf` (local o
  de una web) y coincide con la palabra clave de la tarea, cuenta
  tiempo igual que Udemy. Aquí no hay detección de "página final" —
  el visor de PDF nativo de Chrome no es inspeccionable desde una
  extensión — así que la tarea se completa sola cuando llegas al
  objetivo en minutos del día (si la tarea tiene uno puesto), igual
  que ya hace cualquier tarea de Enfoque con temporizador.

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
2. Crea una tarea de categoría "Enfoque" → subtipo "Lectura", con una
   palabra clave que aparezca en el nombre del archivo o el título de
   la pestaña (ej. "clean-code" para `clean-code.pdf`).
3. Abre el PDF en una pestaña de Chrome (arrastra el archivo a una
   ventana de Chrome, o pégalo en la barra de direcciones) y déjalo en
   primer plano mientras lees. También funciona con un PDF alojado en
   una web (no hace falta que sea un archivo local).

### En ambos casos

- Si cambias de pestaña, minimizas la ventana, o pasas más de un
  minuto sin tocar ratón/teclado, esa sesión se cierra y se manda; al
  volver, empieza una sesión nueva. (Para Udemy, el ratón/teclado no
  cuenta si la pestaña está sonando — se asume que sigues viendo el
  vídeo. Para un PDF no hay audio, así que ahí sí hace falta seguir
  tocando algo de vez en cuando.)
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
- Las sesiones de menos de 1 minuto no se mandan.
- La lista de tareas "Curso de Udemy" se cachea 2 minutos — crear o
  editar una tarea puede tardar hasta ese rato en reflejarse aquí.
