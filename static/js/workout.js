/* ============================================================
   Contador de dominadas con MediaPipe (100% en el navegador).
   No se sube ni se guarda ningún vídeo — solo los números que
   salen de aquí (reps, duración de cada rep, avisos de descanso).
   ============================================================ */

const MEDIAPIPE_VERSION = "0.10.14";
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task";

// Umbrales del conteo (proporcionales al ancho de hombros, para que
// dé igual lo lejos o cerca que esté la cámara).
const UP_FACTOR = 0.45;    // cuánto tiene que subir la nariz para contar "arriba"
const DOWN_FACTOR = 0.15;  // cuánto tiene que bajar para contar "abajo" otra vez
const CALIBRATION_MS = 2000; // tiempo colgado quieto para calibrar
const REST_ALERT_SECONDS = 90; // segundos de descanso antes del pitido

// Índices de landmarks de MediaPipe Pose que usamos
const NOSE = 0, L_SHOULDER = 11, R_SHOULDER = 12;

function el(id) { return document.getElementById(id); }

function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.5);
    osc.connect(gain).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.55);
    // segundo pitido, un poco más agudo, medio segundo después
    setTimeout(() => {
      const ctx2 = new (window.AudioContext || window.webkitAudioContext)();
      const osc2 = ctx2.createOscillator();
      const gain2 = ctx2.createGain();
      osc2.type = "sine";
      osc2.frequency.value = 1046.5;
      gain2.gain.setValueAtTime(0.0001, ctx2.currentTime);
      gain2.gain.exponentialRampToValueAtTime(0.3, ctx2.currentTime + 0.02);
      gain2.gain.exponentialRampToValueAtTime(0.0001, ctx2.currentTime + 0.5);
      osc2.connect(gain2).connect(ctx2.destination);
      osc2.start();
      osc2.stop(ctx2.currentTime + 0.55);
    }, 550);
  } catch (e) {
    console.warn("No se pudo reproducir el aviso sonoro:", e);
  }
}

function getCookie(name) {
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? decodeURIComponent(match[2]) : null;
}

class WorkoutSession {
  constructor(root) {
    this.root = root;
    this.saveUrl = root.dataset.saveUrl;
    this.video = el("workout-video");
    this.canvas = el("workout-canvas");
    this.ctx = this.canvas.getContext("2d");

    this.statusEl = el("workout-status");
    this.repsEl = el("workout-reps");
    this.timerEl = el("workout-timer");
    this.restEl = el("workout-rest");
    this.finishBtn = el("workout-finish");
    this.cancelBtn = el("workout-cancel");

    this.poseLandmarker = null;
    this.stream = null;
    this.running = false;

    this.calibrating = false;
    this.calibrationSamples = [];
    this.calibrationStartTs = null;
    this.baselineY = null;
    this.shoulderWidth = null;

    this.state = "down"; // "down" | "up"
    this.reps = 0;
    this.repDurations = [];
    this.lastBottomTime = null;

    this.sessionStart = null;
    this.lastRepTime = null;
    this.restAlerted = false;
    this.restAlertsTriggered = 0;

    this.finishBtn.addEventListener("click", () => this.finish());
    this.cancelBtn.addEventListener("click", () => {
      this.stopCamera();
      window.location.href = root.dataset.cancelUrl;
    });
  }

  setStatus(text) {
    this.statusEl.textContent = text;
  }

  async start() {
    this.setStatus("Pidiendo acceso a la cámara…");
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: 640, height: 480 },
        audio: false,
      });
    } catch (err) {
      this.setStatus(
        "No se pudo acceder a la cámara. Revisa los permisos del navegador y recarga la página."
      );
      console.error(err);
      return;
    }

    this.video.srcObject = this.stream;
    await this.video.play();
    this.canvas.width = this.video.videoWidth || 640;
    this.canvas.height = this.video.videoHeight || 480;

    this.setStatus("Cargando el modelo de seguimiento…");
    try {
      const { FilesetResolver, PoseLandmarker } = await import(
        `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE_VERSION}`
      );
      const vision = await FilesetResolver.forVisionTasks(
        `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE_VERSION}/wasm`
      );
      this.poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
        runningMode: "VIDEO",
        numPoses: 1,
      });
    } catch (err) {
      this.setStatus("No se pudo cargar el modelo de seguimiento. Comprueba tu conexión y recarga.");
      console.error(err);
      return;
    }

    this.running = true;
    this.calibrating = true;
    this.calibrationStartTs = performance.now();
    this.sessionStart = performance.now();
    this.setStatus("Cuélgate de la barra con los brazos estirados y quédate quieto 2 segundos…");

    this.restIntervalId = setInterval(() => this.tickRestTimer(), 500);
    this.loop();
  }

  loop() {
    if (!this.running) return;
    const now = performance.now();
    const result = this.poseLandmarker.detectForVideo(this.video, now);
    this.drawOverlay(result);
    this.processResult(result, now);
    requestAnimationFrame(() => this.loop());
  }

  drawOverlay(result) {
    const ctx = this.ctx;
    ctx.save();
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    // Espejo, para que se vea natural (como un espejo real)
    ctx.translate(this.canvas.width, 0);
    ctx.scale(-1, 1);

    if (result.landmarks && result.landmarks.length) {
      const lm = result.landmarks[0];
      const nose = lm[NOSE];
      ctx.fillStyle = "#D8654A";
      ctx.beginPath();
      ctx.arc(nose.x * this.canvas.width, nose.y * this.canvas.height, 8, 0, Math.PI * 2);
      ctx.fill();

      if (this.baselineY !== null && this.shoulderWidth) {
        const upY = (this.baselineY - UP_FACTOR * this.shoulderWidth) * this.canvas.height;
        const downY = (this.baselineY - DOWN_FACTOR * this.shoulderWidth) * this.canvas.height;
        ctx.strokeStyle = "rgba(122,139,111,0.8)";
        ctx.setLineDash([6, 6]);
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(0, upY);
        ctx.lineTo(this.canvas.width, upY);
        ctx.stroke();
        ctx.strokeStyle = "rgba(216,101,74,0.8)";
        ctx.beginPath();
        ctx.moveTo(0, downY);
        ctx.lineTo(this.canvas.width, downY);
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  processResult(result, now) {
    if (!result.landmarks || !result.landmarks.length) return;
    const lm = result.landmarks[0];
    const nose = lm[NOSE];
    const lShoulder = lm[L_SHOULDER];
    const rShoulder = lm[R_SHOULDER];
    const shoulderWidth = Math.hypot(lShoulder.x - rShoulder.x, lShoulder.y - rShoulder.y);
    const shoulderMidY = (lShoulder.y + rShoulder.y) / 2;
    // usamos nariz para el movimiento vertical, hombros para la escala
    const y = nose.y;

    if (this.calibrating) {
      this.calibrationSamples.push(y);
      const elapsed = now - this.calibrationStartTs;
      const remaining = Math.max(0, Math.ceil((CALIBRATION_MS - elapsed) / 1000));
      this.setStatus(`Calibrando… quédate quieto (${remaining}s)`);
      if (elapsed >= CALIBRATION_MS) {
        const sorted = [...this.calibrationSamples].sort((a, b) => a - b);
        this.baselineY = sorted[Math.floor(sorted.length / 2)];
        this.shoulderWidth = shoulderWidth;
        this.calibrating = false;
        this.lastBottomTime = now;
        this.lastRepTime = now;
        this.setStatus("¡Listo! Empieza a hacer dominadas.");
      }
      return;
    }

    if (!this.shoulderWidth) return;
    const rise = this.baselineY - y; // positivo si la nariz sube
    const upThresh = UP_FACTOR * this.shoulderWidth;
    const downThresh = DOWN_FACTOR * this.shoulderWidth;

    if (this.state === "down" && rise > upThresh) {
      this.state = "up";
    } else if (this.state === "up" && rise < downThresh) {
      const duration = (now - this.lastBottomTime) / 1000;
      this.reps += 1;
      this.repDurations.push(Math.round(duration * 100) / 100);
      this.lastBottomTime = now;
      this.lastRepTime = now;
      this.restAlerted = false;
      this.state = "down";
      this.repsEl.textContent = String(this.reps);
      this.setStatus(`¡Dominada ${this.reps}! (${duration.toFixed(1)}s)`);
    }
  }

  tickRestTimer() {
    if (!this.running || this.calibrating || !this.sessionStart) return;
    const now = performance.now();
    this.timerEl.textContent = this.formatTime((now - this.sessionStart) / 1000);

    if (this.lastRepTime === null) return;
    const restSeconds = (now - this.lastRepTime) / 1000;
    this.restEl.textContent = this.formatTime(restSeconds);

    if (restSeconds >= REST_ALERT_SECONDS && !this.restAlerted) {
      this.restAlerted = true;
      this.restAlertsTriggered += 1;
      beep();
      this.setStatus("⏰ ¡Descanso acabado! Vuelve a la barra.");
    }
  }

  formatTime(totalSeconds) {
    const s = Math.max(0, Math.floor(totalSeconds));
    const m = Math.floor(s / 60);
    const r = s % 60;
    return `${m}:${String(r).padStart(2, "0")}`;
  }

  stopCamera() {
    this.running = false;
    if (this.restIntervalId) clearInterval(this.restIntervalId);
    if (this.stream) this.stream.getTracks().forEach((t) => t.stop());
    if (this.poseLandmarker) this.poseLandmarker.close();
  }

  async finish() {
    if (this.reps === 0 && !confirm("No se ha contado ninguna dominada. ¿Guardar la sesión igualmente?")) {
      return;
    }
    this.finishBtn.disabled = true;
    this.finishBtn.textContent = "Guardando…";

    const sessionDuration = this.sessionStart ? (performance.now() - this.sessionStart) / 1000 : 0;
    this.stopCamera();

    try {
      const resp = await fetch(this.saveUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({
          total_reps: this.reps,
          rep_durations: this.repDurations,
          session_duration_seconds: Math.round(sessionDuration),
          rest_alerts_triggered: this.restAlertsTriggered,
        }),
      });
      const data = await resp.json();
      if (data.ok) {
        window.location.href = data.redirect_url;
      } else {
        alert("No se pudo guardar la sesión: " + (data.error || "error desconocido"));
        this.finishBtn.disabled = false;
        this.finishBtn.textContent = "Terminar sesión";
      }
    } catch (err) {
      console.error(err);
      alert("No se pudo guardar la sesión (sin conexión?). Los datos no se han perdido de la pantalla, prueba de nuevo.");
      this.finishBtn.disabled = false;
      this.finishBtn.textContent = "Terminar sesión";
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const root = el("workout-root");
  if (!root) return;
  const session = new WorkoutSession(root);
  session.start();
});
