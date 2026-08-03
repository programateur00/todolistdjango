/**
 * Reproductor de la sesión de un plan: circuito MIXTO, cronómetro y
 * cámara a la vez. Es la contrapartida web de session-runner.js (la
 * app móvil) — misma idea, mismo formato de datos, adaptado a que aquí
 * los iconos vienen renderizados por Django (no hay exercise-icons.js
 * en la web) y el guardado es un fetch normal con CSRF, no el cliente
 * de API de la app.
 *
 *   - mode "timed"  (plancha, crunch)   -> cuenta atrás
 *   - mode "pose"   (dominadas, fondos) -> cámara contando reps
 *     (el conteo de verdad lo sigue haciendo workout.js sin tocarlo;
 *     aquí solo se le engancha vía window.__workoutSubmit)
 */
(function () {
  "use strict";

  const root = document.getElementById("circuit-root");
  if (!root) return;

  const items = JSON.parse(root.dataset.items || "[]");
  const saveUrl = root.dataset.saveUrl;
  const cancelUrl = root.dataset.cancelUrl;
  const csrfToken = (root.querySelector("[name=csrfmiddlewaretoken]") || {}).value || "";

  const modeSelect = document.getElementById("circuit-mode-select");
  const playerHost = document.getElementById("session-player");

  // Los iconos los renderiza Django (misma fuente que ya usaba
  // circuit.js) — nada de módulos JS con SVGs duplicados.
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

  function runCurrent() {
    const item = current();
    if (!item) return finish();
    if (item.mode === "pose") runCamera(item);
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
        <p class="circuit__next">${hasNext() ? `Siguiente: ${esc(sequence[index + 1].name)}` : "¡Último!"}</p>
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
      if (!confirm("¿Terminar la sesión ahora? Se guarda lo hecho hasta aquí.")) return;
      clearInterval(timerId);
      if (elapsed > 0) record({ exercise: item.slug, seconds: elapsed });
      finish();
    });
  }

  // -------------------------------------------------------------- cámara

  async function runCamera(item) {
    const objetivo = item.target_reps ? `${item.target_sets} × ${item.target_reps}` : `${item.target_sets} × ${item.work}s`;
    const fuente =
      item.target_source === "plan"
        ? `<span class="run-plan">plan «${esc(item.plan_name || "")}» ${item.is_headline ? "★" : ""}</span>`
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

    // workout.js llama a esto al pulsar "Siguiente/Terminar" en vez de
    // guardar y salir por su cuenta: aquí se apunta lo hecho y se pasa
    // al siguiente ejercicio del circuito.
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

    // "Saltar" no debe guardar nada de este ejercicio, solo pasar.
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
        <p class="circuit__done-title">¡Sesión completada! 💪</p>
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
        const resp = await fetch(saveUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
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
