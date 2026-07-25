/* ============================================================
   Contador de dominadas con MediaPipe (100% en el navegador).
   No se sube ni se guarda ningún vídeo — solo los números que
   salen de aquí (reps, duración de cada rep, avisos de descanso).
   ============================================================ */

const MEDIAPIPE_VERSION = "0.10.14";
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task";

// Umbral de movimiento (proporcional al ancho de hombros) para
// considerar que hay un cambio de estado real y no ruido de la cámara.
const MOVE_FACTOR = 0.12;
const LIFTOFF_FACTOR = 0.04; // primer indicio de movimiento real (para medir bien la duracion)
const BAR_MARGIN_FACTOR = 0.25; // cuanto por debajo de la barra ya cuenta como "llegaste arriba"
const MIN_REP_SECONDS = 0.3; // por debajo de esto, se descarta como ruido
const PREP_SECONDS = 6;       // tiempo para llegar a la barra y colgarte antes de calibrar
const CALIBRATION_MS = 1200;  // tiempo colgado quieto que se usa como referencia
const REST_ALERT_SECONDS = 90; // segundos de descanso antes del pitido

// Índices de landmarks de MediaPipe Pose que usamos
const NOSE = 0, L_SHOULDER = 11, R_SHOULDER = 12, L_WRIST = 15, R_WRIST = 16;

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
    this.debugEl = el("workout-debug");

    this.poseLandmarker = null;
    this.stream = null;
    this.running = false;

    this.calibrating = false;
    this.prepping = false;
    this.prepStartTs = null;
    this.calibrationSamples = [];
    this.calibrationStartTs = null;
    this.shoulderWidth = null;

    this.state = "down"; // "down" | "up"
    this.reps = 0;
    this.repDurations = [];
    this.localBottomY = null;  // y (0-1) del punto mas bajo visto en la fase actual
    this.localTopY = null;     // y (0-1) del punto mas alto visto en la fase actual
    this.barY = null;          // y (0-1) de la barra, medida por la altura de tus muñecas
    this.repStartTime = null;
    this.liftoffTime = null;   // instante en que detectamos que empezaste a moverte de verdad

    this.sessionStart = null;
    this.lastRepTime = null;
    this.restAlerted = false;
    this.restAlertsTriggered = 0;

    this.finishBtn.addEventListener("click", () => this.finish());
    this.cancelBtn.addEventListener("click", () => {
      this.stopCamera();
      window.location.href = root.dataset.cancelUrl;
    });
    this.recalBtn = el("workout-recalibrate");
    if (this.recalBtn) {
      this.recalBtn.addEventListener("click", () => this.beginPrep());
    }
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
    this.sessionStart = performance.now();
    this.beginPrep();

    this.restIntervalId = setInterval(() => this.tickRestTimer(), 500);
    this.loop();
  }

  beginPrep() {
    // Cuenta atrás para darte tiempo a llegar a la barra y colgarte
    // ANTES de que se tome ninguna medida (esto es lo que fallaba:
    // calibrar de golpe al abrir la cámara, con nadie aún en la barra).
    this.prepping = true;
    this.calibrating = false;
    this.prepStartTs = performance.now();
    this.calibrationSamples = [];
    this.state = "down";
    this.localBottomY = null;
    this.localTopY = null;
    this.barY = null;
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

      if (this.shoulderWidth && this.barY !== null) {
        const moveThresh = MOVE_FACTOR * this.shoulderWidth;
        const barThresh = (this.barY + BAR_MARGIN_FACTOR * this.shoulderWidth) * this.canvas.height;

        // Línea de la barra (medida por tus muñecas al calibrar)
        ctx.strokeStyle = "rgba(201,162,39,0.95)";
        ctx.setLineDash([]);
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(0, this.barY * this.canvas.height);
        ctx.lineTo(this.canvas.width, this.barY * this.canvas.height);
        ctx.stroke();

        ctx.strokeStyle = "rgba(201,162,39,0.5)";
        ctx.setLineDash([4, 4]);
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(0, barThresh);
        ctx.lineTo(this.canvas.width, barThresh);
        ctx.stroke();

        const ref = this.state === "down" ? this.localBottomY : this.localTopY;
        if (ref !== null) {
          const refY = ref * this.canvas.height;
          const triggerY =
            this.state === "down"
              ? (ref - moveThresh) * this.canvas.height
              : (ref + moveThresh) * this.canvas.height;
          ctx.strokeStyle = "rgba(122,139,111,0.7)";
          ctx.setLineDash([3, 5]);
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.moveTo(0, refY);
          ctx.lineTo(this.canvas.width, refY);
          ctx.stroke();

          ctx.strokeStyle = "rgba(216,101,74,0.9)";
          ctx.setLineDash([6, 6]);
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.moveTo(0, triggerY);
          ctx.lineTo(this.canvas.width, triggerY);
          ctx.stroke();
        }
      }
    }
    ctx.restore();
  }

  processResult(result, now) {
    if (!result.landmarks || !result.landmarks.length) {
      if (this.debugEl) this.debugEl.textContent = "sin detección — ¿sales entero en el encuadre?";
      return;
    }
    const lm = result.landmarks[0];
    const nose = lm[NOSE];
    const lShoulder = lm[L_SHOULDER];
    const rShoulder = lm[R_SHOULDER];
    const lWrist = lm[L_WRIST];
    const rWrist = lm[R_WRIST];
    const shoulderWidth = Math.hypot(lShoulder.x - rShoulder.x, lShoulder.y - rShoulder.y);
    const y = nose.y; // 0 = arriba del todo del encuadre, 1 = abajo del todo
    const wristY = (lWrist.y + rWrist.y) / 2;

    if (this.prepping) {
      const elapsed = now - this.prepStartTs;
      const remaining = Math.max(0, Math.ceil((PREP_SECONDS - elapsed / 1000)));
      this.setStatus(`Ve a la barra y cuélgate con los brazos estirados… (${remaining}s)`);
      if (elapsed >= PREP_SECONDS * 1000) {
        this.prepping = false;
        this.calibrating = true;
        this.calibrationStartTs = now;
      }
      return;
    }

    if (this.calibrating) {
      this.calibrationSamples.push({ y, shoulderWidth, wristY });
      const elapsed = now - this.calibrationStartTs;
      const remaining = Math.max(0, Math.ceil((CALIBRATION_MS - elapsed) / 1000));
      this.setStatus(`Calibrando, quédate colgado y quieto… (${remaining || 1}s)`);
      if (elapsed >= CALIBRATION_MS) {
        const ys = this.calibrationSamples.map((s) => s.y).sort((a, b) => a - b);
        const ws = this.calibrationSamples.map((s) => s.shoulderWidth).sort((a, b) => a - b);
        const wy = this.calibrationSamples.map((s) => s.wristY).sort((a, b) => a - b);
        this.shoulderWidth = ws[Math.floor(ws.length / 2)];
        this.localBottomY = ys[Math.floor(ys.length / 2)];
        this.localTopY = this.localBottomY;
        this.barY = wy[Math.floor(wy.length / 2)]; // altura de la barra = altura de tus muñecas al colgar
        this.calibrating = false;
        this.repStartTime = now;
        this.lastRepTime = now;
        this.setStatus("¡Listo! Empieza a hacer dominadas.");
      }
      return;
    }

    if (!this.shoulderWidth || this.barY === null) return;
    const moveThresh = MOVE_FACTOR * this.shoulderWidth;
    const barThresh = this.barY + BAR_MARGIN_FACTOR * this.shoulderWidth;

    if (this.state === "down") {
      // sigue bajando (o igual) -> este es el nuevo punto de referencia "abajo",
      // y todavia no has "despegado" (reinicia la marca de despegue)
      if (this.localBottomY === null || y > this.localBottomY) {
        this.localBottomY = y;
        this.liftoffTime = null;
      }
      const risenFromBottom = this.localBottomY - y;

      // primer indicio de que te has empezado a mover de verdad
      if (this.liftoffTime === null && risenFromBottom > LIFTOFF_FACTOR * this.shoulderWidth) {
        this.liftoffTime = now;
      }

      const reachedBar = y <= barThresh;
      if (reachedBar && risenFromBottom > moveThresh) {
        this.state = "up";
        this.localTopY = y;
        this.repStartTime = this.liftoffTime ?? now;
      }
    } else {
      // state === "up": sigue subiendo (o igual) -> nuevo punto de referencia "arriba"
      if (this.localTopY === null || y < this.localTopY) {
        this.localTopY = y;
      }
      const fallenFromTop = y - this.localTopY;
      if (fallenFromTop > moveThresh) {
        // ha vuelto a bajar lo suficiente -> repetición completa
        const duration = (now - this.repStartTime) / 1000;
        if (duration >= MIN_REP_SECONDS) {
          this.reps += 1;
          this.repDurations.push(Math.round(duration * 100) / 100);
          this.lastRepTime = now;
          this.restAlerted = false;
          this.repsEl.textContent = String(this.reps);
          this.setStatus(`¡Dominada ${this.reps}! (${duration.toFixed(1)}s)`);
        }
        this.state = "down";
        this.localBottomY = y;
      }
    }

    if (this.debugEl) {
      this.debugEl.textContent =
        `estado: ${this.state} | nariz-barra: ${((y - this.barY) / this.shoulderWidth).toFixed(2)} ` +
        `(umbral ${BAR_MARGIN_FACTOR}) | hombros: ${this.shoulderWidth.toFixed(3)}`;
    }
  }

  tickRestTimer() {
    if (!this.running || this.prepping || this.calibrating || !this.sessionStart) return;
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
