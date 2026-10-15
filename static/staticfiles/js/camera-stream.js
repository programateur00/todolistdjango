/**
 * Apertura ÚNICA de la cámara para todos los ejercicios (suelto, plan,
 * calentamiento, retos). Antes cada pantalla pedía la cámara por su cuenta;
 * ahora todas piden exactamente lo mismo, así el encuadre es siempre el mismo.
 *
 * 1280x720 y no 640x480: con poca resolución, a cierta distancia el cuerpo
 * ocupa pocos píxeles y el seguimiento de MediaPipe se vuelve inestable.
 * Son valores "ideales" (sin exact/min): si la cámara no da para tanto,
 * degrada a la resolución más cercana en vez de fallar.
 */
export const CAMERA_CONSTRAINTS = {
  video: { facingMode: "user", width: 1280, height: 720 },
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
