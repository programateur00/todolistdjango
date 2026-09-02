# Libreta — Tiempo en Udemy (extensión de Chrome)

Cuenta el tiempo real que pasas con una pestaña de Udemy en primer plano
(ventana con foco, sin inactividad) cuando su título coincide con la
palabra clave de una tarea "Curso de Udemy" pendiente en tu Libreta, y
manda esa sesión a `/api/tasks/<uuid>/focus/` — igual que ya hace el
plugin de lectura de la app móvil, con `source=pc_usage` en vez de
`app_usage`. Además comprueba cada minuto si Udemy reporta el curso al
100% y, si es así, cierra la tarea entera (no solo el día) sin esperar a
que llegues a un número de horas.

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

1. Crea una tarea de categoría "Estudio" → subtipo "Curso de Udemy",
   con una palabra clave que aparezca en el título del curso en Udemy
   (ej. "Linux" para un curso que se llame "Curso completo de Linux").
2. Ponte a ver el curso en Chrome, con esa pestaña en primer plano.
   No hace falta hacer nada más — la extensión cuenta sola.
3. Si cambias de pestaña, minimizas la ventana, o pasas más de un
   minuto sin tocar ratón/teclado, esa sesión se cierra y se manda; al
   volver, empieza una sesión nueva.
4. El icono de la extensión (clic izquierdo) enseña qué se está
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
