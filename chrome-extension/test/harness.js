// Entorno simulado de Chrome para probar background.js SIN navegador.
// Carga el background.js REAL en un contexto aislado y le da un `chrome`
// falso con reloj controlable. Uso:  node --test chrome-extension/test/
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const T0 = Date.UTC(2026, 9, 15, 10, 0, 0);

function makeEnv() {
  const env = {
    now: T0,
    tab: { id: 5, url: "https://www.udemy.com/course/python/learn/lecture/1", title: "Python - Udemy", audible: false },
    idle: "active",        // "active" | "idle" | "locked" (forzado, vale para cualquier umbral)
    idleFor: 0,            // segundos sin tocar nada; con idle:"active", queryState(n) da "idle" si idleFor >= n
    idleQueries: [],       // umbrales con los que se ha consultado chrome.idle.queryState
    detection: null,       // último chrome.idle.setDetectionInterval
    videoPlaying: false,
    focused: true,
    tasks: [],
    posts: [],            // sesiones mandadas al servidor (POST /focus/)
    fetchImpl: null,      // para sobrescribir el servidor falso
    listeners: {},
  };
  const store = { local: {}, session: {} };
  const area = (o) => ({
    get: async (keys) => {
      const out = {};
      const list = keys == null ? Object.keys(o) : Array.isArray(keys) ? keys : [keys];
      for (const k of list) if (k in o) out[k] = JSON.parse(JSON.stringify(o[k]));
      return out;
    },
    set: async (v) => { for (const [k, val] of Object.entries(v)) o[k] = JSON.parse(JSON.stringify(val)); },
    remove: async (k) => { for (const x of Array.isArray(k) ? k : [k]) delete o[x]; },
  });
  const noop = () => {};
  const on = (name) => ({ addListener: (fn) => { env.listeners[name] = fn; } });
  const chrome = {
    storage: { local: area(store.local), session: area(store.session) },
    windows: { getLastFocused: async () => ({ id: 1, focused: env.focused }), onFocusChanged: on("focus") },
    tabs: { query: async () => [env.tab], onActivated: on("tabActivated"), onUpdated: on("tabUpdated"), onRemoved: on("tabRemoved") },
    idle: {
      queryState: async (n) => {
        env.idleQueries.push(n);
        if (env.idle === "locked") return "locked";
        if (env.idle === "idle") return "idle";
        return env.idleFor >= n ? "idle" : "active";
      },
      onStateChanged: on("idle"),
      setDetectionInterval: (n) => { env.detection = n; },
    },
    scripting: { executeScript: async () => [{ result: env.videoPlaying }] },
    alarms: { onAlarm: on("alarm"), create: noop },
    runtime: { onInstalled: on("installed"), onStartup: on("startup"), onMessage: on("message") },
  };
  const RealDate = Date;
  class FakeDate extends RealDate {
    constructor(...a) { a.length ? super(...a) : super(env.now); }
    static now() { return env.now; }
  }
  const fetchFn = async (url, opts = {}) => {
    if (env.fetchImpl) { const r = await env.fetchImpl(url, opts); if (r) return r; }
    const method = (opts.method || "GET").toUpperCase();
    if (method === "POST" && /\/focus\/$/.test(url)) {
      env.posts.push({ url, body: JSON.parse(opts.body) });
      return { ok: true, status: 200, json: async () => ({ ok: true }) };
    }
    if (method === "GET" && /\/api\/tasks\/$/.test(url)) {
      return { ok: true, status: 200, json: async () => ({ pending: env.tasks }) };
    }
    return { ok: false, status: 404, json: async () => ({}) };
  };
  const ctx = vm.createContext({
    chrome, console: { log: noop, warn: noop, error: noop }, Date: FakeDate, URL, btoa, fetch: fetchFn,
    setTimeout, clearTimeout, Promise, JSON, Math, Set, Array, Object,
  });
  vm.runInContext(fs.readFileSync(process.env.BACKGROUND_FILE || path.join(__dirname, "..", "background.js"), "utf8"), ctx);
  env.ctx = ctx;
  env.store = store;
  env.configure = () => { store.local.config = { baseUrl: "https://libreta.test", user: "u", password: "p" }; };
  env.setTasks = (tasks) => { env.tasks = tasks; store.local.tasksCache = tasks; store.local.tasksCacheAt = env.now; };
  env.advance = (ms) => { env.now += ms; store.local.tasksCacheAt = env.now; };
  env.minutes = (n) => n * 60000;
  return env;
}

const webTask = (over = {}) => ({
  uuid: "t-web", title: "Hyperskill", subcategory: "web", watch_url: "hyperskill.org",
  watch_keyword: "", watch_idle_seconds: 120, watch_audio_counts: false, target_minutes: 30, ...over,
});

const udemyTask = (over = {}) => ({
  uuid: "t-udemy", title: "Curso", subcategory: "udemy", watch_keyword: "python",
  watch_requires_audio: true, target_minutes: 30, ...over,
});

module.exports = { makeEnv, udemyTask, webTask, T0 };
