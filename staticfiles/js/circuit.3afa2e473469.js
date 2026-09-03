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
  angle,
  checkPlankPosture, checkSidePlankPosture, checkWallSitPosture,
  checkKneeHoldBarPosture, checkHandstandPosture,
  speakOut, numeroEnPalabras, isVoiceEnabled,
} from "./workout.js";
// De dónde sale MediaPipe (versión + rutas a los ficheros locales)
// vive en un único sitio — ver static/js/mediapipe-vendor.js.
import { MEDIAPIPE_BUNDLE_URL, MEDIAPIPE_WASM_BASE_URL, MODEL_URL } from "./mediapipe-vendor.js";

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
  // checkSidePlankPosture / checkWallSitPosture / checkKneeHoldBarPosture /
  // checkHandstandPosture más abajo.
  const POSTURE_COUNTERS = new Set(["plank", "sideplank", "wallsit", "kneeholdbar", "handstand"]);

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
    let lastSpokenNumber = null; // último entero ya dicho, para no repetirlo en el mismo segundo
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
      // Cuenta atrás dicha en voz alta cada segundo — igual que ya hacía
      // runTimerWithPosture() más abajo (mismo motivo: se pidió poder
      // seguir un ejercicio cronometrado de oído, sin mirar la pantalla,
      // igual que ya se puede con las repeticiones).
      if (isVoiceEnabled() && remaining !== lastSpokenNumber) {
        lastSpokenNumber = remaining;
        speakOut(numeroEnPalabras(remaining));
      }
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

  // checkPlankPosture / checkSidePlankPosture / checkWallSitPosture /
  // checkKneeHoldBarPosture / checkHandstandPosture viven ahora en
  // workout.js (importadas arriba) — se comparten con el entreno suelto
  // de una tarea (plancha, plancha lateral, silla en pared, kneehold en
  // barra y pino ya no dependen solo de estar dentro de un circuito), en
  // vez de mantener la misma comprobación duplicada en dos sitios.

  async function runTimerWithPosture(item) {
    const checker =
      item.counter_key === "sideplank"
        ? checkSidePlankPosture
        : item.counter_key === "wallsit"
        ? checkWallSitPosture
        : item.counter_key === "kneeholdbar"
        ? checkKneeHoldBarPosture
        : item.counter_key === "handstand"
        ? checkHandstandPosture
        : checkPlankPosture;

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
        <p id="run-goal-banner" class="workout__goal-banner" hidden></p>
        <div class="circuit__timer" id="run-timer">${fmt(item.work)}</div>
        <p class="circuit__next">${hasNext() ? `Siguiente: ${esc(sequence[index + 1].name)}` : "¡Último ejercicio!"}</p>
        <div class="circuit__controls">
          <button type="button" class="workout__btn workout__btn--ghost" id="run-skip">Saltar ▸</button>
          <button type="button" class="workout__btn workout__btn--ghost" id="run-quit">Terminar antes</button>
        </div>
        <p class="workout__note">La cuenta atrás se pausa sola mientras la postura no sea correcta. Si sigues después del objetivo, sigue sumando por encima del 100%.</p>
      </div>`;

    // OJO: a diferencia de antes, llegar a item.work YA NO cierra el
    // ejercicio solo — antes remaining llegaba a 0 y se cerraba la serie
    // de golpe, así que nunca se podía aguantar más del objetivo (ni
    // aunque quisieras). Ahora, igual que en dominadas/fondos (sigue
    // contando por encima del 100% si quieres, se guarda tal cual), el
    // cronómetro pasa a contar hacia ADELANTE los segundos de propina y
    // eres tú quien decide cuándo parar con "Saltar"/"Terminar antes".
    let elapsed = 0;
    let postureOk = false;
    let goalReached = false;
    let lastSpokenNumber = null; // último entero (cuenta atrás o adelante) ya dicho, para no repetirlo en el mismo segundo
    let running = true;
    let stream = null;
    let poseLandmarker = null;
    const timerEl = document.getElementById("run-timer");
    const statusEl = document.getElementById("posture-status");
    const goalBannerEl = document.getElementById("run-goal-banner");
    const skipBtn = document.getElementById("run-skip");
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

    skipBtn.addEventListener("click", () => {
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
        // Misma resolución que workout.js (ver ahí el porqué): 1280x720
        // en vez de 640x480, para que el seguimiento no se degrade a
        // cierta distancia de la cámara.
        video: { facingMode: "user", width: 1280, height: 720 }, audio: false,
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
        const { FilesetResolver, PoseLandmarker } = await import(MEDIAPIPE_BUNDLE_URL);
        const vision = await FilesetResolver.forVisionTasks(MEDIAPIPE_WASM_BASE_URL);
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
      elapsed += 1;

      if (!goalReached && elapsed < item.work) {
        // Cuenta atrás normal hacia el objetivo — igual que antes, pero
        // ahora además dicha en voz alta cada segundo (como cada
        // repetición en dominadas/fondos), para poder seguir sin mirar
        // la pantalla.
        const remaining = item.work - elapsed;
        timerEl.textContent = fmt(remaining);
        if (remaining <= 3) beep(660, 0.1);
        if (isVoiceEnabled() && remaining !== lastSpokenNumber) {
          lastSpokenNumber = remaining;
          speakOut(numeroEnPalabras(remaining));
        }
        return;
      }

      if (!goalReached) {
        // Objetivo alcanzado justo este segundo — un aviso, una sola vez,
        // y sin cortar nada (el ejercicio sigue: ya no se cierra solo).
        goalReached = true;
        lastSpokenNumber = 0;
        beep(880, 0.2);
        if (isVoiceEnabled()) speakOut("¡Objetivo cumplido!", { flush: false });
        if (goalBannerEl) {
          goalBannerEl.hidden = false;
          goalBannerEl.textContent = `🎯 ¡Objetivo cumplido! (${fmt(item.work)}) Sigue si quieres, o termina cuando acabes.`;
        }
        // "Saltar" ya no describe bien lo que hace este botón una vez
        // cumplido el objetivo (no se está saltando nada) — mismo texto
        // que usa workout.js para el botón equivalente en reps.
        skipBtn.textContent = hasNext() ? "Siguiente ▸" : "Terminar";
        timerEl.textContent = "+0";
        return;
      }

      // Por encima del objetivo: cuenta hacia ADELANTE los segundos de
      // propina, igual que seguir oyendo "9", "10" al pasarte de un
      // objetivo de 8 dominadas — así se nota de oído que vas por encima
      // del 100% (y se guarda tal cual: ver finish(), el % de logro ya
      // sabe compararlo contra item.work).
      const over = elapsed - item.work;
      timerEl.textContent = `+${fmt(over)}`;
      if (isVoiceEnabled() && over !== lastSpokenNumber) {
        lastSpokenNumber = over;
        speakOut(numeroEnPalabras(over));
      }
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
        <p id="workout-goal-banner" class="workout__goal-banner" hidden></p>
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
              // Porcentaje conseguido sobre el objetivo, si lo había. Para
              // reps es sobre el volumen total (sets × reps); para
              // cronometrados (plancha, plancha lateral…) es sobre el
              // objetivo de ESE tramo (item.work) — aquí no hay "series"
              // que sumar, cada aparición en el circuito es un aguante
              // suelto, y ahora puede superar el objetivo (ver
              // runTimerWithPosture, ya no se corta solo al llegar).
              let pct = "";
              if (item?.target_sets && item?.target_reps && b.reps) {
                const meta = item.target_sets * item.target_reps;
                const logro = Math.round((100 * b.reps) / meta);
                const clase = logro >= 100 ? "run-pct--full" : "run-pct--partial";
                pct = `<span class="run-pct ${clase}">${logro}%</span>`;
              } else if (item?.work && b.seconds) {
                const logro = Math.round((100 * b.seconds) / item.work);
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
