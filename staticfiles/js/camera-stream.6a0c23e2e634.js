/**
 * Apertura ÚNICA de la cámara para todos los ejercicios (suelto, plan,
 * calentamiento, retos). Antes cada pantalla pedía la cámara por su cuenta;
 * ahora todas piden exactamente lo mismo, así el encuadre es siempre el mismo.
 *
 * 2026-10-22: 640x360 (16:9, mismo encuadre) y no 1280x720. MediaPipe reescala la imagen a
 * 256x256 por dentro, así que los 720p no daban más precisión, pero en el Redmi A5 (~11 fps)
 * costaban copiar/subir cada frame a la GPU y generar/leer la máscara de persona a 1280x720.
 * Con menos píxeles por frame, detectForVideo tarda menos y se cuentan mejor las reps rápidas.
 * Si a cierta distancia el seguimiento se vuelve inestable, subir CAMERA_WIDTH/HEIGHT
 * (p. ej. 960x540 o 1280x720) aquí, un solo sitio para toda la app.
 * Son valores "ideales" (sin exact/min): si la cámara no da para tanto,
 * degrada a la resolución más cercana en vez de fallar.
 */
export const CAMERA_WIDTH = 640;
export const CAMERA_HEIGHT = 360;
export const CAMERA_CONSTRAINTS = {
  video: { facingMode: "user", width: CAMERA_WIDTH, height: CAMERA_HEIGHT, frameRate: { ideal: 30 } },
  audio: false,
};

export async function openCameraStream() {
  const stream = await navigator.mediaDevices.getUserMedia(CAMERA_CONSTRAINTS);
  // Zoom del hardware al mínimo (el más abierto) si la cámara lo permite,
  // por si el móvil dejó un zoom/auto-encuadre de otra sesión. Es un extra:
  // si no hay soporte o falla, se ignora.
  try {
    const track = stream.getVideoTracks()[0];
    const zoom = track && track.getCapabilities && track.getCapabilities().zoom;
    if (zoom && typeof zoom.min === "number") {
      await track.applyConstraints({ advanced: [{ zoom: zoom.min }] });
    }
  } catch (_) { /* sin zoom de hardware: nada que fijar */ }
  return stream;
}
