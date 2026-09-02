/**
 * Service worker de la extensión "Libreta — Tiempo en Udemy".
 *
 * Qué hace, en corto: mientras una pestaña de udemy.com está en primer
 * plano (ventana con foco, pestaña activa, sin inactividad) y su título
 * contiene la palabra clave de alguna tarea "Curso de Udemy" pendiente,
 * cuenta el tiempo. En cuanto deja de cumplirse cualquiera de esas
 * condiciones, manda UNA sesión con el total a /api/tasks/<uuid>/focus/
 * — el mismo endpoint y la misma forma que ya usa el plugin de lectura
 * del móvil (ver mobile-app/www/js/focus-view.js), con
 * source="pc_usage" en vez de "app_usage".
 *
 * No hay tramos "en pausa": si sales de la pestaña o del curso, esa
 * sesión se cierra y se manda tal cual — volver más tarde empieza una
 * sesión nueva. Es literalmente "cuenta segundos con la pestaña en
 * primer plano", sin acumular huecos.
 *
 * Además, mientras hay una sesión en marcha, cada minuto comprueba si
 * Udemy ya reporta el curso al 100% — si lo detecta, avisa a
 * /api/tasks/<uuid>/mark/course-complete/, que cierra la serie entera
 * (ver Task.finish_recurring_series en el backend). Es una detección
 * tolerante a fallo: si no encuentra el indicador de progreso, no pasa
 * nada, simplemente no marca nada y se sigue contando tiempo normal.
 */

const TASKS_CACHE_TTL_MS = 2 * 60 * 1000;     // 2 min
const IDLE_DETECTION_SECONDS = 60;             // 1 min sin tocar ratón/teclado = inactivo
const MIN_SESSION_MINUTES_TO_SEND = 1;         // sesiones de <1 min no se mandan, no aportan nada
const HEARTBEAT_ALARM = "libreta-udemy-heartbeat";
const RETRY_ALARM = "libreta-udemy-retry-uploads";

// ------------------------------------------------------------- config

async function getConfig() {
  const { config } = await chrome.storage.local.get("config");
  return config || {};
}

function isConfigured(cfg) {
  return Boolean(cfg && cfg.baseUrl && cfg.user && cfg.password);
}

function authHeader(cfg) {
  return "Basic " + btoa(`${cfg.user}:${cfg.password}`);
}

function apiUrl(cfg, path) {
  const base = (cfg.baseUrl || "").replace(/\/+$/, "");
  return `${base}/api${path}`;
}

// ------------------------------------------------------- tareas (caché)

async function fetchTasksFromServer(cfg) {
  const resp = await fetch(apiUrl(cfg, "/tasks/?category=study"), {
    headers: { Authorization: authHeader(cfg) },
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const data = await resp.json();
  const pending = Array.isArray(data.pending) ? data.pending : [];
  return pending.filter((t) => t.subcategory === "udemy" && (t.watch_keyword || "").trim());
}

async function refreshTasksCache() {
  const cfg = await getConfig();
  if (!isConfigured(cfg)) return;
  try {
    const tasks = await fetchTasksFromServer(cfg);
    await chrome.storage.local.set({ tasksCache: tasks, tasksCacheAt: Date.now() });
  } catch (err) {
    // Sin red o servidor caído: nos quedamos con la caché que hubiera.
    console.warn("[Libreta] no se pudo refrescar la lista de tareas:", err);
  }
}

async function getCachedTasks() {
  const { tasksCache, tasksCacheAt } = await chrome.storage.local.get(["tasksCache", "tasksCacheAt"]);
  const stale = !tasksCacheAt || Date.now() - tasksCacheAt > TASKS_CACHE_TTL_MS;
  if (stale) {
    // No bloquea: se refresca para la próxima vez, esta vez se usa lo que haya.
    refreshTasksCache();
  }
  return Array.isArray(tasksCache) ? tasksCache : [];
}

// --------------------------------------------------- sesión en curso

async function getCurrentSession() {
  const { current } = await chrome.storage.session.get("current");
  return current || null;
}

async function setCurrentSession(session) {
  if (session) await chrome.storage.session.set({ current: session });
  else await chrome.storage.session.remove("current");
}

function matchTask(tasks, tabTitle) {
  const title = (tabTitle || "").toLowerCase();
  if (!title) return null;
  let best = null;
  for (const t of tasks) {
    const kw = (t.watch_keyword || "").trim().toLowerCase();
    if (kw && title.includes(kw)) {
      if (!best || kw.length > best.keyword.length) best = { task: t, keyword: kw };
    }
  }
  return best;
}

function isUdemyUrl(rawUrl) {
  try {
    const u = new URL(rawUrl);
    return /(^|\.)udemy\.com$/i.test(u.hostname);
  } catch {
    return false;
  }
}

/** Tarea+pestaña que tocaría estar contando AHORA MISMO, o null si nada aplica. */
async function getActiveMatch() {
  try {
    const idleState = await chrome.idle.queryState(IDLE_DETECTION_SECONDS);
    if (idleState !== "active") return null;

    const win = await chrome.windows.getLastFocused({ populate: false }).catch(() => null);
    if (!win || !win.focused) return null;

    const tabs = await chrome.tabs.query({ active: true, windowId: win.id });
    const tab = tabs[0];
    if (!tab || !tab.url || !isUdemyUrl(tab.url)) return null;

    const tasks = await getCachedTasks();
    const found = matchTask(tasks, tab.title);
    if (!found) return null;

    return { task: found.task, tabId: tab.id };
  } catch (err) {
    console.warn("[Libreta] getActiveMatch falló:", err);
    return null;
  }
}

// --------------------------------------------------------- subir sesión

async function queueFailedUpload(taskUuid, minutes) {
  const { pendingUploads } = await chrome.storage.local.get("pendingUploads");
  const list = Array.isArray(pendingUploads) ? pendingUploads : [];
  list.push({ taskUuid, minutes, queuedAt: Date.now() });
  await chrome.storage.local.set({ pendingUploads: list });
}

async function postFocusSession(cfg, taskUuid, minutes) {
  const resp = await fetch(apiUrl(cfg, `/tasks/${taskUuid}/focus/`), {
    method: "POST",
    headers: { Authorization: authHeader(cfg), "Content-Type": "application/json" },
    body: JSON.stringify({ minutes, source: "pc_usage", app_package: "udemy.com" }),
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

async function sendSessionMinutes(taskUuid, minutes) {
  const cfg = await getConfig();
  if (!isConfigured(cfg)) return;
  try {
    await postFocusSession(cfg, taskUuid, minutes);
    // La lista de tareas pudo cambiar (objetivo cumplido = tarea ya no
    // pendiente hoy) — se refresca para que la próxima comprobación no
    // la siga ofreciendo como candidata.
    refreshTasksCache();
  } catch (err) {
    console.warn("[Libreta] no se pudo mandar la sesión, se guarda para reintentar:", err);
    await queueFailedUpload(taskUuid, minutes);
  }
}

async function flushPendingUploads() {
  const cfg = await getConfig();
  if (!isConfigured(cfg)) return;
  const { pendingUploads } = await chrome.storage.local.get("pendingUploads");
  const list = Array.isArray(pendingUploads) ? pendingUploads : [];
  if (!list.length) return;

  const stillFailing = [];
  for (const item of list) {
    try {
      await postFocusSession(cfg, item.taskUuid, item.minutes);
    } catch {
      stillFailing.push(item);
    }
  }
  await chrome.storage.local.set({ pendingUploads: stillFailing });
  if (stillFailing.length < list.length) refreshTasksCache();
}

// ----------------------------------------------- detección de "100%"

/** Se ejecuta DENTRO de la página de Udemy — no puede usar nada de fuera. */
function detectCourseCompleteInPage() {
  try {
    const text = document.body ? document.body.innerText || "" : "";
    if (/\b100\s?%[^.\n]{0,20}(complet|finaliz)/i.test(text)) return true;
    if (/(complet|finaliz)[a-záéíóúñ]*[^.\n]{0,20}\b100\s?%/i.test(text)) return true;
    const bars = document.querySelectorAll('[role="progressbar"], progress');
    for (const el of bars) {
      const raw = el.getAttribute("aria-valuenow") || el.getAttribute("value");
      const val = raw !== null ? parseFloat(raw) : NaN;
      if (!Number.isNaN(val) && Math.round(val) >= 100) return true;
    }
    return false;
  } catch {
    return false;
  }
}

async function checkCourseCompletion(taskUuid, tabId) {
  try {
    const [{ result } = {}] = await chrome.scripting.executeScript({
      target: { tabId },
      func: detectCourseCompleteInPage,
    });
    if (!result) return;
  } catch (err) {
    // La pestaña pudo cerrarse, cambiar de origen, etc. — no es un error
    // real, simplemente no se pudo comprobar esta vez.
    return;
  }

  const cfg = await getConfig();
  if (!isConfigured(cfg)) return;
  try {
    await fetch(apiUrl(cfg, `/tasks/${taskUuid}/mark/course-complete/`), {
      method: "POST",
      headers: { Authorization: authHeader(cfg) },
    });
    refreshTasksCache();
  } catch (err) {
    console.warn("[Libreta] no se pudo avisar de curso completado (se reintentará solo):", err);
  }
}

// ------------------------------------------------------------ el ciclo

async function endSession(session) {
  await setCurrentSession(null);
  const minutes = Math.round((Date.now() - session.startedAt) / 60000);
  if (minutes < MIN_SESSION_MINUTES_TO_SEND) return;
  await sendSessionMinutes(session.task.uuid, minutes);
}

async function startSession(match) {
  await setCurrentSession({
    task: match.task,
    tabId: match.tabId,
    startedAt: Date.now(),
  });
}

async function reevaluate() {
  const match = await getActiveMatch();
  const current = await getCurrentSession();

  if (!match) {
    if (current) await endSession(current);
    return;
  }

  if (current && current.task.uuid === match.task.uuid && current.tabId === match.tabId) {
    return; // misma sesión, sigue contando sola — nada que hacer aquí
  }

  if (current) await endSession(current);
  await startSession(match);
}

async function heartbeat() {
  await reevaluate();
  const current = await getCurrentSession();
  if (current) await checkCourseCompletion(current.task.uuid, current.tabId);
  await flushPendingUploads();
}

// ------------------------------------------------------------ arranque

chrome.tabs.onActivated.addListener(() => reevaluate());
chrome.tabs.onUpdated.addListener((_tabId, changeInfo) => {
  if (changeInfo.title !== undefined || changeInfo.url !== undefined || changeInfo.status === "complete") {
    reevaluate();
  }
});
chrome.tabs.onRemoved.addListener(async (tabId) => {
  const current = await getCurrentSession();
  if (current && current.tabId === tabId) await endSession(current);
});
chrome.windows.onFocusChanged.addListener(() => reevaluate());
chrome.idle.onStateChanged.addListener(() => reevaluate());

chrome.idle.setDetectionInterval(IDLE_DETECTION_SECONDS);

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === HEARTBEAT_ALARM) heartbeat();
  if (alarm.name === RETRY_ALARM) flushPendingUploads();
});

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create(HEARTBEAT_ALARM, { periodInMinutes: 1 });
  chrome.alarms.create(RETRY_ALARM, { periodInMinutes: 5 });
  refreshTasksCache();
});
chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create(HEARTBEAT_ALARM, { periodInMinutes: 1 });
  chrome.alarms.create(RETRY_ALARM, { periodInMinutes: 5 });
  refreshTasksCache();
});
