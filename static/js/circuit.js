/**
 * Reproductor de circuitos cronometrados (abdominales tipo Freeletics).
 * Nada de cámara ni MediaPipe aquí — es solo un cronómetro con estados
 * work/rest encadenando los ejercicios de una Routine. Completamente
 * independiente de workout.js: no comparten código ni estado.
 */
(function () {
  "use strict";

  const root = document.getElementById("circuit-root");
  if (!root) return;

  const items = JSON.parse(root.dataset.items || "[]");
  const saveUrl = root.dataset.saveUrl;
  const cancelUrl = root.dataset.cancelUrl;

  const modeSelect = document.getElementById("circuit-mode-select");
  const playerEl = document.getElementById("circuit-player");
  const doneEl = document.getElementById("circuit-done");
  const progressEl = document.getElementById("circuit-progress");
  const iconEl = document.getElementById("circuit-icon");
  const nameEl = document.getElementById("circuit-exercise-name");
  const phaseEl = document.getElementById("circuit-phase");
  const timerEl = document.getElementById("circuit-timer");
  const nextEl = document.getElementById("circuit-next");
  const pauseBtn = document.getElementById("circuit-pause");
  const skipBtn = document.getElementById("circuit-skip");
  const quitBtn = document.getElementById("circuit-quit");
  const finishBtn = document.getElementById("circuit-finish");
  const summaryEl = document.getElementById("circuit-done-summary");

  const iconMap = {};
  const iconsHost = document.getElementById("circuit-icons");
  if (iconsHost) {
    iconsHost.querySelectorAll("[data-slug]").forEach((div) => {
      iconMap[div.dataset.slug] = div.innerHTML;
    });
  }

  let sequence = [];
  let index = 0;
  let phase = "work"; // "work" | "rest"
  let remaining = 0;
  let timerId = null;
  let paused = false;
  let breakdown = [];
  let workElapsedForCurrent = 0;

  function shuffle(arr) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      const tmp = a[i];
      a[i] = a[j];
      a[j] = tmp;
    }
    return a;
  }

  // Pitido corto vía WebAudio. Autocontenido a propósito: no se toca ni
  // se comparte nada de workout.js.
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
      // Si el navegador bloquea audio sin interacción previa, no pasa nada.
    }
  }

  function formatTime(s) {
    const m = Math.floor(s / 60);
    const r = s % 60;
    return m > 0 ? `${m}:${String(r).padStart(2, "0")}` : `${r}`;
  }

  function renderIcon(slug) {
    iconEl.innerHTML = iconMap[slug] || iconMap.generic || "";
  }

  function hasNext() {
    return index < sequence.length - 1;
  }

  function updateProgress() {
    progressEl.textContent = `Ejercicio ${index + 1} de ${sequence.length}`;
  }

  function updateNext() {
    if (phase === "work") {
      if (hasNext() && sequence[index].rest > 0) {
        nextEl.textContent = `Luego: descanso ${sequence[index].rest}s`;
      } else if (hasNext()) {
        nextEl.textContent = `Siguiente: ${sequence[index + 1].name}`;
      } else {
        nextEl.textContent = "¡Último ejercicio!";
      }
    } else {
      nextEl.textContent = hasNext() ? `Siguiente: ${sequence[index + 1].name}` : "";
    }
  }

  function startPhase() {
    const current = sequence[index];
    updateProgress();
    if (phase === "work") {
      nameEl.textContent = current.name;
      phaseEl.textContent = "Trabajo";
      phaseEl.className = "circuit__phase circuit__phase--work";
      renderIcon(current.slug);
      remaining = current.work;
      workElapsedForCurrent = 0;
    } else {
      nameEl.textContent = "Descanso";
      phaseEl.textContent = "Descanso";
      phaseEl.className = "circuit__phase circuit__phase--rest";
      renderIcon("generic");
      remaining = current.rest;
    }
    updateNext();
    timerEl.textContent = formatTime(remaining);
    clearInterval(timerId);
    timerId = setInterval(tick, 1000);
  }

  function tick() {
    if (paused) return;
    remaining -= 1;
    if (phase === "work") workElapsedForCurrent += 1;
    if (remaining <= 0) {
      advance();
      return;
    }
    if (remaining <= 3) beep(660, 0.1);
    timerEl.textContent = formatTime(remaining);
  }

  function advance() {
    if (phase === "work") {
      breakdown.push({ exercise: sequence[index].slug, seconds: sequence[index].work });
      if (hasNext() && sequence[index].rest > 0) {
        phase = "rest";
        beep(440, 0.2);
        startPhase();
        return;
      }
    }
    index += 1;
    if (index >= sequence.length) {
      finish();
      return;
    }
    phase = "work";
    beep(880, 0.2);
    startPhase();
  }

  function skip() {
    if (phase === "work" && workElapsedForCurrent > 0) {
      breakdown.push({ exercise: sequence[index].slug, seconds: workElapsedForCurrent });
    }
    clearInterval(timerId);
    if (phase === "work" && hasNext() && sequence[index].rest > 0) {
      phase = "rest";
      startPhase();
      return;
    }
    index += 1;
    if (index >= sequence.length) {
      finish();
      return;
    }
    phase = "work";
    startPhase();
  }

  function quit() {
    if (phase === "work" && workElapsedForCurrent > 0) {
      breakdown.push({ exercise: sequence[index].slug, seconds: workElapsedForCurrent });
    }
    finish();
  }

  function finish() {
    clearInterval(timerId);
    playerEl.hidden = true;
    doneEl.hidden = false;
    const totalSeconds = breakdown.reduce((a, b) => a + b.seconds, 0);
    summaryEl.textContent = `${breakdown.length} ejercicio(s) — ${formatTime(totalSeconds)} en total.`;
    beep(1046, 0.3);
  }

  function begin(randomize) {
    if (!items.length) return;
    sequence = randomize ? shuffle(items) : items.slice();
    index = 0;
    phase = "work";
    breakdown = [];
    modeSelect.hidden = true;
    playerEl.hidden = false;
    startPhase();
  }

  document.getElementById("circuit-start-order").addEventListener("click", () => begin(false));
  document.getElementById("circuit-start-random").addEventListener("click", () => begin(true));

  pauseBtn.addEventListener("click", () => {
    paused = !paused;
    pauseBtn.textContent = paused ? "Reanudar" : "Pausar";
  });

  skipBtn.addEventListener("click", skip);

  quitBtn.addEventListener("click", () => {
    if (confirm("¿Terminar el circuito ahora? Se guarda lo hecho hasta aquí.")) quit();
  });

  finishBtn.addEventListener("click", async () => {
    finishBtn.disabled = true;
    finishBtn.textContent = "Guardando…";
    try {
      const csrfInput = root.querySelector("[name=csrfmiddlewaretoken]");
      const resp = await fetch(saveUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfInput ? csrfInput.value : "",
        },
        body: JSON.stringify({ breakdown }),
      });
      const data = await resp.json();
      window.location.href = (data && data.redirect_url) || cancelUrl;
    } catch (e) {
      finishBtn.disabled = false;
      finishBtn.textContent = "Guardar y volver";
      alert("No se pudo guardar. Revisa la conexión e inténtalo otra vez.");
    }
  });
})();
