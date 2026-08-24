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
export const MODEL_URL = new URL("models/pose_landmarker_lite.task", MEDIAPIPE_VENDOR_BASE).href;
