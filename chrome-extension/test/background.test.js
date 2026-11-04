const test = require("node:test");
const assert = require("node:assert/strict");
const { makeEnv, udemyTask, webTask } = require("./harness");

const counts = async (env) => Boolean(await env.ctx.getActiveMatch());
// El listener de la alarma no devuelve la promesa del latido: se deja correr un rato.
const heartbeat = async (env) => {
  await env.listeners.alarm({ name: "libreta-udemy-heartbeat" });
  await new Promise((r) => setTimeout(r, 30));
};

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

// -------------------------------------------- Tiempo en una web (genérico)
const onWeb = (env, url, title = "Página") => { env.tab.url = url; env.tab.title = title; env.tab.audible = false; };

test("web: cuenta si la URL contiene el texto, en cualquier subpágina, https o www", async () => {
  const env = makeEnv(); env.setTasks([webTask()]);
  for (const url of ["https://hyperskill.org/learn/step/1", "http://www.Hyperskill.org/", "https://hyperskill.org/"]) {
    onWeb(env, url);
    assert.equal(await counts(env), true, url);
  }
  onWeb(env, "https://example.com/redir/hyperskill.org/x"); // el texto está en la ruta: también vale
  assert.equal(await counts(env), true);
  onWeb(env, "https://example.com/otra-cosa");
  assert.equal(await counts(env), false);
});

test("web: varios trozos separados por comas, vale cualquiera", async () => {
  const env = makeEnv(); env.setTasks([webTask({ watch_url: "hyperskill.org, ilernaonline.zoom.us/rec" })]);
  onWeb(env, "https://ilernaonline.zoom.us/rec/play/abc"); assert.equal(await counts(env), true);
  onWeb(env, "https://ilernaonline.zoom.us/j/123");        assert.equal(await counts(env), false);
  onWeb(env, "https://hyperskill.org/");                   assert.equal(await counts(env), true);
});

test("web: los trozos de menos de 3 letras se ignoran (no encajan con todo)", async () => {
  const env = makeEnv(); env.setTasks([webTask({ watch_url: "a" })]);
  onWeb(env, "https://example.com/a"); assert.equal(await counts(env), false);
});

test("web: la palabra del título, si se pone, es obligatoria", async () => {
  const env = makeEnv(); env.setTasks([webTask({ watch_keyword: "Programación" })]);
  onWeb(env, "https://hyperskill.org/", "Redes — Hyperskill");        assert.equal(await counts(env), false);
  onWeb(env, "https://hyperskill.org/", "PROGRAMACIÓN — Hyperskill"); assert.equal(await counts(env), true);
});

test("web: gana la tarea más específica (con palabra del título, luego trozo más largo)", async () => {
  const env = makeEnv();
  env.setTasks([
    webTask({ uuid: "general", watch_url: "hyperskill.org" }),
    webTask({ uuid: "ruta", watch_url: "hyperskill.org/learn" }),
    webTask({ uuid: "asig", watch_url: "hyperskill.org", watch_keyword: "java" }),
  ]);
  onWeb(env, "https://hyperskill.org/learn/step/1", "Python");
  assert.equal((await env.ctx.getActiveMatch()).task.uuid, "ruta");
  onWeb(env, "https://hyperskill.org/learn/step/1", "Java basics");
  assert.equal((await env.ctx.getActiveMatch()).task.uuid, "asig");
  onWeb(env, "https://hyperskill.org/", "Home");
  assert.equal((await env.ctx.getActiveMatch()).task.uuid, "general");
});

test("web: Udemy sigue yendo por su propia lógica aunque una web encaje con 'udemy'", async () => {
  const env = makeEnv();
  env.setTasks([webTask({ uuid: "w", watch_url: "udemy.com" }), udemyTask()]);
  env.tab.audible = true;                                        // reproductor de Udemy sonando
  assert.equal((await env.ctx.getActiveMatch()).task.uuid, "t-udemy");
});

// ---- anti-AFK
test("web anti-AFK: sin tocar nada más del umbral NO cuenta (aunque la página esté delante)", async () => {
  const env = makeEnv(); env.setTasks([webTask({ watch_idle_seconds: 120 })]);
  onWeb(env, "https://hyperskill.org/");
  env.idleFor = 30;  assert.equal(await counts(env), true);
  env.idleFor = 119; assert.equal(await counts(env), true);
  env.idleFor = 121; assert.equal(await counts(env), false);
});

test("web anti-AFK: cada tarea usa SU umbral de inactividad", async () => {
  const env = makeEnv(); env.setTasks([webTask({ watch_idle_seconds: 600 })]);
  onWeb(env, "https://hyperskill.org/");
  env.idleFor = 400;
  assert.equal(await counts(env), true);
  assert.equal(env.idleQueries.at(-1), 600);
  env.idleFor = 601;
  assert.equal(await counts(env), false);
});

test("web anti-AFK: sin umbral en la caché vieja se usa 3 min; los absurdos se acotan", async () => {
  const env = makeEnv(); env.setTasks([webTask({ watch_idle_seconds: undefined })]);
  onWeb(env, "https://hyperskill.org/");
  await counts(env); assert.equal(env.idleQueries.at(-1), 180);
  env.setTasks([webTask({ watch_idle_seconds: 1 })]);   await counts(env); assert.equal(env.idleQueries.at(-1), 15);
  env.setTasks([webTask({ watch_idle_seconds: 99999 })]); await counts(env); assert.equal(env.idleQueries.at(-1), 1800);
});

test("web anti-AFK: la pantalla bloqueada nunca cuenta, ni con audio", async () => {
  const env = makeEnv(); env.setTasks([webTask({ watch_audio_counts: true })]);
  onWeb(env, "https://hyperskill.org/"); env.tab.audible = true; env.idle = "locked";
  assert.equal(await counts(env), false);
});

test("web: el sonido NO cuenta por defecto (irte con la página sonando no vale)", async () => {
  const env = makeEnv(); env.setTasks([webTask({ watch_audio_counts: false })]);
  onWeb(env, "https://hyperskill.org/"); env.tab.audible = true; env.idle = "idle";
  assert.equal(await counts(env), false);
});

test("web con audio activado: suena o hay actividad cuenta; silencio + inactivo no", async () => {
  const env = makeEnv();
  env.setTasks([webTask({ uuid: "t-il", watch_url: "ilernaonline.zoom.us", watch_audio_counts: true, watch_idle_seconds: 300 })]);
  onWeb(env, "https://ilernaonline.zoom.us/rec/play/abc", "Clase");
  env.tab.audible = true;  env.idle = "idle";   assert.equal(await counts(env), true);
  env.tab.audible = false; env.idle = "active"; assert.equal(await counts(env), true);
  env.tab.audible = false; env.idle = "idle";   assert.equal(await counts(env), false);
});

test("web: ventana sin foco o pestaña en segundo plano NO cuenta", async () => {
  const env = makeEnv(); env.setTasks([webTask()]);
  onWeb(env, "https://hyperskill.org/");
  env.focused = false; assert.equal(await counts(env), false);
  env.focused = true;  assert.equal(await counts(env), true);
});

test("web: al irte no se suman los minutos de espera (umbral de 2 min)", async () => {
  const env = makeEnv(); env.configure(); env.setTasks([webTask({ watch_idle_seconds: 120 })]);
  onWeb(env, "https://hyperskill.org/");
  await env.ctx.reevaluate();                         // 10:00 empieza
  env.advance(env.minutes(20));                        // 10:20 dejas de tocar
  env.advance(120000);                                 // 10:22 chrome avisa: idle (umbral 2 min)
  env.idle = "idle"; env.idleFor = 121;
  await env.listeners.idle("idle");
  assert.equal(env.posts.length, 1);
  assert.equal(env.posts[0].body.minutes, 20);        // no 22
  assert.equal(env.posts[0].body.app_package, "hyperskill.org");
});

test("web: dejarlo olvidado horas NO suma horas (el latido cierra en el instante en que dejaste de tocar)", async () => {
  const env = makeEnv(); env.configure(); env.setTasks([webTask({ watch_idle_seconds: 120 })]);
  onWeb(env, "https://hyperskill.org/");
  await env.ctx.reevaluate();
  env.advance(env.minutes(10));                        // 10 min de uso real
  env.idle = "idle"; env.idleFor = 121;
  env.advance(120000); await env.listeners.idle("idle"); // chrome avisa a los 2 min
  env.advance(env.minutes(180));                       // te vas 3 horas, el PC sigue encendido
  await heartbeat(env);
  assert.equal(env.posts.length, 1);
  assert.equal(env.posts[0].body.minutes, 10);
});

test("web con audio: irse con el sonido puesto sigue contando (y lo avisa el formulario); al parar el sonido corta en el último instante presente", async () => {
  const env = makeEnv(); env.configure();
  env.setTasks([webTask({ watch_audio_counts: true, watch_idle_seconds: 120 })]);
  onWeb(env, "https://hyperskill.org/"); env.tab.audible = true;
  await env.ctx.reevaluate();                          // 10:00
  env.advance(env.minutes(3));                         // 10:03: dejas de tocar, sigue sonando
  env.idle = "idle"; env.idleFor = 121;
  await env.listeners.idle("idle");                    // idleSince ~10:01
  assert.equal(env.posts.length, 0);                   // sigue contando por el audio
  env.advance(env.minutes(27));                        // 10:30 sigue sonando
  await env.ctx.reevaluate();
  assert.equal(env.posts.length, 0);
  env.advance(env.minutes(5)); env.tab.audible = false;   // 10:35 deja de sonar
  await env.listeners.tabUpdated(env.tab.id, { audible: false });
  env.advance(env.minutes(60));                        // y te quedas ausente
  await heartbeat(env);
  assert.equal(env.posts.length, 1);
  assert.equal(env.posts[0].body.minutes, 35);         // 10:00 -> 10:35 (último sonido), no 95
});

test("web: cambiar de pestaña cierra la sesión sin perder el tiempo real", async () => {
  const env = makeEnv(); env.configure(); env.setTasks([webTask()]);
  onWeb(env, "https://hyperskill.org/");
  await env.ctx.reevaluate();
  env.advance(env.minutes(15));
  onWeb(env, "https://example.com/");                  // cambias de pestaña
  await env.ctx.reevaluate();
  assert.equal(env.posts.at(-1).body.minutes, 15);
});

test("web: el umbral de chrome.idle se ajusta al más estricto de las tareas web (máx. 300 s)", async () => {
  const env = makeEnv(); env.configure();
  env.tasks = [webTask({ watch_idle_seconds: 600 }), webTask({ uuid: "b", watch_idle_seconds: 60 })];
  await env.ctx.refreshTasksCache();
  assert.equal(env.detection, 60);
  env.tasks = [webTask({ watch_idle_seconds: 600 })];
  await env.ctx.refreshTasksCache();
  assert.equal(env.detection, 300);
  env.tasks = [webTask({ watch_idle_seconds: 5 })];
  await env.ctx.refreshTasksCache();
  assert.equal(env.detection, 15);                     // el mínimo que admite chrome.idle
  env.tasks = [udemyTask()];
  await env.ctx.refreshTasksCache();
  assert.equal(env.detection, 300);
});

test("web: el registro de la sesión dice que fue por actividad", async () => {
  const env = makeEnv(); env.configure(); env.setTasks([webTask()]);
  onWeb(env, "https://hyperskill.org/");
  await env.ctx.reevaluate();
  env.advance(env.minutes(2));
  await env.ctx.reevaluate();
  onWeb(env, "https://example.com/"); await env.ctx.reevaluate();
  const entry = env.store.local.sessionLog.at(-1);
  assert.equal(entry.mode, "web · solo actividad");
  assert.ok(entry.signals["actividad"] >= 1);
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

// ------------------------------- Udemy solo cuenta dentro del reproductor
test("fuera del reproductor (portada, ficha del curso) NO cuenta, en ningún modo", async () => {
  for (const requiresAudio of [true, false]) {
    for (const url of [
      "https://www.udemy.com/",
      "https://www.udemy.com/home/my-courses/learning/",
      "https://www.udemy.com/course/python/",
      "https://www.udemy.com/courses/search/?q=python",
    ]) {
      const env = makeEnv(); env.setTasks([udemyTask({ watch_requires_audio: requiresAudio })]);
      env.tab.url = url; env.idle = "active"; env.tab.audible = true; env.videoPlaying = true;
      assert.equal(await counts(env), false, `${url} (audio=${requiresAudio})`);
    }
  }
});

test("fuera del reproductor tampoco cuenta el hábito genérico de Udemy", async () => {
  const env = makeEnv(); env.setTasks([udemyTask({ watch_keyword: "" })]);
  env.tab.url = "https://www.udemy.com/"; env.tab.title = "Udemy"; env.idle = "active"; env.tab.audible = true;
  assert.equal(await counts(env), false);
});

test("dentro del reproductor (y en un Udemy de empresa) sigue contando", async () => {
  for (const url of [
    "https://www.udemy.com/course/python/learn/lecture/123#overview",
    "https://acme.udemy.com/course/python/learn/quiz/9",
  ]) {
    const env = makeEnv(); env.setTasks([udemyTask()]);
    env.tab.url = url; env.tab.audible = true;
    assert.equal(await counts(env), true, url);
  }
});

test("dejar la ficha del curso abierta no suma minutos (sesión completa)", async () => {
  const env = makeEnv(); env.configure(); env.setTasks([udemyTask({ watch_requires_audio: false })]);
  env.tab.url = "https://www.udemy.com/course/python/"; env.idle = "active";
  await env.ctx.reevaluate();
  env.advance(env.minutes(6));
  env.tab.url = "https://example.com/"; // al cambiar de pestaña se cierra y se manda lo contado
  await env.ctx.reevaluate();
  assert.equal(env.posts.length, 0);
});

// ------------------------------------------------ registro de sesiones
test("el registro guarda qué señales mantuvieron viva la sesión", async () => {
  const env = makeEnv(); env.configure(); env.setTasks([udemyTask()]);
  env.tab.audible = true;
  await env.ctx.reevaluate();
  env.advance(env.minutes(3)); await env.ctx.reevaluate();
  env.tab.audible = false; env.videoPlaying = true;
  env.advance(env.minutes(1)); await env.ctx.reevaluate();
  env.tab.url = "https://example.com/"; await env.ctx.reevaluate();
  const log = env.store.local.sessionLog;
  assert.equal(log.length, 1);
  assert.equal(log[0].mode, "vídeos");
  assert.deepEqual(log[0].signals, { audio: 2, video: 1 });
  assert.equal(log[0].minutes, 4);
});
