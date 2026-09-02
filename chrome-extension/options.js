/**
 * Ajustes de la extensión: URL de la Libreta + usuario/contraseña del
 * candado (BasicAuthMiddleware) — mismo criterio que la app móvil (ver
 * mobile-app/www/js/api.js), guardado en chrome.storage.local en vez de
 * localStorage porque aquí no hay una página persistente con la que
 * compartirlo.
 */

const baseUrlInput = document.getElementById("baseUrl");
const userInput = document.getElementById("user");
const passwordInput = document.getElementById("password");
const statusEl = document.getElementById("status");

function showStatus(text, kind) {
  statusEl.textContent = text;
  statusEl.className = kind || "";
}

function originPatternFor(rawUrl) {
  try {
    const u = new URL(rawUrl);
    return `${u.protocol}//${u.hostname}/*`;
  } catch {
    return null;
  }
}

async function load() {
  const { config } = await chrome.storage.local.get("config");
  if (config) {
    baseUrlInput.value = config.baseUrl || "";
    userInput.value = config.user || "";
    passwordInput.value = config.password || "";
  }
}

async function save() {
  const baseUrl = baseUrlInput.value.trim().replace(/\/+$/, "");
  const user = userInput.value.trim();
  const password = passwordInput.value;

  if (!baseUrl || !user || !password) {
    showStatus("Rellena los tres campos.", "error");
    return;
  }

  const pattern = originPatternFor(baseUrl);
  if (!pattern) {
    showStatus("Esa URL no parece válida — incluye https:// al principio.", "error");
    return;
  }

  // El permiso de host se pide aquí, con el gesto del usuario al pulsar
  // "Guardar" — Chrome exige que permissions.request() venga de una
  // acción directa de la persona, no se puede pedir solo en segundo plano.
  let granted = false;
  try {
    granted = await chrome.permissions.request({ origins: [pattern] });
  } catch (err) {
    showStatus("No se pudo pedir permiso para ese dominio: " + err.message, "error");
    return;
  }
  if (!granted) {
    showStatus("Sin ese permiso la extensión no puede hablar con tu servidor.", "error");
    return;
  }

  await chrome.storage.local.set({ config: { baseUrl, user, password } });
  // Cambió el servidor/credenciales: la caché de tareas de antes ya no vale.
  await chrome.storage.local.remove(["tasksCache", "tasksCacheAt", "pendingUploads"]);
  showStatus("Guardado.", "ok");
}

async function test() {
  const { config } = await chrome.storage.local.get("config");
  if (!config || !config.baseUrl) {
    showStatus("Guarda los ajustes primero.", "error");
    return;
  }
  showStatus("Probando…", "");
  try {
    const resp = await fetch(`${config.baseUrl}/api/meta/`, {
      headers: { Authorization: "Basic " + btoa(`${config.user}:${config.password}`) },
    });
    if (resp.status === 401) {
      showStatus("Usuario o contraseña incorrectos.", "error");
      return;
    }
    if (!resp.ok) {
      showStatus(`El servidor respondió ${resp.status}.`, "error");
      return;
    }
    const data = await resp.json();
    const cursos = (data.study_subcategories || []).some((c) => c.value === "udemy");
    showStatus(
      cursos
        ? "Conectado ✓ — tu Libreta ya sabe de \"Curso de Udemy\"."
        : "Conectado ✓, pero tu Libreta todavía no tiene el subtipo \"Curso de Udemy\" (¿falta desplegar?).",
      "ok",
    );
  } catch (err) {
    showStatus("No se pudo conectar: " + err.message, "error");
  }
}

document.getElementById("save").addEventListener("click", save);
document.getElementById("test").addEventListener("click", test);
load();
