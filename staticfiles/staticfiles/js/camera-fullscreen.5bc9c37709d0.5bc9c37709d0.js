/**
 * Pantalla completa para TODAS las cámaras de entreno (.workout__camera) de
 * la web: ejercicio suelto, circuitos/planes y retos. Equivalente web de
 * mobile-app/www/js/camera-fullscreen.js.
 *
 * Se engancha solo: un MutationObserver añade el botón a cualquier
 * .workout__camera que aparezca (las vistas se renderizan desde JS), así no
 * hay que tocar circuit.js / plan-session.js / challenges.js.
 *
 * Entra con la Fullscreen API nativa (oculta también la barra del navegador)
 * y, si el navegador no la soporta sobre un <div> (iPhone/Safari), usa un
 * overlay CSS que cubre toda la ventana. Sale con el botón "Salir" o con Esc.
 * Si la cámara se re-renderiza (cambio automático de ejercicio) el modo
 * pantalla completa se mantiene en la cámara nueva.
 */

const CLS_FULL = "workout__camera--full";
const CLS_BODY = "cam-fullscreen";

const ICON_ENTER =
  '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg>';
const ICON_EXIT =
  '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M18 6L6 18"/></svg>';

let usedNative = false;

function nativeElement() {
  return document.fullscreenElement || document.webkitFullscreenElement || null;
}

function isFull() {
  return document.body.classList.contains(CLS_BODY);
}

function requestNative(el) {
  try {
    const fn = el.requestFullscreen || el.webkitRequestFullscreen;
    if (!fn) return;
    const p = fn.call(el);
    usedNative = true;
    p?.catch?.(() => { usedNative = false; }); // sin API o denegado: queda el overlay CSS
  } catch (_) { usedNative = false; }
}

function exitNative() {
  usedNative = false;
  if (!nativeElement()) return;
  try {
    const fn = document.exitFullscreen || document.webkitExitFullscreen;
    fn?.call(document)?.catch?.(() => {});
  } catch (_) { /* extra visual, nunca debe romper el entreno */ }
}

function enterFull(cam) {
  cam.classList.add(CLS_FULL);
  document.body.classList.add(CLS_BODY);
  requestNative(cam);
}

function exitFull() {
  document.querySelectorAll("." + CLS_FULL).forEach((c) => c.classList.remove(CLS_FULL));
  const was = isFull();
  document.body.classList.remove(CLS_BODY);
  exitNative();
  return was;
}

function decorate() {
  document.querySelectorAll(".workout__camera:not([data-fs])").forEach((cam) => {
    cam.dataset.fs = "1";
    cam.insertAdjacentHTML(
      "beforeend",
      `<button type="button" class="cam-fs-btn cam-fs-btn--enter" aria-label="Pantalla completa" title="Pantalla completa">${ICON_ENTER}</button>` +
      `<button type="button" class="cam-fs-btn cam-fs-btn--exit" aria-label="Salir de pantalla completa" title="Salir de pantalla completa (Esc)">${ICON_EXIT}<span>Salir</span></button>`
    );
    cam.querySelector(".cam-fs-btn--enter").addEventListener("click", () => enterFull(cam));
    cam.querySelector(".cam-fs-btn--exit").addEventListener("click", () => exitFull());
  });
  // La cámara en pantalla completa desapareció: o es un cambio automático
  // de ejercicio (se crea una .workout__camera nueva) -> se mantiene en la
  // nueva; o es un cambio real de vista (sin cámara) -> se sale.
  if (isFull() && !document.querySelector("." + CLS_FULL + ":not([hidden])")) {
    const cam = document.querySelector(".workout__camera");
    if (cam) cam.classList.add(CLS_FULL);
    else exitFull();
  }
}

let scheduled = false;
function schedule() {
  if (scheduled) return;
  scheduled = true;
  requestAnimationFrame(() => { scheduled = false; decorate(); });
}

new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
decorate();

// El usuario sale de la pantalla completa nativa (Esc, gesto del navegador):
// se quita también el estado propio. Si en cambio el navegador la cerró
// porque la cámara se quitó del DOM, no se sale: decorate() la mantiene.
function onNativeChange() {
  if (nativeElement() || !usedNative) return;
  usedNative = false;
  const cam = document.querySelector("." + CLS_FULL);
  if (cam && cam.isConnected) exitFull();
}
document.addEventListener("fullscreenchange", onNativeChange);
document.addEventListener("webkitfullscreenchange", onNativeChange);

// Overlay CSS (sin Fullscreen API): Esc también sale.
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && isFull() && !nativeElement()) exitFull();
});
