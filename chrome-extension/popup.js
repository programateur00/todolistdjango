/** Enseña la sesión que la extensión está contando ahora mismo, si hay alguna. */

const content = document.getElementById("content");

function fmt(totalSeconds) {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

async function render() {
  const { config } = await chrome.storage.local.get("config");
  if (!config || !config.baseUrl) {
    content.innerHTML = '<p class="empty">Sin configurar todavía — abre Ajustes.</p>';
    return;
  }

  const { current } = await chrome.storage.session.get("current");
  if (!current) {
    content.innerHTML = '<p class="empty">Sin actividad de Udemy detectada ahora mismo.</p>';
    return;
  }

  const elapsed = Math.floor((Date.now() - current.startedAt) / 1000);
  content.innerHTML = `
    <p class="task-title">${current.task.title}</p>
    <p class="elapsed">${fmt(elapsed)}</p>
  `;
}

document.getElementById("open-options").addEventListener("click", (e) => {
  e.preventDefault();
  chrome.runtime.openOptionsPage();
});

// -------------------------------------------------------- diagnóstico

const debugEl = document.getElementById("debug");
const toggleDebug = document.getElementById("toggle-debug");
let debugVisible = false;

function renderDebug(snap) {
  if (!snap) {
    debugEl.textContent = "No se pudo consultar el estado (¿el service worker está activo?).";
    return;
  }
  const lines = [];
  lines.push(`Configurada: ${snap.configured ? "sí" : "NO — falta URL/usuario/contraseña"} ${snap.baseUrl ? `(${snap.baseUrl})` : ""}`);
  lines.push(`Ventana del navegador con foco: ${snap.windowFocused ? "sí" : "NO"}`);
  if (snap.tab) {
    lines.push(`Pestaña activa — título: "${snap.tab.title}"`);
    lines.push(`Pestaña activa — URL: ${snap.tab.url}`);
    lines.push(`¿Reconocida como Udemy?: ${snap.isUdemyTab ? "sí" : "NO"}`);
    lines.push(`¿Suena audio en la pestaña?: ${snap.tab.audible ? "sí" : "no"}`);
  } else {
    lines.push("Pestaña activa: (no se detecta ninguna)");
  }
  lines.push(`Estado de inactividad (chrome.idle): ${snap.idleState}`);
  lines.push(`Tareas de Udemy en caché: ${snap.tasksCount}${snap.tasksCacheAgeSeconds !== null ? ` (actualizada hace ${snap.tasksCacheAgeSeconds}s)` : " (nunca se ha cargado)"}`);
  if (snap.tasks.length) {
    snap.tasks.forEach((t) => lines.push(`   · "${t.title}" — palabra clave: "${t.watch_keyword}"`));
  } else {
    lines.push("   (ninguna — revisa que la tarea sea de hoy, categoría Estudio, subtipo Curso de Udemy, con palabra clave puesta)");
  }
  lines.push(`Coincidencia encontrada ahora: ${snap.match ? `SÍ — "${snap.match.taskTitle}" (por "${snap.match.keyword}")` : "NO"}`);
  lines.push(`Sesión en curso: ${snap.currentSession ? snap.currentSession.taskTitle : "ninguna"}`);
  debugEl.textContent = lines.join("\n");
}

async function refreshDebug() {
  if (!debugVisible) return;
  const snap = await chrome.runtime.sendMessage({ type: "debug-snapshot" }).catch(() => null);
  renderDebug(snap);
}

toggleDebug.addEventListener("click", (e) => {
  e.preventDefault();
  debugVisible = !debugVisible;
  debugEl.hidden = !debugVisible;
  if (debugVisible) refreshDebug();
});

render();
setInterval(render, 1000);
setInterval(refreshDebug, 1000);
