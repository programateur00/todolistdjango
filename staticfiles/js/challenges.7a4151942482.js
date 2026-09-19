/**
 * Retos — desafíos de un solo tirón, sin progresión semana a semana
 * detrás (a diferencia de un Plan: ver plan-session.js). Contrapartida
 * web de challenges-view.js (la app móvil) — misma mecánica y mismos
 * guiones (SALLY_*, PULLUPS_*), adaptada a que aquí no hay router SPA
 * (cada reto es una página de Django distinta, ver
 * tasks/templates/tasks/challenge_*.html) y MediaPipe se carga como en
 * circuit.js/plan-session.js (mediapipe-vendor.js), no con el
 * modelAssetBuffer cacheado que usa la app.
 *
 * v1: TODO LOCAL — no se guarda nada en el backend todavía, solo la
 * mejor marca en localStorage de este navegador (ver getBest/setBest).
 * Si esto cuaja, el siguiente paso natural es un endpoint de guardado
 * como routine_save/plan_session_save.
 *
 * Bring Sally Up: NO usa la canción real de Moby (derechos de autor) —
 * en su lugar, una voz propia (speakOut, ya usado en toda la app para
 * TTS) marca "Sube y aguanta" / "Baja y aguanta" con un guion propio
 * (buildSallyScript) que imita la mecánica del reto viral (aguantes
 * cada vez más largos, arriba y abajo alternando) sin copiar tiempos
 * exactos de la canción.
 */
import {
  checkPushupTopHoldPosture, checkPushupBottomHoldPosture,
  speakOut, stopSpeaking, isVoiceEnabled, startWorkout, setQuietVoice,
} from "./workout.js";
import { MEDIAPIPE_BUNDLE_URL, MEDIAPIPE_WASM_BASE_URL, MODEL_URL } from "./mediapipe-vendor.js";

const fmt = (s) => {
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m > 0 ? `${m}:${String(r).padStart(2, "0")}` : String(r);
};

function beep(freq = 880, dur = 0.15) {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = freq;
    osc.connect(gain);
    gain.connect(ctx.destination);
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    osc.start();
    osc.stop(ctx.currentTime + dur);
  } catch {
    /* si el navegador bloquea el audio, seguimos igual */
  }
}

// localStorage puede estar bloqueado (modo privado…) — cada acceso va
// en try/catch, y si falla simplemente no se recuerda la marca entre
// sesiones, sin romper el reto.
const BEST_KEY_PREFIX = "reto_mejor_marca__";
function getBest(id) {
  try {
    return JSON.parse(localStorage.getItem(BEST_KEY_PREFIX + id) || "null");
  } catch {
    return null;
  }
}
function setBest(id, value) {
  try {
    localStorage.setItem(BEST_KEY_PREFIX + id, JSON.stringify(value));
  } catch {
    /* no pasa nada, solo no se guarda la marca */
  }
}

// ------------------------------------------------ Bring Sally Up (flexiones)

/**
 * Guion propio del reto (NO son los tiempos reales de la canción, ver
 * cabecera del archivo). ~30 transiciones en total (SALLY_ROUNDS pares
 * abajo+arriba), empezando cortas — calientan — y alargándose hacia el
 * final, pensado para acabar sobre los 3-3:30 min con los rangos de
 * abajo. Un solo sitio para tocar la dificultad: las tres constantes
 * siguientes. Copia exacta de la misma tabla en la app móvil.
 */
const SALLY_ROUNDS = 15;
const SALLY_DOWN_RANGE_SECONDS = [3, 16]; // aguante ABAJO: ronda 1 → última
const SALLY_UP_RANGE_SECONDS = [2, 6];    // aguante ARRIBA: ronda 1 → última

function buildSallyScript() {
  const script = [];
  for (let i = 0; i < SALLY_ROUNDS; i++) {
    const t = SALLY_ROUNDS > 1 ? i / (SALLY_ROUNDS - 1) : 0;
    const down = Math.round(SALLY_DOWN_RANGE_SECONDS[0] + t * (SALLY_DOWN_RANGE_SECONDS[1] - SALLY_DOWN_RANGE_SECONDS[0]));
    const up = Math.round(SALLY_UP_RANGE_SECONDS[0] + t * (SALLY_UP_RANGE_SECONDS[1] - SALLY_UP_RANGE_SECONDS[0]));
    script.push({ phase: "bottom", seconds: down, cue: "Baja y aguanta" });
    script.push({ phase: "top", seconds: up, cue: "Sube y aguanta" });
  }
  return script;
}

function initSallyPushups(host) {
  const best = getBest("sally-pushups");
  host.innerHTML = `
    <p>
      Réplica del reto viral sin la canción original de Moby (derechos de autor). En su lugar, una
      voz te va marcando "Sube y aguanta" / "Baja y aguanta", con un guion propio que empieza fácil
      y se pone duro hacia el final. Mientras toca aguantar, la cámara comprueba que sigues en
      posición — si te sales, el tiempo de ese tramo se para hasta que vuelvas.
    </p>
    <p>
      Para empezar: <strong>túmbate boca abajo, de perfil a la cámara, con los codos ya doblados</strong>
      (la posición de ABAJO de la flexión, no la de arriba) — el reto arranca justo en
      "Baja y aguanta".
    </p>
    ${
      best
        ? `<p class="plan-card__meta">Tu mejor marca: ${best.roundsCompleted} de ${SALLY_ROUNDS} rondas · ${fmt(best.totalHeldSeconds)} aguantados en total</p>`
        : ""
    }
    <button type="button" class="primary-btn" id="sally-start">Empezar</button>`;
  document.getElementById("sally-start").addEventListener("click", () => runSallyPushups(host));
}

async function runSallyPushups(host) {
  const script = buildSallyScript();
  let phaseIndex = 0;
  let elapsedInPhase = 0;
  let postureOk = false;
  let running = true;
  let totalHeldSeconds = 0;
  let roundsCompleted = 0; // cada 2 fases (bottom+top) = 1 ronda completa
  let stream = null;
  let poseLandmarker = null;
  let tickId = null;
  let waitId = null;
  let lastSpokenSecond = null;

  host.innerHTML = `
    <div class="circuit">
      <p class="circuit__progress" id="sally-progress">Ronda 1 de ${SALLY_ROUNDS}</p>
      <div class="workout__camera">
        <video id="sally-video" playsinline muted class="workout__video"></video>
        <canvas id="sally-canvas" class="workout__canvas"></canvas>
      </div>
      <p id="sally-status" class="workout__status">Colócate: boca abajo, de perfil, codos ya doblados (posición de abajo).</p>
      <p class="circuit__phase" id="sally-cue">—</p>
      <div class="circuit__timer" id="sally-timer">${script[0].seconds}</div>
      <div class="circuit__controls">
        <button type="button" class="workout__btn workout__btn--ghost" id="sally-quit">Terminar antes</button>
      </div>
      <p class="workout__note">El vídeo no sale de tu navegador. El cronómetro de cada tramo se pausa si la postura no es correcta.</p>
    </div>`;

  const statusEl = document.getElementById("sally-status");
  const cueEl = document.getElementById("sally-cue");
  const timerEl = document.getElementById("sally-timer");
  const progressEl = document.getElementById("sally-progress");
  const video = document.getElementById("sally-video");
  const canvas = document.getElementById("sally-canvas");

  const stopCamera = () => {
    running = false;
    clearInterval(tickId);
    clearInterval(waitId);
    if (stream) stream.getTracks().forEach((t) => t.stop());
    if (poseLandmarker) poseLandmarker.close();
    // Sales de la pantalla de la cámara del reto: la voz se calla con
    // ella (ver stopSpeaking() en workout.js).
    stopSpeaking();
  };

  document.getElementById("sally-quit").addEventListener("click", () => {
    if (!confirm("¿Terminar el reto ahora?")) return;
    stopCamera();
    finishSally(host, { roundsCompleted, totalHeldSeconds, quit: true });
  });

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: 1280, height: 720 }, audio: false,
    });
  } catch {
    statusEl.textContent = "No se pudo acceder a la cámara — revisa los permisos del navegador.";
    return;
  }
  video.srcObject = stream;
  await video.play();
  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;

  try {
    const { FilesetResolver, PoseLandmarker } = await import(MEDIAPIPE_BUNDLE_URL);
    const vision = await FilesetResolver.forVisionTasks(MEDIAPIPE_WASM_BASE_URL);
    poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
      baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
      runningMode: "VIDEO", numPoses: 1,
    });
  } catch (err) {
    statusEl.textContent = "No se pudo cargar el seguimiento de postura.";
    console.error(err);
    return;
  }

  const currentChecker = () => (script[phaseIndex].phase === "top" ? checkPushupTopHoldPosture : checkPushupBottomHoldPosture);

  const loop = () => {
    if (!running) return;
    const result = poseLandmarker.detectForVideo(video, performance.now());
    if (result.landmarks && result.landmarks.length) {
      const check = currentChecker()(result.landmarks[0]);
      postureOk = check.ok;
      statusEl.textContent = check.ok ? "Postura correcta — aguanta." : `⚠️ ${check.reason}`;
    } else {
      postureOk = false;
      statusEl.textContent = "No se te ve — sal en el encuadre.";
    }
    requestAnimationFrame(loop);
  };
  loop();

  const speakCue = (text) => {
    cueEl.textContent = text;
    if (isVoiceEnabled()) speakOut(text);
  };

  const advancePhase = () => {
    roundsCompleted = Math.floor((phaseIndex + 1) / 2);
    phaseIndex += 1;
    elapsedInPhase = 0;
    lastSpokenSecond = null;
    if (phaseIndex >= script.length) {
      stopCamera();
      finishSally(host, { roundsCompleted: SALLY_ROUNDS, totalHeldSeconds, quit: false });
      return false;
    }
    progressEl.textContent = `Ronda ${Math.floor(phaseIndex / 2) + 1} de ${SALLY_ROUNDS}`;
    timerEl.textContent = String(script[phaseIndex].seconds);
    speakCue(script[phaseIndex].cue);
    return true;
  };

  function tick() {
    if (!postureOk) return; // pausado mientras la postura no sea correcta
    elapsedInPhase += 1;
    totalHeldSeconds += 1;
    const remaining = script[phaseIndex].seconds - elapsedInPhase;
    if (remaining <= 0) {
      beep(880, 0.15);
      advancePhase();
      return;
    }
    timerEl.textContent = String(remaining);
    if (remaining <= 3) {
      beep(660, 0.1);
      if (isVoiceEnabled() && remaining !== lastSpokenSecond) {
        lastSpokenSecond = remaining;
        speakOut(String(remaining), { flush: false });
      }
    }
  }

  // Espera a que la postura inicial (abajo, fase 0) sea correcta antes de
  // arrancar el guion de verdad — igual que el "armado" de las flexiones
  // contadas (ver processPushup en workout.js), para no empezar a
  // descontar tiempo mientras todavía te estás colocando.
  waitId = setInterval(() => {
    if (!running) { clearInterval(waitId); return; }
    if (postureOk) {
      clearInterval(waitId);
      speakCue(script[0].cue);
      tickId = setInterval(tick, 1000);
    }
  }, 200);
}

function finishSally(host, { roundsCompleted, totalHeldSeconds, quit }) {
  const best = getBest("sally-pushups");
  const isNewBest =
    !best ||
    roundsCompleted > best.roundsCompleted ||
    (roundsCompleted === best.roundsCompleted && totalHeldSeconds > best.totalHeldSeconds);
  if (isNewBest) setBest("sally-pushups", { roundsCompleted, totalHeldSeconds });

  host.innerHTML = `
    <div class="circuit__done">
      <p class="circuit__done-title">${quit ? "Reto cortado" : "¡Reto completado! 💪"}</p>
      <p>${roundsCompleted} de ${SALLY_ROUNDS} rondas · ${fmt(totalHeldSeconds)} aguantados en total</p>
      ${isNewBest ? `<p class="run-pct run-pct--full">🏆 Nueva mejor marca</p>` : ""}
      <button type="button" class="primary-btn" id="sally-retry">Volver a intentarlo</button>
    </div>`;
  document.getElementById("sally-retry").addEventListener("click", () => initSallyPushups(host));
}

// ------------------------------------------------------- 100 dominadas

const PULLUPS_TARGET = 100;
const PULLUPS_REST_SECONDS = 60;
const PULLUPS_SUGGESTED_PER_SET = 5;

function initPullups100(host) {
  const best = getBest("pullups-100");
  host.innerHTML = `
    <p>
      Objetivo: llegar a <strong>${PULLUPS_TARGET} dominadas</strong> en total, en las series que
      quieras (la sugerencia es de ${PULLUPS_SUGGESTED_PER_SET} en ${PULLUPS_SUGGESTED_PER_SET}, pero
      puedes hacer más o menos por serie — lo único que cuenta es el acumulado). Entre serie y
      serie, ${PULLUPS_REST_SECONDS} segundos de descanso obligatorio (con opción de saltarlo si
      quieres seguir antes).
    </p>
    ${
      best
        ? `<p class="plan-card__meta">Tu mejor marca: completado en ${best.sets} serie(s) · ${fmt(best.totalSeconds)}</p>`
        : ""
    }
    <button type="button" class="primary-btn" id="pullups-start">Empezar</button>`;
  document.getElementById("pullups-start").addEventListener("click", () => {
    const state = { totalReps: 0, sets: 0, startedAt: performance.now() };
    runPullupSet(host, state);
  });
}

function runPullupSet(host, state) {
  const remaining = Math.max(PULLUPS_TARGET - state.totalReps, 0);
  const suggestedThisSet = Math.min(PULLUPS_SUGGESTED_PER_SET, remaining) || PULLUPS_SUGGESTED_PER_SET;

  host.innerHTML = `
    <div id="workout-root" class="workout"
         data-save-url="#" data-cancel-url="#" data-exercise-slug="pullup"
         data-counter-key="pullup"
         data-target-sets="1" data-target-reps="${suggestedThisSet}">
      <p class="circuit__progress">Reto: 100 dominadas — llevas ${state.totalReps} de ${PULLUPS_TARGET}</p>
      <h2 class="circuit__exercise-name">Dominadas</h2>
      <p class="run-target">Haz las que quieras en esta serie y pulsa «Terminar serie» cuando acabes.</p>
      <div class="workout__camera">
        <video id="workout-video" playsinline muted class="workout__video"></video>
        <canvas id="workout-canvas" class="workout__canvas"></canvas>
      </div>
      <p id="workout-goal-banner" class="workout__goal-banner" hidden></p>
      <details class="workout__stats-toggle">
        <summary class="workout__stats-summary">Datos</summary>
        <div class="workout__stats">
          <div class="workout__stat"><span class="workout__stat-value" id="workout-reps">0</span><span class="workout__stat-label">reps</span></div>
          <div class="workout__stat"><span class="workout__stat-value" id="workout-sets">1</span><span class="workout__stat-label">serie</span></div>
          <div class="workout__stat"><span class="workout__stat-value" id="workout-timer">0:00</span><span class="workout__stat-label">sesión</span></div>
          <div class="workout__stat"><span class="workout__stat-value" id="workout-rest">0:00</span><span class="workout__stat-label">descanso</span></div>
        </div>
      </details>
      <div class="workout__actions">
        <button type="button" id="workout-cancel" class="workout__btn workout__btn--ghost">Salir del reto</button>
        <button type="button" id="workout-recalibrate" class="workout__btn workout__btn--ghost">↻ Recalibrar</button>
        <button type="button" id="workout-finish" class="workout__btn workout__btn--primary">Terminar serie</button>
      </div>
      <p class="workout__note">El vídeo no sale de tu navegador. Solo se guardan los números.</p>
    </div>`;

  let workoutSession = startWorkout();

  window.__workoutSubmit = async (payload) => {
    const reps = payload.total_reps || 0;
    state.totalReps += reps;
    state.sets += 1;
    workoutSession?.stopCamera?.();
    window.__workoutSubmit = null;
    if (state.totalReps >= PULLUPS_TARGET) {
      finishPullups(host, state);
    } else {
      runPullupRest(host, state, reps);
    }
  };

  document.getElementById("workout-cancel").addEventListener(
    "click",
    (e) => {
      e.stopImmediatePropagation();
      if (!confirm("¿Salir del reto? Se pierde el progreso de esta serie sin guardar.")) return;
      workoutSession?.stopCamera?.();
      window.__workoutSubmit = null;
      window.location.href = document.referrer || "/";
    },
    true
  );
}

function runPullupRest(host, state, lastSetReps) {
  host.innerHTML = `
    <div class="circuit">
      <p class="circuit__progress">Llevas ${state.totalReps} de ${PULLUPS_TARGET} · última serie: ${lastSetReps}</p>
      <h2 class="circuit__exercise-name">Descanso</h2>
      <p class="circuit__phase circuit__phase--rest">Descanso</p>
      <div class="circuit__timer" id="pullups-rest-timer">${fmt(PULLUPS_REST_SECONDS)}</div>
      <p class="circuit__next">Faltan ${PULLUPS_TARGET - state.totalReps} dominadas</p>
      <div class="circuit__controls">
        <button type="button" class="workout__btn workout__btn--ghost" id="pullups-skip-rest">Saltar descanso ▸</button>
      </div>
    </div>`;

  let remaining = PULLUPS_REST_SECONDS;
  const timerEl = document.getElementById("pullups-rest-timer");
  const id = setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      clearInterval(id);
      beep(880, 0.2);
      runPullupSet(host, state);
      return;
    }
    if (remaining <= 3) beep(660, 0.1);
    timerEl.textContent = fmt(remaining);
  }, 1000);

  document.getElementById("pullups-skip-rest").addEventListener("click", () => {
    clearInterval(id);
    runPullupSet(host, state);
  });
}

function finishPullups(host, state) {
  const totalSeconds = Math.round((performance.now() - state.startedAt) / 1000);
  const best = getBest("pullups-100");
  const isNewBest = !best || state.sets < best.sets || (state.sets === best.sets && totalSeconds < best.totalSeconds);
  if (isNewBest) setBest("pullups-100", { sets: state.sets, totalSeconds });

  host.innerHTML = `
    <div class="circuit__done">
      <p class="circuit__done-title">¡100 dominadas completadas! 💪</p>
      <p>${state.sets} serie(s) · ${fmt(totalSeconds)} en total</p>
      ${isNewBest ? `<p class="run-pct run-pct--full">🏆 Nueva mejor marca</p>` : ""}
      <button type="button" class="primary-btn" id="pullups-retry">Volver a intentarlo</button>
    </div>`;
  document.getElementById("pullups-retry").addEventListener("click", () => initPullups100(host));
}

// ------------------------------------------------------- Cindy workout

/**
 * Cindy workout (el circuito de Tom Holland): dominadas → flexiones →
 * sentadillas, una detrás de otra, y vuelta a empezar. MÍNIMO por ronda
 * CINDY_MINS (no se puede pasar al siguiente ejercicio con menos, sí con
 * más), tantas rondas como quepan en CINDY_LIMIT_SECONDS. Flexiones y
 * sentadillas se cuentan DE FRENTE a la cámara (counterKey pushupfront /
 * squatfront, ver workout.js); las dominadas ya eran de frente.
 * Todo local (localStorage), como el resto de retos: borrador para
 * retomar, mejor marca e historial de intentos con las reps de cada
 * serie y ronda.
 */
const CINDY_ID = "cindy";
const CINDY_LIMIT_SECONDS = 20 * 60;
const CINDY_PHASES = [
  { key: "pullups", name: "Dominadas", counter: "pullup", slug: "pullup", min: 5, exit: "Al llegar a 5 pasa solo al siguiente.", say: "Dominadas. A la barra." },
  { key: "pushups", name: "Flexiones", counter: "pushupfront", slug: "push-up", min: 10, exit: "Al llegar a 10 pasa solo al siguiente.", say: "Flexiones. Al suelo." },
  { key: "squats", name: "Sentadillas", counter: "squatfront", slug: "squat", min: 15, exit: "Al llegar a 15 pasa solo a la siguiente ronda.", say: "Sentadillas. Levántate." },
];
const CINDY_HISTORY_KEY = "reto_historial__cindy";

function getCindyHistory() {
  try {
    return JSON.parse(localStorage.getItem(CINDY_HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}
function pushCindyHistory(entry) {
  try {
    const h = getCindyHistory();
    h.unshift(entry);
    localStorage.setItem(CINDY_HISTORY_KEY, JSON.stringify(h.slice(0, 30)));
  } catch {
    /* sin historial, el reto sigue igual */
  }
}

const cindyTotalReps = (rounds) =>
  rounds.reduce((t, r) => t + CINDY_PHASES.reduce((a, p) => a + (r[p.key]?.reps || 0), 0), 0);
const cindyCompleteRounds = (rounds) =>
  rounds.filter((r) => CINDY_PHASES.every((p) => (r[p.key]?.reps || 0) >= p.min)).length;

function initCindy(host) {
  const best = getBest(CINDY_ID);
  const hist = getCindyHistory();
  host.innerHTML = `
    <p>
      El circuito de Tom Holland, en bucle durante <strong>${CINDY_LIMIT_SECONDS / 60} minutos</strong>:
      <strong>${CINDY_PHASES[0].min} dominadas → ${CINDY_PHASES[1].min} flexiones → ${CINDY_PHASES[2].min} sentadillas</strong>
      y vuelta a empezar. Cada ejercicio es <strong>una sola serie con esas repeticiones exactas</strong>: ni más ni menos.
      Al llegar al número pasa solo al siguiente. Si cortas la serie antes (te levantas, sales del encuadre, paras)
      o intentas una segunda serie, <strong>el reto queda fallado</strong>. Cuenta cuántas rondas completas te caben.
    </p>
    <p class="workout__note" style="text-align:left">
      Flexiones: pon el móvil delante de ti (en el suelo o en un trípode alto), ponte de pie mirando a la cámara
      y luego túmbate boca abajo, también mirando a la cámara. Sentadillas: de pie, de frente, con el cuerpo entero
      en el encuadre. El reloj de ${CINDY_LIMIT_SECONDS / 60} min no se para mientras te colocas.
    </p>
    ${
      best
        ? `<p class="plan-card__meta">Tu mejor marca: ${best.rounds} ronda(s) completa(s) · ${best.totalReps} reps en total</p>`
        : ""
    }
    ${
      hist.length
        ? `<p class="plan-card__meta">Últimos intentos: ${hist
            .slice(0, 3)
            .map((h) => `${h.rounds} ronda(s)/${h.totalReps} reps`)
            .join(" · ")}</p>`
        : ""
    }
    <button type="button" class="primary-btn" id="cindy-start">Empezar</button>`;
  document.getElementById("cindy-start").addEventListener("click", () => {
    runCindyPhase(host, {
      rounds: [],
      round: {},
      phaseIdx: 0,
      elapsedMs: 0,
      deadline: Date.now() + CINDY_LIMIT_SECONDS * 1000,
    });
  });
}

function runCindyPhase(host, state) {
  const phase = CINDY_PHASES[state.phaseIdx];
  const roundNo = state.rounds.length + 1;
  const remainingMs = () => Math.max(0, state.deadline - Date.now());
  if (remainingMs() <= 0) {
    finishCindy(host, state);
    return;
  }

  host.innerHTML = `
    <div id="workout-root" class="workout"
         data-save-url="local" data-cancel-url="#" data-exercise-slug="${phase.slug}"
         data-counter-key="${phase.counter}"
         data-target-sets="1" data-target-reps="${phase.min}" data-exact-reps="${phase.min}">
      <p class="circuit__progress">Cindy · ronda ${roundNo} · ejercicio ${state.phaseIdx + 1} de ${CINDY_PHASES.length}
        · <strong id="cindy-clock">${fmt(Math.ceil(remainingMs() / 1000))}</strong> restantes</p>
      <h2 class="circuit__exercise-name">${phase.name}</h2>
      <p class="run-target">Exactamente ${phase.min}, en una sola serie. <span id="cindy-gate"></span><br><small>${phase.exit}</small></p>
      <div class="workout__camera">
        <video id="workout-video" playsinline muted class="workout__video"></video>
        <canvas id="workout-canvas" class="workout__canvas"></canvas>
      </div>
      <p id="workout-goal-banner" class="workout__goal-banner" hidden></p>
      <button type="button" id="workout-debug-export" class="workout__btn workout__btn--ghost">📋 Copiar registro de depuración</button>
      <p id="workout-debug-export-status" class="workout__debug"></p>
      <details class="workout__stats-toggle">
        <summary class="workout__stats-summary">Datos</summary>
        <div class="workout__stats">
        <div class="workout__stat"><span class="workout__stat-value" id="workout-reps">0</span><span class="workout__stat-label">reps</span></div>
        <div class="workout__stat"><span class="workout__stat-value" id="workout-sets">1</span><span class="workout__stat-label">serie</span></div>
        <div class="workout__stat"><span class="workout__stat-value" id="workout-timer">0:00</span><span class="workout__stat-label">sesión</span></div>
        <div class="workout__stat"><span class="workout__stat-value" id="workout-rest">0:00</span><span class="workout__stat-label">descanso</span></div>
        </div>
      </details>
      <div class="workout__actions">
        <button type="button" id="workout-cancel" class="workout__btn workout__btn--ghost">Salir del reto</button>
        <button type="button" id="workout-recalibrate" class="workout__btn workout__btn--ghost">↻ Recalibrar</button>
        <button type="button" id="workout-finish" class="workout__btn workout__btn--primary" disabled>Siguiente ▸</button>
      </div>
      <p class="workout__note">El vídeo no sale de tu móvil. Solo se guardan los números.</p>
    </div>`;

  setQuietVoice(true);
  let workoutSession = startWorkout();
  let tick = null;
  let done = false;
  const finishBtn = document.getElementById("workout-finish");
  const gateEl = document.getElementById("cindy-gate");
  const clockEl = document.getElementById("cindy-clock");
  const lastLabel = state.phaseIdx === CINDY_PHASES.length - 1 ? "Terminar ronda ▸" : "Siguiente ▸";

  const stopAll = () => {
    if (tick) clearInterval(tick);
    tick = null;
    workoutSession?.stopCamera?.();
    window.__currentViewCleanup = null;
    window.__currentViewGuard = null;
    window.__workoutSubmit = null;
  };

  // Reps y series REALES del ejercicio en curso, sin esperar al botón (lo
  // necesita tanto el candado del mínimo como el corte por tiempo).
  const currentResult = () => {
    const s = workoutSession;
    const sets = (s?.sets || []).map((x) => x.reps);
    if ((s?.currentSetReps || 0) > 0) sets.push(s.currentSetReps);
    return { reps: s?.reps || 0, sets };
  };

  const savePhase = (result) => {
    state.round = { ...state.round, [phase.key]: result };
    if (state.phaseIdx === CINDY_PHASES.length - 1) {
      state.rounds = [...state.rounds, state.round];
      state.round = {};
      state.phaseIdx = 0;
    } else {
      state.phaseIdx += 1;
    }
      };

  // Pasar al siguiente ejercicio: por botón, o SIN tocar la pantalla cuando el propio contador
  // cierra la serie (bajar los brazos / levantarte / levantar los brazos) con el mínimo ya hecho.
  const advance = (result) => {
    if (done) return;
    done = true;
    stopAll();
    savePhase(result);
    if (remainingMs() <= 0) finishCindy(host, state);
    else runCindyPhase(host, state);
  };

  window.__currentViewCleanup = () => {
    if (tick) clearInterval(tick);
    setQuietVoice(false);
    workoutSession?.stopCamera?.();
    window.__currentViewGuard = null;
  };

  // El botón «Siguiente» de la sesión llama aquí (solo se puede pulsar con el mínimo hecho).
  window.__workoutSubmit = async (payload) => {
    if (done) return;
    done = true;
    const reps = payload.total_reps || 0;
    const sets = (payload.sets || []).map((x) => x.reps);
    stopAll();
    savePhase({ reps, sets });
    if (remainingMs() <= 0) finishCindy(host, state);
    else runCindyPhase(host, state);
  };

  tick = setInterval(() => {
    if (done) return;
    const left = remainingMs();
    if (clockEl) clockEl.textContent = fmt(Math.ceil(left / 1000));
    const { reps } = currentResult();
    // Serie cerrada (te levantas, sales del encuadre…) con menos de las reps exactas, o una
    // segunda serie: reto fallado.
    const closed = workoutSession?.sets || [];
    if (closed.some((x) => x.reps < phase.min) || closed.length > 1) {
      done = true;
      const r = currentResult();
      beep(220, 0.5);
      stopAll();
      savePhase({ reps: r.reps, sets: r.sets });
      finishCindy(host, state, `${phase.name}: serie de ${closed[0]?.reps ?? r.reps} en vez de ${phase.min}. Es una serie exacta o nada.`);
      return;
    }
    gateEl.textContent = `Llevas ${reps} de ${phase.min}.`;
    // Reps exactas conseguidas: siguiente ejercicio al momento, sin tocar la pantalla.
    if (reps >= phase.min) {
      beep(880, 0.15);
      advance({ reps: phase.min, sets: [phase.min] });
      return;
    }
    if (left <= 0) {
      // Se acabó el tiempo: se guarda lo que haya en este ejercicio (aunque no llegue al mínimo).
      done = true;
      const r = currentResult();
      beep(440, 0.4);
      stopAll();
      savePhase({ reps: r.reps, sets: r.sets });
      finishCindy(host, state);
    }
  }, 250);

  document.getElementById("workout-cancel").addEventListener(
    "click",
    (e) => {
      e.stopImmediatePropagation();
      if (!confirm("¿Salir del reto? Se pierde el progreso.")) return;
      done = true;
      stopAll();
      setQuietVoice(false);
      window.location.href = document.referrer || "/";
    },
    true
  );

  if (isVoiceEnabled()) {
    speakOut(phase.say, { flush: true, force: true });
  }
}

function finishCindy(host, state, failReason = null) {
  setQuietVoice(false);
  const rounds = [...state.rounds];
  if (state.round && Object.keys(state.round).length) rounds.push(state.round); // ronda a medias
  const complete = cindyCompleteRounds(rounds);
  const totalReps = cindyTotalReps(rounds);
  const best = getBest(CINDY_ID);
  const isNewBest = !failReason && (!best || complete > best.rounds || (complete === best.rounds && totalReps > best.totalReps));
  if (isNewBest) setBest(CINDY_ID, { rounds: complete, totalReps });
  pushCindyHistory({ at: Date.now(), rounds: complete, totalReps, detail: rounds, failed: !!failReason });
  if (failReason && isVoiceEnabled()) speakOut("Reto fallido.", { flush: true, force: true });

  const cell = (r, p) => {
    const x = r[p.key];
    if (!x) return "—";
    const sets = x.sets && x.sets.length > 1 ? ` (${x.sets.join("+")})` : "";
    return `${x.reps}${sets}`;
  };
  host.innerHTML = `
    <div class="circuit__done">
      <p class="circuit__done-title">${failReason ? "Reto fallido ❌" : "¡Cindy workout terminado! 💪"}</p>
      ${failReason ? `<p>${String(failReason).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c])}</p>` : ""}
      <p>${complete} ronda(s) completa(s) · ${totalReps} repeticiones en ${CINDY_LIMIT_SECONDS / 60} min</p>
      ${isNewBest ? `<p class="run-pct run-pct--full">🏆 Nueva mejor marca</p>` : ""}
      <table class="plan-table" style="width:100%;text-align:center">
        <thead><tr><th>Ronda</th>${CINDY_PHASES.map((p) => `<th>${p.name}</th>`).join("")}</tr></thead>
        <tbody>${rounds
          .map((r, i) => `<tr><td>${i + 1}</td>${CINDY_PHASES.map((p) => `<td>${cell(r, p)}</td>`).join("")}</tr>`)
          .join("")}</tbody>
      </table>
      <button type="button" class="primary-btn" id="cindy-retry">Volver a intentarlo</button>
    </div>`;
  document.getElementById("cindy-retry").addEventListener("click", () => initCindy(host));
}

// ------------------------------------------------------------- arranque

const sallyHost = document.getElementById("sally-challenge-root");
if (sallyHost) initSallyPushups(sallyHost);

const pullupsHost = document.getElementById("pullups-challenge-root");
if (pullupsHost) initPullups100(pullupsHost);

const cindyHost = document.getElementById("cindy-challenge-root");
if (cindyHost) initCindy(cindyHost);
