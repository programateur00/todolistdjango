/* ============================================================
   ÚNICO fichero que hay que tocar para cambiar de dónde sale
   MediaPipe (versión vendorizada, o volver a un CDN externo si algún
   día hiciera falta) — workout.js y circuit.js importan de aquí,
   nunca definen ni repiten esto por su cuenta. Ver
   static/vendor/mediapipe/README.md para cómo revendorizar una
   versión nueva paso a paso.
   ============================================================ */

// Qué versión hay vendorizada en static/vendor/mediapipe/ ahora mismo
// — esto es solo informativo (documenta qué se bajó), NO se usa para
// construir ninguna URL (eso lo hacen las rutas de abajo, relativas a
// este propio fichero vía import.meta.url). Nunca "latest": para subir
// de verdad hay que revendorizar los ficheros a mano primero (ver el
// README) y solo entonces actualizar este número para que coincida.
export const MEDIAPIPE_VERSION = "0.10.14";

// Todo servido en local (vendorizado) — antes la librería y el modelo
// se pedían a cdn.jsdelivr.net y storage.googleapis.com en cada
// sesión de entreno, lo que nos dejaba a merced de que esos dominios
// caigan, los bloqueen en algún país, o que Google reorganice dónde
// cuelga sus modelos (ya lo ha hecho antes). Resuelto con
// import.meta.url (no con STATIC_URL a pelo) para que funcione igual
// da igual desde qué URL sirva Django este fichero.
const MEDIAPIPE_VENDOR_BASE = new URL("../vendor/mediapipe/", import.meta.url);
export const MEDIAPIPE_BUNDLE_URL = new URL("vision_bundle.mjs", MEDIAPIPE_VENDOR_BASE).href;
export const MEDIAPIPE_WASM_BASE_URL = new URL("wasm/", MEDIAPIPE_VENDOR_BASE).href;
// pose_landmarker_FULL, no lite: el modelo lite fallaba dominadas a
// cierta distancia (usuario real, feedback en sesión) — con menos
// precisión de landmark, el ruido de seguimiento se come el margen de
// los umbrales (HANG_MARGIN_FACTOR, MOVE_FACTOR...) en cuanto te
// alejas y el ancho de hombros en píxeles se hace pequeño. "full" es
// más preciso a costa de algo más de CPU; con GPU delegate (ver
// workout.js/circuit.js) debería ir sobrado en cualquier portátil o
// móvil de los últimos años.
//
// OJO: a diferencia de pose_landmarker_lite.task (sí vendorizado aquí
// en su día), pose_landmarker_full.task TODAVÍA NO está en
// models/ — el entorno donde se hizo este cambio no tiene salida a
// storage.googleapis.com (mismo motivo que ya documentaba el README
// para el lite). Hay que bajarlo a mano UNA vez desde un ordenador
// normal y colocarlo en esta misma carpeta antes de que esto funcione
// — ver README.md, sección "Cómo actualizar de versión". Hasta
// entonces, esta URL apunta a un fichero que no existe y la carga del
// modelo fallará (se verá como "No se pudo cargar el modelo de
// seguimiento" en pantalla).
export const MODEL_URL = new URL("models/pose_landmarker_full.task", MEDIAPIPE_VENDOR_BASE).href;
