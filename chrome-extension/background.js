/**
 * Service worker de la extensión "Libreta — Tiempo en Udemy y Lectura".
 *
 * Qué hace, en corto: mientras una pestaña "trackeable" está en primer
 * plano (ventana con foco, pestaña activa, sin inactividad) y su título
 * contiene la palabra clave de alguna tarea pendiente, cuenta el
 * tiempo. En cuanto deja de cumplirse cualquiera de esas condiciones,
 * manda UNA sesión con el total a /api/tasks/<uuid>/focus/ — el mismo
 * endpoint y la misma forma que ya usa el plugin de lectura del móvil
 * (ver mobile-app/www/js/focus-view.js), con source="pc_usage" en vez
 * de "app_usage".
 *
 * Hay dos tipos de pestaña trackeable, cada uno emparejado con un
 * subtipo de tarea distinto:
 *
 *   - Udemy (category="study", subcategory="udemy"): la pestaña es
 *     udemy.com Y ADEMÁS suena (chrome.tabs.audible) — estar en el
 *     Q&A, las reseñas o el temario del curso sin el vídeo reproduciéndose
 *     NO cuenta como estudiar, el audio es la única señal fiable desde
 *     fuera de la página de que la clase se está viendo de verdad.
 *     Además, mientras hay sesión, se comprueba cada minuto cuánto
 *     lleva el curso (ver checkCourseCompletion) — el % se manda siempre
 *     que se puede calcular, para la barra de la pantalla del plan, y si
 *     Udemy lo reporta al 100% eso además cierra la tarea entera, no
 *     solo el día.
 *
 *   - Lectura de un PDF (category="work", subcategory="reading"): la
 *     pestaña es un .pdf (local, file://, o servido por una web) visto
 *     con el visor nativo de Chrome. No hay forma de detectar "página
 *     final" desde fuera (el visor nativo no es accesible a scripts de
 *     extensión), así que aquí solo se cuenta tiempo — el cierre de la
 *     tarea, si tiene target_minutes, ya lo hace solo el backend cuando
 *     se llega al objetivo del día (mismo mecanismo que Udemy, ver
 *     focus_save en tasks/api.py).
 *
 * No hay tramos "en pausa": si sales de la pestaña o del contenido,
 * esa sesión se cierra y se manda tal cual — volver más tarde empieza
 * una sesión nueva. Es literalmente "cuenta segundos con la pestaña en
 * primer plano", sin acumular huecos.
 */

const TASKS_CACHE_TTL_MS = 2 * 60 * 1000;     // 2 min
const IDLE_DETECTION_SECONDS = 300;            // 5 min sin tocar ratón/teclado = inactivo
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
  // Sin filtro de categoría: aquí se necesitan tareas de dos categorías
  // distintas (Estudio → Udemy, Enfoque → Lectura), así que se pide
  // todo lo pendiente de hoy y se filtra en el cliente.
  const resp = await fetch(apiUrl(cfg, "/tasks/"), {
    headers: { Authorization: authHeader(cfg) },
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const data = await resp.json();
  const pending = Array.isArray(data.pending) ? data.pending : [];
  // Antes se exigia palabra clave puesta siempre. Ahora una tarea
  // suelta de Udemy (o de Lectura) SIN palabra clave es un habito
  // GENERICO a proposito -- "pasa tiempo en Udemy" / "pasa tiempo
  // leyendo", sin curso ni libro concreto que reconocer -- asi que
  // tambien se deja pasar. matchTask() es quien decide, mas abajo, que
  // una palabra clave especifica (normalmente de un Plan) gana siempre
  // sobre el habito generico si las dos encajan a la vez.
  return pending.filter((t) => t.subcategory === "udemy" || t.subcategory === "reading");
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
  let best = null;
  if (title) {
    for (const t of tasks) {
      const kw = (t.watch_keyword || "").trim().toLowerCase();
      if (kw && title.includes(kw)) {
        if (!best || kw.length > best.keyword.length) best = { task: t, keyword: kw };
      }
    }
  }
  if (best) return best;
  // Ninguna palabra clave especifica encaja: si hay una tarea suelta
  // "generica" (sin palabra clave puesta a proposito -- ver
  // _study_link_error en el backend), se lleva el tiempo ella en su
  // lugar -- es el habito de "pasar tiempo en Udemy/leyendo", sin
  // curso concreto. Una palabra clave especifica (normalmente de un
  // Plan) SIEMPRE gana sobre esto -- por eso se prueba primero, arriba
  // -- para que las dos nunca se pisen ni sumen el mismo rato dos veces.
  const generic = tasks.find((t) => !(t.watch_keyword || "").trim());
  return generic ? { task: generic, keyword: "" } : null;
}

function isUdemyUrl(rawUrl) {
  try {
    const u = new URL(rawUrl);
    return /(^|\.)udemy\.com$/i.test(u.hostname);
  } catch {
    return false;
  }
}

function isPdfUrl(rawUrl) {
  try {
    const u = new URL(rawUrl);
    return /\.pdf($|[?#])/i.test(u.pathname);
  } catch {
    return false;
  }
}

/** Nombre corto para guardar como app_package de la sesión de lectura. */
function pdfFileName(rawUrl) {
  try {
    const u = new URL(rawUrl);
    const last = u.pathname.split("/").filter(Boolean).pop() || u.pathname;
    return decodeURIComponent(last).slice(0, 120);
  } catch {
    return "pdf_local";
  }
}

/** Tarea+pestaña que tocaría estar contando AHORA MISMO, o null si nada aplica. */
async function getActiveMatch() {
  try {
    const win = await chrome.windows.getLastFocused({ populate: false }).catch(() => null);
    if (!win || !win.focused) return null;

    const tabs = await chrome.tabs.query({ active: true, windowId: win.id });
    const tab = tabs[0];
    if (!tab || !tab.url) return null;

    const udemy = isUdemyUrl(tab.url);
    const pdf = !udemy && isPdfUrl(tab.url);
    if (!udemy && !pdf) return null;

    if (udemy) {
      // Estar en una pestaña de udemy.com no es lo mismo que estar
      // viendo una clase — se puede estar leyendo el Q&A, las reseñas o
      // el temario del curso sin que el vídeo esté sonando, y eso es
      // contenido trivial, no estudiar. La única señal fiable desde
      // fuera de la página de que la clase se está reproduciendo de
      // verdad es que la pestaña suene, así que aquí NO basta con no
      // estar inactivo: sin audio, no cuenta, aunque sigas ahí delante.
      if (!tab.audible) return null;
    } else {
      // Un PDF no suena nunca, así que aquí la única señal de "sigues
      // ahí" que hay es la inactividad de ratón/teclado de Chrome.
      const idleState = await chrome.idle.queryState(IDLE_DETECTION_SECONDS);
      if (idleState !== "active") return null;
    }

    const tasks = await getCachedTasks();
    const candidates = tasks.filter((t) => t.subcategory === (udemy ? "udemy" : "reading"));
    const found = matchTask(candidates, tab.title);
    if (!found) return null;

    return {
      task: found.task,
      tabId: tab.id,
      appPackage: udemy ? "udemy.com" : pdfFileName(tab.url),
    };
  } catch (err) {
    console.warn("[Libreta] getActiveMatch falló:", err);
    return null;
  }
}

// --------------------------------------------------------- subir sesión

async function queueFailedUpload(taskUuid, minutes, appPackage) {
  const { pendingUploads } = await chrome.storage.local.get("pendingUploads");
  const list = Array.isArray(pendingUploads) ? pendingUploads : [];
  list.push({ taskUuid, minutes, appPackage, queuedAt: Date.now() });
  await chrome.storage.local.set({ pendingUploads: list });
}

async function postFocusSession(cfg, taskUuid, minutes, appPackage) {
  const resp = await fetch(apiUrl(cfg, `/tasks/${taskUuid}/focus/`), {
    method: "POST",
    headers: { Authorization: authHeader(cfg), "Content-Type": "application/json" },
    body: JSON.stringify({ minutes, source: "pc_usage", app_package: appPackage }),
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

async function sendSessionMinutes(taskUuid, minutes, appPackage) {
  const cfg = await getConfig();
  if (!isConfigured(cfg)) return;
  try {
    await postFocusSession(cfg, taskUuid, minutes, appPackage);
    // La lista de tareas pudo cambiar (objetivo cumplido = tarea ya no
    // pendiente hoy) — se refresca para que la próxima comprobación no
    // la siga ofreciendo como candidata.
    refreshTasksCache();
  } catch (err) {
    console.warn("[Libreta] no se pudo mandar la sesión, se guarda para reintentar:", err);
    await queueFailedUpload(taskUuid, minutes, appPackage);
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
      await postFocusSession(cfg, item.taskUuid, item.minutes, item.appPackage);
    } catch {
      stillFailing.push(item);
    }
  }
  await chrome.storage.local.set({ pendingUploads: stillFailing });
  if (stillFailing.length < list.length) refreshTasksCache();
}

// ----------------------------------------------- detección de "100%"
// (solo aplica a Udemy — un PDF en el visor nativo no es inspeccionable
// desde la extensión, así que para "reading" nunca se llama a esto.)

// Mínimo de fracciones "x/x" que hacen falta para fiarse del resultado —
// una sola por casualidad no basta (aunque, al estar acotado al apartado
// de contenido del curso, ya cuesta mucho más que cuele algo que no sea
// una sección real).
const COURSE_PROGRESS_MIN_FRACTIONS = 1;

// Título de "Contenido del curso" tal cual lo pone Udemy según el idioma
// de la interfaz — para poder acotar la búsqueda SOLO a ese apartado y
// dejar fuera valoraciones/comentarios ("10/10, lo recomiendo") que
// también podrían leerse como una fracción si mirásemos toda la página.
const COURSE_CONTENT_HEADINGS = [
  "course content",       // inglés
  "contenido del curso",  // español
  "contenu du cours",     // francés
  "kursinhalte",          // alemán
  "contenuto del corso",  // italiano
];

/**
 * Busca el título "Course content" (en cualquiera de los idiomas de
 * arriba) y devuelve el texto SOLO del bloque que cuelga de él — no toda
 * la página. El título suele venir en un contenedor pequeño (icono +
 * texto), así que hay que subir unos pocos niveles hasta dar con el
 * contenedor que ya incluye la lista de secciones (bastante más texto
 * que el propio título suelto).
 *
 * Si no lo encuentra (Udemy cambió el marcado, título en otro idioma que
 * no está en la lista...), devuelve null y quien llame usa un respaldo
 * más conservador en vez de mirar la página entera a lo loco.
 */
function getCourseContentSectionText() {
  const heading = Array.from(
    document.querySelectorAll('h1,h2,h3,h4,h5,[role="heading"]')
  ).find((el) => {
    const t = (el.textContent || "").trim().toLowerCase();
    return COURSE_CONTENT_HEADINGS.some((h) => t === h || t.startsWith(h));
  });
  if (!heading) return null;

  const headingLen = (heading.textContent || "").trim().length;
  let node = heading;
  for (let i = 0; i < 6 && node.parentElement; i++) {
    node = node.parentElement;
    const len = (node.innerText || "").length;
    // +200 es un margen arbitrario para asegurarnos de que ya no es solo
    // el título repetido/envuelto, sino que trae contenido de verdad
    // (las secciones) debajo.
    if (len > headingLen + 200) return node.innerText || "";
  }
  return node.innerText || null;
}

/** Extrae fracciones "num/num" de un trozo de texto, descartando lo que
 * parece nota con decimales ("4.7/5") o fecha ("12/09/2024"). */
function extractSectionFractions(text) {
  const fractionRe = /\b(\d{1,3})\s*\/\s*(\d{1,3})\b/g;
  const fractions = [];
  let match;
  while ((match = fractionRe.exec(text)) !== null) {
    const before = text.slice(Math.max(0, match.index - 2), match.index);
    const after = text.slice(
      match.index + match[0].length,
      match.index + match[0].length + 3
    );
    if (/\d\.$/.test(before)) continue;        // "4.7/5" → nota, no lección
    if (/^\s*\/\s*\d/.test(after)) continue;   // "12/09/2024" → fecha
    const total = parseInt(match[2], 10);
    if (total <= 0) continue;                    // "0/0" no dice nada
    fractions.push([parseInt(match[1], 10), total]);
  }
  return fractions;
}

/** Se ejecuta DENTRO de la página de Udemy — no puede usar nada de fuera.
 *
 * OJO: antes esto contaba como "curso completo" cualquier
 * <progress>/[role="progressbar"] de la página con valor >= 100, pero eso
 * incluye el propio scrubber del reproductor de vídeo — que llega a 100 al
 * terminar CUALQUIER lección, no solo la última. Y el texto en español
 * ("curso"+"100%"+"completado") tampoco vale si Udemy está en otro idioma.
 *
 * Detección principal, independiente del idioma: en "Contenido del
 * curso" cada sección enseña cuántas lecciones tiene vistas como "x/x"
 * (ej. "10/10") — son solo números, da igual el idioma de la interfaz.
 * Si TODAS las fracciones de ESE apartado (no de toda la página, para no
 * colar reseñas) tienen el mismo número a los dos lados, está completo.
 *
 * De paso (esto es lo nuevo) se suma nº de lecciones vistas / totales de
 * TODAS las fracciones del apartado para sacar un % de avance del curso
 * entero — no solo el "sí/no" de completado — así la pantalla del plan
 * puede enseñar una barra de "cuánto llevas" en vez de nada hasta que se
 * termina del todo. Devuelve {complete, pct}: `pct` sale null cuando no
 * hay suficientes fracciones fiables (mismo umbral que la detección de
 * completado) o cuando se cae al respaldo de texto, que no da números.
 */
async function detectCourseProgressInPage() {
  // Vía principal: la API de Udemy (misma origin, con la sesión del
  // usuario). El panel "Contenido del curso" ya no enseña fracciones x/y
  // como texto, así que leer el DOM no da nada. Ojo: esta función se
  // serializa y se ejecuta DENTRO de la página, por eso no puede usar
  // helpers ni constantes definidos fuera de ella.
  try {
    const slug = location.pathname.split("/")[2];
    if (location.pathname.startsWith("/course/") && slug) {
      const get = async (u) => {
        const r = await fetch(u, { credentials: "include" });
        return r.ok ? r.json() : null;
      };
      const c = await get(`/api-2.0/courses/${slug}/?fields[course]=id`);
      if (c && c.id) {
        const p = await get(
          `/api-2.0/users/me/subscribed-courses/${c.id}/?fields[course]=completion_ratio,num_published_lectures`
        );
        if (p && typeof p.completion_ratio === "number" && p.num_published_lectures > 0) {
          const total = p.num_published_lectures;
          const pct = Math.max(0, Math.min(100, Math.round(p.completion_ratio)));
          const done = Math.min(total, Math.round((total * p.completion_ratio) / 100));
          return { complete: pct >= 100, pct, done, total };
        }
      }
    }
  } catch (e) {
    // sigue con el respaldo de abajo
  }
  try {
    // Varias vías para localizar el temario (Udemy cambia el marcado y
    // el título "Contenido del curso" no siempre es un <h2>): 1) por
    // título, 2) por las cabeceras de sección (data-purpose), 3) por el
    // contenedor del temario. La primera que dé fracciones gana.
    const candidates = [getCourseContentSectionText()];
    const collect = (selector) => {
      const els = Array.from(document.querySelectorAll(selector));
      return els.length ? els.map((el) => el.innerText || el.textContent || "").join("\n") : null;
    };
    candidates.push(collect('[data-purpose*="section-heading"], [data-purpose*="section-title"]'));
    candidates.push(collect('[data-purpose*="curriculum-section"], [data-purpose*="section-panel"]'));
    candidates.push(collect('[data-purpose*="curriculum"], [data-purpose*="sidebar"]'));
    let scoped = null;
    let fractions = [];
    for (const c of candidates) {
      if (!c) continue;
      const f = extractSectionFractions(c);
      if (f.length >= COURSE_PROGRESS_MIN_FRACTIONS) { scoped = c; fractions = f; break; }
    }
    console.log("[Libreta] curso Udemy: fracciones detectadas =", fractions.length);
    if (scoped) {
      if (fractions.length >= COURSE_PROGRESS_MIN_FRACTIONS) {
        const done = fractions.reduce((sum, [d]) => sum + d, 0);
        const total = fractions.reduce((sum, [, t]) => sum + t, 0);
        return {
          complete: fractions.every(([d, t]) => d === t),
          pct: total > 0 ? Math.round((done / total) * 100) : null,
          done,
          total,
        };
      }
      // Encontramos el apartado pero no salen suficientes fracciones
      // ahí (temario con 1 sola sección, colapsado sin contadores...) —
      // no concluir "no" a ciegas, seguir con el respaldo de texto.
    }

    // Respaldo si no se pudo acotar el apartado (título no encontrado):
    // solo el texto en español, más específico que una fracción suelta
    // y con mucho menos riesgo de colarse desde una reseña. Sin
    // fracciones no hay con qué sacar un %, así que aquí siempre null.
    const text = document.body ? document.body.innerText || "" : "";
    let complete = false;
    if (/\bcurso\b[^.\n]{0,40}\b100\s?%[^.\n]{0,20}(complet|finaliz)/i.test(text)) complete = true;
    if (/(complet|finaliz)[a-záéíóúñ]*[^.\n]{0,20}\b100\s?%[^.\n]{0,40}\bcurso\b/i.test(text)) complete = true;

    return { complete, pct: null };
  } catch {
    return { complete: false, pct: null };
  }
}

async function checkCourseCompletion(taskUuid, tabId, itemId = null) {
  let progress;
  try {
    const [{ result } = {}] = await chrome.scripting.executeScript({
      target: { tabId },
      func: detectCourseProgressInPage,
    });
    progress = result;
  } catch (err) {
    // La pestaña pudo cerrarse, cambiar de origen, etc. — no es un error
    // real, simplemente no se pudo comprobar esta vez.
    console.warn("[Libreta] no se pudo leer el progreso en la pestaña:", err);
    return;
  }
  console.log("[Libreta] progreso del curso leído:", JSON.stringify(progress));
  if (!progress) return;

  const cfg = await getConfig();
  if (!isConfigured(cfg)) return;

  // El % se manda aparte de "completado" -- son dos señales
  // independientes (ver Task.record_course_progress vs
  // finish_recurring_series), así que uno puede fallar sin bloquear al
  // otro.
  if (progress.pct !== null && progress.pct !== undefined) {
    try {
      const progressUrl = itemId
        ? `/plan-items/${itemId}/course-progress/`
        : `/tasks/${taskUuid}/course-progress/`;
      const res = await fetch(apiUrl(cfg, progressUrl), {
        method: "POST",
        headers: { Authorization: authHeader(cfg), "Content-Type": "application/json" },
        body: JSON.stringify({ pct: progress.pct, done: progress.done, total: progress.total }),
      });
      console.log("[Libreta] % del curso enviado al servidor -> HTTP", res.status);
    } catch (err) {
      console.warn("[Libreta] no se pudo mandar el % del curso (se reintentará en el próximo heartbeat):", err);
    }
  }

  if (!progress.complete || !taskUuid) return;
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
  await sendSessionMinutes(session.task.uuid, minutes, session.appPackage);
}

async function startSession(match) {
  await setCurrentSession({
    task: match.task,
    tabId: match.tabId,
    appPackage: match.appPackage,
    startedAt: Date.now(),
  });
}

async function reevaluate({ allowEndOnNoMatch = true } = {}) {
  const match = await getActiveMatch();
  const current = await getCurrentSession();

  if (!match) {
    // chrome.tabs.onUpdated dispara por CUALQUIER cambio en la pestaña —
    // Udemy cambia el título entre lecciones, un PDF cambia de página
    // visible, hay instantes de buffering sin sonido, etc. Cortar la
    // sesión ahí mismo la trocea en un montón de sesiones de segundos
    // que casi nunca llegan al minuto mínimo, y deja el popup enseñando
    // "sin actividad" casi todo el rato aunque sí se esté contando. Solo
    // se corta de verdad ante una señal fiable (cambiaste de pestaña,
    // perdiste el foco, te quedaste inactivo) o en el latido de cada
    // minuto, que confirma el estado real.
    if (current && allowEndOnNoMatch) await endSession(current);
    return;
  }

  if (current && current.task.uuid === match.task.uuid && current.tabId === match.tabId) {
    return; // misma sesión, sigue contando sola — nada que hacer aquí
  }

  if (current) await endSession(current);
  await startSession(match);
  if (match.task.subcategory === "udemy" && (match.task.watch_keyword || "").trim()) {
    checkCourseCompletion(match.task.uuid, match.tabId);
  }
}

// El % del curso NO depende de que haya una sesión de tiempo en marcha
// (que exige audio sonando + ventana enfocada): basta con estar en una
// pestaña de Udemy cuyo título case con la palabra clave de un curso.
// Los cursos de Udemy vienen de los OBJETIVOS de los planes activos
// (palabra clave + id del objetivo), no de la tarea diaria: esa puede no
// existir hoy, estar hecha o no llevar la palabra clave.
let udemyCoursesCache = { at: 0, courses: [] };
async function getUdemyCourses() {
  if (Date.now() - udemyCoursesCache.at < 5 * 60 * 1000 && udemyCoursesCache.courses.length) {
    return udemyCoursesCache.courses;
  }
  const cfg = await getConfig();
  if (!isConfigured(cfg)) {
    console.warn("[Libreta] extensión sin configurar (URL/usuario/contraseña en Opciones)");
    return [];
  }
  try {
    const resp = await fetch(apiUrl(cfg, "/plans/udemy-courses/"), { headers: { Authorization: authHeader(cfg) } });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    const courses = (data.courses || []).filter((c) => (c.watch_keyword || "").trim());
    udemyCoursesCache = { at: Date.now(), courses };
    console.log("[Libreta] cursos de Udemy en planes:", courses.map((c) => c.watch_keyword));
    return courses;
  } catch (err) {
    console.warn("[Libreta] no se pudo pedir los cursos de Udemy (¿desplegado el servidor?):", err);
    return udemyCoursesCache.courses;
  }
}

let lastProgressCheckAt = 0;
async function checkProgressOnActiveUdemyTab(force = false) {
  try {
    if (!force && Date.now() - lastProgressCheckAt < 20000) return;
    const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    const tab = tabs[0];
    if (!tab || !tab.url || !isUdemyUrl(tab.url)) return;
    const candidates = await getUdemyCourses();
    const title = (tab.title || "").toLowerCase();
    let best = null;
    for (const c of candidates) {
      const kw = c.watch_keyword.trim().toLowerCase();
      if (title.includes(kw) && (!best || kw.length > best.kw.length)) best = { course: c, kw };
    }
    if (!best) {
      console.log("[Libreta] pestaña de Udemy sin curso que case. Título:", tab.title,
        "| palabras clave:", candidates.map((c) => c.watch_keyword));
      return;
    }
    lastProgressCheckAt = Date.now();
    await checkCourseCompletion(null, tab.id, best.course.item_id);
  } catch (err) {
    console.warn("[Libreta] checkProgressOnActiveUdemyTab falló:", err);
  }
}

async function heartbeat() {
  await checkProgressOnActiveUdemyTab();
  await reevaluate();
  const current = await getCurrentSession();
  if (current && current.task.subcategory === "udemy" && (current.task.watch_keyword || "").trim()) {
    await checkCourseCompletion(current.task.uuid, current.tabId);
  }
  await flushPendingUploads();
}

// ------------------------------------------------------------ arranque

chrome.tabs.onActivated.addListener(() => { reevaluate(); checkProgressOnActiveUdemyTab(); });
chrome.tabs.onUpdated.addListener((_tabId, changeInfo) => {
  if (
    changeInfo.title !== undefined ||
    changeInfo.url !== undefined ||
    changeInfo.status === "complete" ||
    changeInfo.audible !== undefined
  ) {
    // "Suave": puede EMPEZAR o CAMBIAR de sesión (nueva coincidencia),
    // pero no la CORTA solo porque en este instante concreto no
    // coincida nada — ver más arriba, en reevaluate().
    reevaluate({ allowEndOnNoMatch: false });
    if (changeInfo.status === "complete") setTimeout(() => checkProgressOnActiveUdemyTab(), 4000);
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

// ------------------------------------------------------------ diagnóstico

/**
 * Foto del estado ahora mismo, para el panel de diagnóstico del popup:
 * qué pestaña ve la extensión, cómo la clasifica, qué tareas tiene en
 * caché con sus palabras clave, y si alguna encaja con el título real
 * de la pestaña. Todo lo que necesitamos para saber POR QUÉ no está
 * contando, en vez de adivinarlo desde fuera.
 */
async function debugSnapshot() {
  const cfg = await getConfig();

  const win = await chrome.windows.getLastFocused({ populate: false }).catch(() => null);
  const focused = Boolean(win && win.focused);
  let tab = null;
  if (win) {
    const tabs = await chrome.tabs.query({ active: true, windowId: win.id });
    tab = tabs[0] || null;
  }

  const idleState = await chrome.idle.queryState(IDLE_DETECTION_SECONDS).catch(() => "desconocido");
  const tasks = await getCachedTasks();
  const { tasksCacheAt } = await chrome.storage.local.get("tasksCacheAt");

  const hasUrl = Boolean(tab && tab.url);
  const isUdemyTab = hasUrl && isUdemyUrl(tab.url);
  const isPdfTab = hasUrl && !isUdemyTab && isPdfUrl(tab.url);
  const noUrlButFileTab = Boolean(tab && !tab.url);
  const tabKind = isUdemyTab ? "udemy" : isPdfTab ? "pdf" : "otro";

  const candidates = tasks.filter((t) => t.subcategory === (isUdemyTab ? "udemy" : "reading"));
  const match = isUdemyTab || isPdfTab ? matchTask(candidates, tab.title) : null;

  const current = await getCurrentSession();

  return {
    configured: isConfigured(cfg),
    baseUrl: cfg.baseUrl || null,
    windowFocused: focused,
    tab: tab ? { url: tab.url || null, title: tab.title, audible: Boolean(tab.audible) } : null,
    noUrlButFileTab, // pestaña file:// sin el permiso "acceso a URLs de archivo" concedido
    tabKind,
    idleState,
    tasksCount: tasks.length,
    tasksCacheAgeSeconds: tasksCacheAt ? Math.round((Date.now() - tasksCacheAt) / 1000) : null,
    tasks: tasks.map((t) => ({ title: t.title, subcategory: t.subcategory, watch_keyword: t.watch_keyword })),
    match: match ? { taskTitle: match.task.title, keyword: match.keyword } : null,
    currentSession: current
      ? { taskTitle: current.task.title, subcategory: current.task.subcategory, startedAt: current.startedAt }
      : null,
  };
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "debug-snapshot") {
    debugSnapshot().then(sendResponse);
    return true; // respuesta asíncrona
  }
  if (msg && msg.type === "debug-refresh-tasks") {
    refreshTasksCache().then(() => debugSnapshot()).then(sendResponse);
    return true;
  }
});
