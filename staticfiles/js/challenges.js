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
  speakOut, stopSpeaking, isVoiceEnabled, startWorkout,
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
      <div class="workout__stats">
        <div class="workout__stat"><span class="workout__stat-value" id="workout-reps">0</span><span class="workout__stat-label">reps</span></div>
        <div class="workout__stat"><span class="workout__stat-value" id="workout-sets">1</span><span class="workout__stat-label">serie</span></div>
        <div class="workout__stat"><span class="workout__stat-value" id="workout-timer">0:00</span><span class="workout__stat-label">sesión</span></div>
        <div class="workout__stat"><span class="workout__stat-value" id="workout-rest">0:00</span><span class="workout__stat-label">descanso</span></div>
      </div>
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

// ------------------------------------------------------------- arranque

const sallyHost = document.getElementById("sally-challenge-root");
if (sallyHost) initSallyPushups(sallyHost);

const pullupsHost = document.getElementById("pullups-challenge-root");
if (pullupsHost) initPullups100(pullupsHost);
