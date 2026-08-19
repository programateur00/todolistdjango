/**
 * Reproductor de circuitos: cronómetro, cámara contando reps, o
 * cronómetro CON cámara comprobando la postura (plancha, plancha
 * lateral) — cada ejercicio se juega con lo que le toca:
 *
 *   - mode "timed", sin counter_key (bicicleta…)   -> cuenta atrás a secas
 *   - mode "timed", con counter_key (plancha…)     -> cuenta atrás + cámara
 *     verificando la postura, pausada mientras la postura no es válida
 *   - mode "pose" (dominadas, fondos, crunch…)     -> cámara contando reps
 *     (el conteo de verdad lo sigue haciendo workout.js sin tocarlo; aquí
 *     solo se le engancha vía window.__workoutSubmit)
 *
 * Es la contrapartida de session-runner.js (la app móvil) y comparte
 * estructura con plan-session.js (la sesión de un plan, aquí en la
 * web) — mismo formato de datos, pero esto reproduce una Routine
 * armada a mano, no los objetivos de un plan.
 */
import {
  NOSE, L_SHOULDER, R_SHOULDER, L_HIP, R_HIP, L_ANKLE, R_ANKLE, L_WRIST, R_WRIST,
  angle, MEDIAPIPE_VERSION, MODEL_URL,
} from "./workout.js";

(function () {
  "use strict";

  const root = document.getElementById("circuit-root");
  if (!root) return;

  const items = JSON.parse(root.dataset.items || "[]");
  const saveUrl = root.dataset.saveUrl;
  const cancelUrl = root.dataset.cancelUrl;

  const modeSelect = document.getElementById("circuit-mode-select");
  const playerHost = document.getElementById("circuit-player");

  const iconMap = {};
  const iconsHost = document.getElementById("circuit-icons");
  if (iconsHost) {
    iconsHost.querySelectorAll("[data-slug]").forEach((div) => {
      iconMap[div.dataset.slug] = div.innerHTML;
    });
  }
  const iconFor = (slug) => iconMap[slug] || iconMap.generic || "";

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function beep(freq, duration) {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.frequency.value = freq || 880;
      osc.connect(gain);
      gain.connect(ctx.destination);
      gain.gain.setValueAtTime(0.15, ctx.currentTime);
      osc.start();
      osc.stop(ctx.currentTime + (duration || 0.15));
    } catch (e) {
      /* si el navegador bloquea audio sin interacción previa, no pasa nada */
    }
  }

  function fmt(s) {
    const m = Math.floor(s / 60);
    const r = s % 60;
    return m > 0 ? `${m}:${String(r).padStart(2, "0")}` : String(r);
  }

  function shuffle(arr) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  let sequence = [];
  let index = 0;
  let breakdown = [];
  let timerId = null;
  let paused = false;
  let workoutSession = null;

  function current() {
    return sequence[index];
  }
  function hasNext() {
    return index < sequence.length - 1;
  }
  function progressLabel() {
    return `Ejercicio ${index + 1} de ${sequence.length}`;
  }
  function record(entry) {
    breakdown.push(entry);
  }

  // Ejercicios cronometrados que además llevan cámara: comprueban
  // postura en vez de contar repeticiones. Ver checkPlankPosture /
  // checkSidePlankPosture más abajo.
  const POSTURE_COUNTERS = new Set(["plank", "sideplank"]);

  function runCurrent() {
    const item = current();
    if (!item) return finish();
    if (item.mode === "pose") runCamera(item);
    else if (POSTURE_COUNTERS.has(item.counter_key)) runTimerWithPosture(item);
    else runTimer(item);
  }

  // -------------------------------------------------------- cronómetro

  function runTimer(item) {
    playerHost.innerHTML = `
      <div class="circuit">
        <p class="circuit__progress">${esc(progressLabel())}</p>
        <div class="circuit__icon">${iconFor(item.slug)}</div>
        <h2 class="circuit__exercise-name">${esc(item.name)}</h2>
        <p class="circuit__phase circuit__phase--work">Trabajo</p>
        <div class="circuit__timer" id="run-timer">${fmt(item.work)}</div>
        <p class="circuit__next">${hasNext() ? `Siguiente: ${esc(sequence[index + 1].name)}` : "¡Último ejercicio!"}</p>
        <div class="circuit__controls">
          <button type="button" class="workout__btn workout__btn--ghost" id="run-pause">Pausar</button>
          <button type="button" class="workout__btn workout__btn--ghost" id="run-skip">Saltar ▸</button>
          <button type="button" class="workout__btn workout__btn--ghost" id="run-quit">Terminar antes</button>
        </div>
      </div>`;

    let remaining = item.work;
    let elapsed = 0;
    const timerEl = document.getElementById("run-timer");
    paused = false;

    clearInterval(timerId);
    timerId = setInterval(() => {
      if (paused) return;
      remaining -= 1;
      elapsed += 1;
      if (remaining <= 0) {
        clearInterval(timerId);
        record({ exercise: item.slug, seconds: item.work });
        beep(880, 0.2);
        advance();
        return;
      }
      if (remaining <= 3) beep(660, 0.1);
      timerEl.textContent = fmt(remaining);
    }, 1000);

    const pauseBtn = document.getElementById("run-pause");
    pauseBtn.addEventListener("click", () => {
      paused = !paused;
      pauseBtn.textContent = paused ? "Reanudar" : "Pausar";
    });
    document.getElementById("run-skip").addEventListener("click", () => {
      clearInterval(timerId);
      if (elapsed > 0) record({ exercise: item.slug, seconds: elapsed });
      advance();
    });
    document.getElementById("run-quit").addEventListener("click", () => {
      if (!confirm("¿Terminar el circuito ahora? Se guarda lo hecho hasta aquí.")) return;
      clearInterval(timerId);
      if (elapsed > 0) record({ exercise: item.slug, seconds: elapsed });
      finish();
    });
  }

  // --------------------------------------- cronómetro + postura (plancha)

  /**
   * LIMITACIÓN CONOCIDA: MediaPipe Pose da la posición 2D de los
   * landmarks, no hacia dónde mira la cara — "la nariz boca abajo" no
   * se puede comprobar tal cual. Se aproxima con la nariz sin subir
   * por encima de la línea de hombros (cabeza no levantada mirando al
   * frente) + cuerpo en línea recta + los brazos apoyados. Es una
   * aproximación razonable, no una detección exacta de hacia dónde
   * miras.
   */
  const PLANK_LINE_MIN_DEG = 155;      // hombro-cadera-tobillo casi recto
  const PLANK_HEAD_UP_MARGIN = 0.15;   // cuánto puede subir la nariz sobre el hombro (proporción al ancho de hombros) antes de contar como "cabeza levantada"
  const PLANK_ARMS_DOWN_MARGIN = 0.05; // las muñecas deben quedar a la altura del hombro o por debajo
  const PLANK_MIN_VISIBILITY = 0.4;

  const SIDEPLANK_HIP_TOUCH_FACTOR = 0.35; // cuánto puede estar la muñeca "de arriba" lejos de la cadera y seguir contando como apoyada
  const SIDEPLANK_LINE_MIN_DEG = 145;      // algo más laxo que la plancha normal: la cadera sube un poco de forma natural
  const SIDEPLANK_MIN_VISIBILITY = 0.4;

  function checkPlankPosture(lm) {
    const nose = lm[NOSE];
    const lS = lm[L_SHOULDER], rS = lm[R_SHOULDER];
    const lH = lm[L_HIP], rH = lm[R_HIP];
    const lA = lm[L_ANKLE], rA = lm[R_ANKLE];
    const lW = lm[L_WRIST], rW = lm[R_WRIST];

    if ([nose, lS, rS, lH, rH, lA, rA, lW, rW].some((p) => (p.visibility ?? 1) < PLANK_MIN_VISIBILITY)) {
      return { ok: false, reason: "No se te ve entera/o. Ponte de perfil a la cámara, con todo el cuerpo en el encuadre." };
    }

    const shoulderWidth = Math.hypot(lS.x - rS.x, lS.y - rS.y) || 1;
    const shoulderMidY = (lS.y + rS.y) / 2;
    const wristMidY = (lW.y + rW.y) / 2;

    const leftVis = (lS.visibility ?? 1) + (lH.visibility ?? 1) + (lA.visibility ?? 1);
    const rightVis = (rS.visibility ?? 1) + (rH.visibility ?? 1) + (rA.visibility ?? 1);
    const useLeft = leftVis >= rightVis;
    const lineAngle = angle(useLeft ? lS : rS, useLeft ? lH : rH, useLeft ? lA : rA);
    if (lineAngle === null || lineAngle < PLANK_LINE_MIN_DEG) {
      return { ok: false, reason: "Cadera desalineada — mantén el cuerpo en línea recta, de los hombros a los tobillos." };
    }
    if ((shoulderMidY - nose.y) / shoulderWidth > PLANK_HEAD_UP_MARGIN) {
      return { ok: false, reason: "Baja la cabeza — mira al suelo, no al frente." };
    }
    if ((wristMidY - shoulderMidY) / shoulderWidth < -PLANK_ARMS_DOWN_MARGIN) {
      return { ok: false, reason: "Apoya los dos brazos en el suelo." };
    }
    return { ok: true };
  }

  function checkSidePlankPosture(lm) {
    const lS = lm[L_SHOULDER], rS = lm[R_SHOULDER];
    const lH = lm[L_HIP], rH = lm[R_HIP];
    const lA = lm[L_ANKLE], rA = lm[R_ANKLE];
    const lW = lm[L_WRIST], rW = lm[R_WRIST];

    if ([lS, rS, lH, rH, lA, rA, lW, rW].some((p) => (p.visibility ?? 1) < SIDEPLANK_MIN_VISIBILITY)) {
      return { ok: false, reason: "No se te ve entera/o. Encuadra todo el cuerpo." };
    }

    const shoulderWidth = Math.hypot(lS.x - rS.x, lS.y - rS.y) || 1;
    // El brazo de apoyo es el que queda más abajo en la imagen (mayor "y").
    const leftIsDown = lW.y > rW.y;
    const downWrist = leftIsDown ? lW : rW;
    const upWrist = leftIsDown ? rW : lW;
    const upHip = leftIsDown ? rH : lH;
    const downShoulder = leftIsDown ? lS : rS;
    const downHip = leftIsDown ? lH : rH;
    const downAnkle = leftIsDown ? lA : rA;

    const lineAngle = angle(downShoulder, downHip, downAnkle);
    if (lineAngle === null || lineAngle < SIDEPLANK_LINE_MIN_DEG) {
      return { ok: false, reason: "Cadera desalineada — mantén el cuerpo en línea recta." };
    }
    const handToHip = Math.hypot(upWrist.x - upHip.x, upWrist.y - upHip.y) / shoulderWidth;
    if (handToHip > SIDEPLANK_HIP_TOUCH_FACTOR) {
      return { ok: false, reason: "Apoya la mano de arriba en la cadera." };
    }
    if ((downWrist.y - downShoulder.y) / shoulderWidth < PLANK_ARMS_DOWN_MARGIN) {
      return { ok: false, reason: "Apoya el brazo de abajo en el suelo." };
    }
    return { ok: true };
  }

  async function runTimerWithPosture(item) {
    const checker = item.counter_key === "sideplank" ? checkSidePlankPosture : checkPlankPosture;

    playerHost.innerHTML = `
      <div class="circuit">
        <p class="circuit__progress">${esc(progressLabel())}</p>
        <h2 class="circuit__exercise-name">${esc(item.name)}</h2>
        <p class="circuit__phase circuit__phase--work">Trabajo</p>
        <div class="workout__camera">
          <video id="posture-video" playsinline muted class="workout__video"></video>
          <canvas id="posture-canvas" class="workout__canvas"></canvas>
        </div>
        <p id="posture-status" class="workout__status">Preparando la cámara…</p>
        <div class="circuit__timer" id="run-timer">${fmt(item.work)}</div>
        <p class="circuit__next">${hasNext() ? `Siguiente: ${esc(sequence[index + 1].name)}` : "¡Último ejercicio!"}</p>
        <div class="circuit__controls">
          <button type="button" class="workout__btn workout__btn--ghost" id="run-skip">Saltar ▸</button>
          <button type="button" class="workout__btn workout__btn--ghost" id="run-quit">Terminar antes</button>
        </div>
        <p class="workout__note">La cuenta atrás se pausa sola mientras la postura no sea correcta.</p>
      </div>`;

    let remaining = item.work;
    let elapsed = 0;
    let postureOk = false;
    let running = true;
    let stream = null;
    let poseLandmarker = null;
    const timerEl = document.getElementById("run-timer");
    const statusEl = document.getElementById("posture-status");
    const video = document.getElementById("posture-video");
    const canvas = document.getElementById("posture-canvas");

    function stopCamera() {
      running = false;
      if (stream) stream.getTracks().forEach((t) => t.stop());
      if (poseLandmarker) poseLandmarker.close();
    }

    function finishThis(secondsHeld) {
      clearInterval(timerId);
      stopCamera();
      record({ exercise: item.slug, seconds: secondsHeld });
    }

    document.getElementById("run-skip").addEventListener("click", () => {
      finishThis(elapsed);
      advance();
    });
    document.getElementById("run-quit").addEventListener("click", () => {
      if (!confirm("¿Terminar el circuito ahora? Se guarda lo hecho hasta aquí.")) return;
      finishThis(elapsed);
      finish();
    });

    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: 640, height: 480 }, audio: false,
      });
    } catch (err) {
      statusEl.textContent = "No se pudo acceder a la cámara — revisa los permisos del navegador. La cuenta atrás sigue sin comprobar la postura.";
      postureOk = true; // sin cámara, no bloquea el ejercicio — degrada a cronómetro normal
    }

    if (stream) {
      video.srcObject = stream;
      await video.play();
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;

      try {
        const { FilesetResolver, PoseLandmarker } = await import(
          `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE_VERSION}`
        );
        const vision = await FilesetResolver.forVisionTasks(
          `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE_VERSION}/wasm`
        );
        poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
          baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
          runningMode: "VIDEO", numPoses: 1,
        });
      } catch (err) {
        statusEl.textContent = "No se pudo cargar el seguimiento de postura. La cuenta atrás sigue sin comprobarla.";
        postureOk = true;
        console.error(err);
      }

      if (poseLandmarker) {
        const loop = () => {
          if (!running) return;
          const result = poseLandmarker.detectForVideo(video, performance.now());
          if (result.landmarks && result.landmarks.length) {
            const check = checker(result.landmarks[0]);
            postureOk = check.ok;
            statusEl.textContent = check.ok ? "Postura correcta — aguanta." : `⚠️ ${check.reason}`;
          } else {
            postureOk = false;
            statusEl.textContent = "No se te ve — sal en el encuadre.";
          }
          requestAnimationFrame(loop);
        };
        loop();
      }
    }

    clearInterval(timerId);
    timerId = setInterval(() => {
      if (!postureOk) return; // pausado mientras la postura no sea válida
      remaining -= 1;
      elapsed += 1;
      if (remaining <= 0) {
        finishThis(item.work);
        beep(880, 0.2);
        advance();
        return;
      }
      if (remaining <= 3) beep(660, 0.1);
      timerEl.textContent = fmt(remaining);
    }, 1000);
  }

  // -------------------------------------------------------------- cámara

  async function runCamera(item) {
    const objetivo = item.target_reps ? `${item.target_sets} × ${item.target_reps}` : `${item.target_sets} × ${item.work}s`;
    const fuente =
      item.target_source === "plan"
        ? `<span class="run-plan">plan «${esc(item.plan_name || "")}»</span>`
        : "";
    playerHost.innerHTML = `
      <div id="workout-root" class="workout"
           data-save-url="local" data-cancel-url="#" data-exercise-slug="${esc(item.slug)}"
           data-target-sets="${item.target_sets || ""}" data-target-reps="${item.target_reps || ""}"
           data-counter-key="${esc(item.counter_key || "pullup")}">
        <p class="circuit__progress">${esc(progressLabel())}</p>
        <h2 class="circuit__exercise-name">${esc(item.name)}</h2>
        <p class="run-target">Objetivo: <strong>${objetivo}</strong> ${fuente}</p>
        <div class="workout__camera">
          <video id="workout-video" playsinline muted class="workout__video"></video>
          <canvas id="workout-canvas" class="workout__canvas"></canvas>
        </div>
        <p id="workout-status" class="workout__status">Iniciando…</p>
        <p id="workout-goal-banner" class="workout__goal-banner" hidden></p>
        <p id="workout-debug" class="workout__debug"></p>
        <div class="workout__stats">
          <div class="workout__stat"><span class="workout__stat-value" id="workout-reps">0</span><span class="workout__stat-label">reps</span></div>
          <div class="workout__stat"><span class="workout__stat-value" id="workout-sets">1</span><span class="workout__stat-label">serie</span></div>
          <div class="workout__stat"><span class="workout__stat-value" id="workout-timer">0:00</span><span class="workout__stat-label">sesión</span></div>
          <div class="workout__stat"><span class="workout__stat-value" id="workout-rest">0:00</span><span class="workout__stat-label">descanso</span></div>
        </div>
        <div class="workout__actions">
          <button type="button" id="workout-cancel" class="workout__btn workout__btn--ghost">Saltar</button>
          <button type="button" id="workout-recalibrate" class="workout__btn workout__btn--ghost">↻ Recalibrar</button>
          <button type="button" id="workout-finish" class="workout__btn workout__btn--primary">
            ${hasNext() ? "Siguiente ▸" : "Terminar"}
          </button>
        </div>
        <p class="workout__note">El vídeo no sale de tu navegador. Solo se guardan los números.</p>
      </div>`;

    window.__workoutSubmit = async (payload) => {
      record({
        exercise: item.slug,
        reps: payload.total_reps || 0,
        sets: payload.total_sets || 0,
        seconds: payload.session_duration_seconds || 0,
      });
      beep(880, 0.2);
      advance();
    };

    window.__LIBRETA_EMBEDDED__ = true;
    const { startWorkout } = await import("./workout.js");
    workoutSession = startWorkout();

    document.getElementById("workout-cancel").addEventListener(
      "click",
      (e) => {
        e.stopImmediatePropagation();
        workoutSession?.stopCamera?.();
        window.__workoutSubmit = null;
        advance();
      },
      true
    );
  }

  // ---------------------------------------------------------------- flujo

  function advance() {
    const item = current();
    index += 1;
    if (index >= sequence.length) return finish();
    const rest = item?.rest ?? 0;
    if (rest > 0) runRest(rest);
    else runCurrent();
  }

  function runRest(seconds) {
    const next = current();
    playerHost.innerHTML = `
      <div class="circuit">
        <p class="circuit__progress">${esc(progressLabel())}</p>
        <div class="circuit__icon circuit__icon--next">${iconFor(next.slug)}</div>
        <h2 class="circuit__exercise-name">Descanso</h2>
        <p class="circuit__phase circuit__phase--rest">Descanso</p>
        <div class="circuit__timer" id="run-timer">${fmt(seconds)}</div>
        <p class="circuit__next">Siguiente: ${esc(next.name)}</p>
        <div class="circuit__controls">
          <button type="button" class="workout__btn workout__btn--ghost" id="run-skip-rest">Saltar descanso ▸</button>
        </div>
      </div>`;

    let remaining = seconds;
    const timerEl = document.getElementById("run-timer");
    clearInterval(timerId);
    timerId = setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        clearInterval(timerId);
        beep(880, 0.2);
        runCurrent();
        return;
      }
      if (remaining <= 3) beep(660, 0.1);
      timerEl.textContent = fmt(remaining);
    }, 1000);

    document.getElementById("run-skip-rest").addEventListener("click", () => {
      clearInterval(timerId);
      runCurrent();
    });
  }

  function finish() {
    clearInterval(timerId);
    window.__workoutSubmit = null;
    workoutSession?.stopCamera?.();

    const totalReps = breakdown.reduce((a, b) => a + (b.reps || 0), 0);
    const totalSecs = breakdown.reduce((a, b) => a + (b.seconds || 0), 0);

    playerHost.innerHTML = `
      <div class="circuit__done">
        <p class="circuit__done-title">¡Circuito completado! 💪</p>
        <p>${breakdown.length} ejercicio(s)${totalReps ? ` · ${totalReps} repeticiones` : ""} · ${fmt(totalSecs)}</p>
        <ul class="run-summary">
          ${breakdown
            .map((b) => {
              const item = sequence.find((i) => i.slug === b.exercise);
              const detail = b.reps ? `${b.reps} reps en ${b.sets} serie(s)` : `${b.seconds}s`;
              let pct = "";
              if (item?.target_sets && item?.target_reps && b.reps) {
                const meta = item.target_sets * item.target_reps;
                const logro = Math.round((100 * b.reps) / meta);
                const clase = logro >= 100 ? "run-pct--full" : "run-pct--partial";
                pct = `<span class="run-pct ${clase}">${logro}%</span>`;
              }
              return `<li><span>${esc(item?.name || b.exercise)}</span><span>${detail} ${pct}</span></li>`;
            })
            .join("")}
        </ul>
        <button type="button" class="primary-btn" id="run-save">Guardar y volver</button>
      </div>`;

    document.getElementById("run-save").addEventListener("click", async (e) => {
      e.target.disabled = true;
      e.target.textContent = "Guardando…";
      try {
        const csrfInput = root.querySelector("[name=csrfmiddlewaretoken]");
        const resp = await fetch(saveUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrfInput ? csrfInput.value : "" },
          body: JSON.stringify({ breakdown }),
        });
        const data = await resp.json();
        window.location.href = (data && data.redirect_url) || cancelUrl;
      } catch (err) {
        e.target.disabled = false;
        e.target.textContent = "Guardar y volver";
        alert("No se pudo guardar. Revisa la conexión e inténtalo otra vez.");
      }
    });
  }

  function begin(randomize) {
    if (!items.length) return;
    sequence = randomize ? shuffle(items) : items.slice();
    index = 0;
    breakdown = [];
    modeSelect.hidden = true;
    playerHost.hidden = false;
    runCurrent();
  }

  document.getElementById("circuit-start-order").addEventListener("click", () => begin(false));
  document.getElementById("circuit-start-random").addEventListener("click", () => begin(true));
})();
