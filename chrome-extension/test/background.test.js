const test = require("node:test");
const assert = require("node:assert/strict");
const { makeEnv, udemyTask } = require("./harness");

const counts = async (env) => Boolean(await env.ctx.getActiveMatch());

// ------------------------------------------------ Udemy "por vídeos vistos"
test("vídeo: sonando cuenta", async () => {
  const env = makeEnv(); env.setTasks([udemyTask()]);
  env.tab.audible = true; env.idle = "idle";
  assert.equal(await counts(env), true);
});

test("vídeo: parado con el ratón activo NO cuenta (el fallo original)", async () => {
  const env = makeEnv(); env.setTasks([udemyTask()]);
  env.tab.audible = false; env.idle = "active";
  assert.equal(await counts(env), false);
});

test("vídeo: parado hace 5 min con ratón activo NO cuenta", async () => {
  const env = makeEnv(); env.setTasks([udemyTask()]);
  env.store.session.lastPlaying = { 5: env.now - env.minutes(5) };
  assert.equal(await counts(env), false);
});

test("vídeo: pausa de 30 s se tolera, de 90 s no", async () => {
  const env = makeEnv(); env.setTasks([udemyTask()]);
  env.store.session.lastPlaying = { 5: env.now - 30000 };
  assert.equal(await counts(env), true);
  env.store.session.lastPlaying = { 5: env.now - 90000 };
  assert.equal(await counts(env), false);
});

test("vídeo: reproduciéndose con el sonido silenciado cuenta", async () => {
  const env = makeEnv(); env.setTasks([udemyTask()]);
  env.videoPlaying = true;
  assert.equal(await counts(env), true);
});

test("vídeo: ratón activo en el Q&A (nunca hubo vídeo) NO cuenta", async () => {
  const env = makeEnv(); env.setTasks([udemyTask()]);
  env.tab.url = "https://www.udemy.com/course/python/learn/lecture/1#questions";
  env.idle = "active";
  assert.equal(await counts(env), false);
});

// --------------------------------------- Udemy "por tiempo en la página"
test("tiempo: sin vídeo pero con ratón activo cuenta", async () => {
  const env = makeEnv(); env.setTasks([udemyTask({ watch_requires_audio: false })]);
  env.idle = "active";
  assert.equal(await counts(env), true);
});

test("tiempo: 5 min inactivo NO cuenta, aunque suene", async () => {
  const env = makeEnv(); env.setTasks([udemyTask({ watch_requires_audio: false })]);
  env.idle = "idle"; env.tab.audible = true;
  assert.equal(await counts(env), false);
});

test("los dos modos no se mezclan: mismo estado, resultado distinto", async () => {
  const video = makeEnv(); video.setTasks([udemyTask({ watch_requires_audio: true })]);
  const time = makeEnv(); time.setTasks([udemyTask({ watch_requires_audio: false })]);
  for (const e of [video, time]) { e.tab.audible = false; e.idle = "active"; }
  assert.equal(await counts(video), false);
  assert.equal(await counts(time), true);
});

// --------------------------------------------- contabilidad de la sesión
test("vídeo: la sesión no suma el rato de pausa de más", async () => {
  const env = makeEnv(); env.configure(); env.setTasks([udemyTask()]);
  env.tab.audible = true;
  await env.ctx.reevaluate();                         // empieza a las 10:00
  env.advance(env.minutes(10));                        // 10:10 se pausa el vídeo
  env.tab.audible = false;
  await env.listeners.tabUpdated(5, { audible: false });
  env.advance(env.minutes(15));                        // 10:25 sigue parado, ratón activo
  await env.ctx.reevaluate();
  assert.equal(env.posts.length, 1);
  // 10 min de vídeo + 1 min de pausa tolerada = 11 (antes habrían sido 25)
  assert.equal(env.posts[0].body.minutes, 11);
});

test("tiempo: al irte no se suman los 5 min de espera de chrome.idle", async () => {
  const env = makeEnv(); env.configure(); env.setTasks([udemyTask({ watch_requires_audio: false })]);
  await env.ctx.reevaluate();                         // 10:00 empieza
  env.advance(env.minutes(20));                        // 10:20 dejas de tocar
  env.advance(env.minutes(5));                         // 10:25 chrome avisa: idle
  env.idle = "idle";
  await env.listeners.idle("idle");
  assert.equal(env.posts.length, 1);
  assert.equal(env.posts[0].body.minutes, 20);        // antes: 25
});

test("tiempo: volver a estar activo limpia el instante de inactividad", async () => {
  const env = makeEnv(); env.configure(); env.setTasks([udemyTask({ watch_requires_audio: false })]);
  env.advance(env.minutes(5)); env.idle = "idle"; await env.listeners.idle("idle");
  env.advance(env.minutes(5)); env.idle = "active"; await env.listeners.idle("active");
  assert.equal(env.store.session.idleSince, undefined);
  await env.ctx.reevaluate();                         // nueva sesión
  env.advance(env.minutes(12)); env.tab.url = "https://example.com/"; // cambias de pestaña
  await env.ctx.reevaluate();
  assert.equal(env.posts.at(-1).body.minutes, 12);
});

// ----------------------------------------------------------- Ilerna / PDF
test("Ilerna: suena o hay actividad cuenta; silencio + inactivo no", async () => {
  const env = makeEnv();
  env.tab.url = "https://ilernaonline.zoom.us/rec/play/abc"; env.tab.title = "Clase";
  env.setTasks([{ uuid: "t-il", title: "Clases", subcategory: "ilerna", watch_keyword: "", target_minutes: 45 }]);
  env.tab.audible = true; env.idle = "idle"; assert.equal(await counts(env), true);
  env.tab.audible = false; env.idle = "active"; assert.equal(await counts(env), true);
  env.tab.audible = false; env.idle = "idle"; assert.equal(await counts(env), false);
});

test("PDF: solo cuenta con actividad", async () => {
  const env = makeEnv();
  env.tab.url = "https://example.com/libro.pdf"; env.tab.title = "clean-code.pdf";
  env.setTasks([{ uuid: "t-rd", title: "Leer", subcategory: "reading", watch_keyword: "clean-code", reading_mode: "freestyle" }]);
  env.idle = "active"; assert.equal(await counts(env), true);
  env.idle = "idle"; assert.equal(await counts(env), false);
});

// ------------------------------------------------------------- emparejado
test("la palabra clave específica gana al hábito genérico", async () => {
  const env = makeEnv();
  env.setTasks([
    udemyTask({ uuid: "generico", watch_keyword: "" }),
    udemyTask({ uuid: "curso", watch_keyword: "python" }),
  ]);
  env.tab.audible = true;
  const m = await env.ctx.getActiveMatch();
  assert.equal(m.task.uuid, "curso");
});

// ------------------------------------------------- cola de envíos fallidos
const networkDown = async () => { throw new TypeError("Failed to fetch"); };

test("envío fallido por red se guarda y se reintenta", async () => {
  const env = makeEnv(); env.configure();
  env.fetchImpl = networkDown;
  await env.ctx.sendSessionMinutes("t1", 7, "udemy.com");
  assert.equal(env.store.local.pendingUploads.length, 1);
  env.fetchImpl = null;
  await env.ctx.flushPendingUploads();
  assert.equal(env.store.local.pendingUploads.length, 0);
  assert.equal(env.posts.length, 1);
});

test("dos reintentos a la vez no duplican minutos", async () => {
  const env = makeEnv(); env.configure();
  env.fetchImpl = networkDown;
  await env.ctx.sendSessionMinutes("t1", 7, "udemy.com");
  env.fetchImpl = null;
  await Promise.all([env.ctx.flushPendingUploads(), env.ctx.flushPendingUploads()]);
  assert.equal(env.posts.length, 1);
});

test("un fallo nuevo durante un reintento no se pierde", async () => {
  const env = makeEnv(); env.configure();
  env.fetchImpl = networkDown;
  await env.ctx.sendSessionMinutes("t1", 7, "udemy.com");
  let release;
  const gate = new Promise((r) => { release = r; });
  env.fetchImpl = async (url, opts) => {
    if ((opts.method || "GET") === "POST") { await gate; return { ok: true, status: 200, json: async () => ({}) }; }
    return null;
  };
  const flushing = env.ctx.flushPendingUploads();
  await new Promise((r) => setTimeout(r, 5));
  const queued = env.ctx.queueFailedUpload("t2", 3, "udemy.com");   // llega mientras se reintenta
  release();
  await Promise.all([flushing, queued]);
  const left = env.store.local.pendingUploads;
  assert.equal(left.length, 1);
  assert.equal(left[0].taskUuid, "t2");
});

test("un 404 no se reintenta eternamente; un 500 sí", async () => {
  const env = makeEnv(); env.configure();
  env.fetchImpl = async (url, opts) => (opts.method === "POST" ? { ok: false, status: 404, json: async () => ({}) } : null);
  await env.ctx.sendSessionMinutes("borrada", 7, "udemy.com");
  assert.equal(env.store.local.pendingUploads, undefined);
  env.fetchImpl = async (url, opts) => (opts.method === "POST" ? { ok: false, status: 500, json: async () => ({}) } : null);
  await env.ctx.sendSessionMinutes("t1", 7, "udemy.com");
  assert.equal(env.store.local.pendingUploads.length, 1);
  await env.ctx.flushPendingUploads();
  assert.equal(env.store.local.pendingUploads.length, 1);
});

test("los segundos sueltos se arrastran entre sesiones (40 s x3 = 2 min)", async () => {
  const env = makeEnv();
  const got = [];
  for (let i = 0; i < 3; i++) got.push(await env.ctx.takeWholeMinutes("t1", 40000));
  assert.deepEqual(got, [1, 0, 1]);
  assert.equal(got.reduce((a, b) => a + b, 0), 2);
});
