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
    content.innerHTML = '<p class="empty">Sin actividad detectada ahora mismo.</p>';
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
    lines.push(`Pestaña activa — URL: ${snap.tab.url ?? "(oculta — falta el permiso de acceso a archivos)"}`);
    lines.push(`Tipo de pestaña detectado: ${{ udemy: "Udemy", pdf: "PDF", otro: "ninguno de los dos" }[snap.tabKind]}`);
    lines.push(`¿Suena audio en la pestaña?: ${snap.tab.audible ? "sí" : "no"}`);
  } else {
    lines.push("Pestaña activa: (no se detecta ninguna)");
  }
  if (snap.noUrlButFileTab) {
    lines.push('Aviso: hay una pestaña sin URL visible — probablemente un archivo local sin el permiso "acceso a URLs de archivo" activado.');
  }
  lines.push(`Estado de inactividad (chrome.idle): ${snap.idleState}`);
  lines.push(`Tareas trackeables en caché: ${snap.tasksCount}${snap.tasksCacheAgeSeconds !== null ? ` (actualizada hace ${snap.tasksCacheAgeSeconds}s)` : " (nunca se ha cargado)"}`);
  if (snap.tasks.length) {
    snap.tasks.forEach((t) => lines.push(`   · [${t.subcategory}] "${t.title}" — palabra clave: "${t.watch_keyword}"`));
  } else {
    lines.push('   (ninguna — revisa que la tarea sea de hoy: Estudio → "Curso de Udemy", o Enfoque → "Lectura", con palabra clave puesta)');
  }
  lines.push(`Coincidencia encontrada ahora: ${snap.match ? `SÍ — "${snap.match.taskTitle}" (por "${snap.match.keyword}")` : "NO"}`);
  lines.push(`Sesión en curso: ${snap.currentSession ? `${snap.currentSession.taskTitle} [${snap.currentSession.subcategory}]` : "ninguna"}`);
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

// ------------------------------------------ aviso de permiso de archivo

const fileAccessWarning = document.getElementById("file-access-warning");

async function refreshFileAccessWarning() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    // Si Chrome no manda "url" para la pestana activa pero SI hay una
    // pestana (activeTab existe), lo mas probable es que sea un file://
    // y falte el permiso "acceso a URLs de archivo" -- sin ese permiso
    // la extension ni siquiera ve la URL, asi que no hay forma de estar
    // 100% seguros, pero es la senal disponible mas fiable.
    fileAccessWarning.hidden = !(tab && !tab.url);
  } catch {
    fileAccessWarning.hidden = true;
  }
}

document.getElementById("open-settings").addEventListener("click", () => {
  chrome.tabs.create({ url: `chrome://extensions/?id=${chrome.runtime.id}` });
});

render();
refreshFileAccessWarning();
setInterval(render, 1000);
setInterval(refreshDebug, 1000);
setInterval(refreshFileAccessWarning, 3000);
