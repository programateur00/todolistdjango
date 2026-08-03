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
const BAR_OFFSET_FACTOR = 0.05; // empuja la linea de la barra hacia arriba respecto a la muñeca (~2cm en un adulto medio, ver nota abajo)
const HANG_MARGIN_FACTOR = 0.08; // cuanto tienen que estar las munecas por encima de los hombros para considerar que estas colgado
const SCALE_TOLERANCE = 0.3; // cuanto puede variar el ancho de hombros (te acercas/alejas) antes de desconfiar del frame
const MIN_REP_SECONDS = 0.3; // por debajo de esto, se descarta como ruido
const HANG_STABLE_MS = 500;   // cuanto tiempo seguido con los brazos en alto para empezar a calibrar
const ARMS_DOWN_STABLE_MS = 400; // cuanto tiempo seguido con los brazos abajo para dar la serie por terminada (evita falsos positivos por un frame ruidoso)
const CALIBRATION_MS = 1200;  // tiempo colgado quieto que se usa como referencia
const REST_ALERT_SECONDS = 90;

// Se mide la NARIZ frente a los CODOS, no el ángulo del brazo. Al bajar
// en un fondo la cabeza cae por debajo de la línea de los codos, y eso
// se ve igual de frente que de lado — el ángulo del codo, en cambio,
// solo se mide bien de perfil.
//
// Los valores van en proporción al ancho de hombros, así que no dependen
// de lo cerca que estés de la cámara.
const DIP_DOWN_FACTOR = 0.05;  // nariz a la altura de los codos o por debajo -> abajo
const DIP_UP_FACTOR = 0.45;    // nariz bien por encima -> arriba
const DIP_MIN_VISIBILITY = 0.4;
// FALLO CONOCIDO: nariz-vs-codos por sí solo no distingue estar agarrado a
// las barras de estar simplemente de pie con los brazos colgando (la nariz
// también queda muy por encima de los codos así), y levantar y bajar las
// manos sin tocar las barras mueve los codos igual que un fondo real, así
// que se contaba como repetición. Arreglo: usar las MANOS como referencia.
// En un fondo real las manos están fijas en la barra durante todo el
// movimiento (solo se mueve el cuerpo); si te sueltas, o si levantas las
// manos sin estar agarrado, las manos se desplazan mucho más de lo que se
// desplazan en un fondo real. DIP_HANDS_MAX_DRIFT_FACTOR es cuánto se
// pueden mover (en proporción al ancho de hombros) respecto a donde
// estaban cuando te pusiste arriba antes de asumir eso y descartar la
// repetición en curso.
const DIP_HANDS_MAX_DRIFT_FACTOR = 0.35;
// En un fondo real la nariz SIEMPRE queda por encima de la línea de los
// hombros (ni agachando la cabeza del todo baja tanto). Si aparece por
// debajo — normalmente porque se ha girado el ángulo de la cámara, o la
// cabeza, para "engañar" a la relación nariz/codos — se descarta como
// postura imposible. Margen pequeño porque en cualquier postura humana
// normal la nariz queda MUY por encima, así que no hace falta más para
// no afectar a fondos reales, ni siquiera con la cabeza muy agachada.
const DIP_NOSE_ABOVE_SHOULDER_MARGIN = 0.05;
// Cuánto tiempo seguido sin agarre válido (manos movidas, postura
// imposible, o no se te ve bien) para dar la serie por terminada, en vez
// de seguir sumando fondos a la misma serie pase lo que pase. Reutiliza
// ARMS_DOWN_STABLE_MS: es el mismo concepto que "te has soltado de la
// barra" en dominadas, solo que aplicado a las barras de los fondos.

// Índices de landmarks de MediaPipe Pose que usamos
const NOSE = 0, L_SHOULDER = 11, R_SHOULDER = 12, L_ELBOW = 13, R_ELBOW = 14, L_WRIST = 15, R_WRIST = 16;

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
    // Objetivo del ejercicio (si viene de un plan o de un circuito con
    // meta fija) — solo para avisar al llegar, NO para parar el conteo.
    // Sin esto (o si no viene ninguno) simplemente no hay aviso.
    this.targetSets = root.dataset.targetSets ? parseInt(root.dataset.targetSets, 10) : null;
    this.targetReps = root.dataset.targetReps ? parseInt(root.dataset.targetReps, 10) : null;
    this.targetAnnounced = false;
    // Qué contador usar. Lo decide el ejercicio (counter_key en el
    // catálogo), no la pantalla.
    this.counterKey = root.dataset.counterKey || "pullup";
    this.video = el("workout-video");
    this.canvas = el("workout-canvas");
    this.ctx = this.canvas.getContext("2d");

    this.statusEl = el("workout-status");
    this.goalBannerEl = el("workout-goal-banner");
    this.repsEl = el("workout-reps");
    this.setsEl = el("workout-sets");
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
    this.hangStableSince = null;
    this.armsDownSince = null; // desde cuándo llevas los brazos abajo seguido (para no cerrar la serie por un frame ruidoso)
    this.calibrationSamples = [];
    this.calibrationStartTs = null;
    this.shoulderWidth = null;

    this.state = "down"; // "down" | "up"
    this.reps = 0;
    this.repDurations = [];
    this.sets = [];              // series ya cerradas: [{reps, durations}, ...]
    this.currentSetReps = 0;     // reps de la serie en curso
    this.currentSetDurations = [];
    this.localBottomY = null;  // y (0-1) del punto mas bajo visto en la fase actual
    this.localTopY = null;     // y (0-1) del punto mas alto visto en la fase actual
    this.barY = null;          // y (0-1) de la barra, medida por la altura de tus muñecas
    this.repStartTime = null;
    this.liftoffTime = null;   // instante en que detectamos que empezaste a moverte de verdad
    this.dipHandsY = null;     // y (0-1) de las manos cuando confirmamos "arriba" en un fondo — referencia para saber si sigues agarrado a las barras
    this.dipReleaseSince = null; // desde cuándo llevas sin agarre válido seguido en un fondo (para no cerrar la serie por un frame ruidoso)

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

    // Cada (re)calibración marca el final de la serie en curso (si
    // tenía alguna repetición) y el principio de la siguiente.
    if (this.currentSetReps > 0) {
      this.sets.push({ reps: this.currentSetReps, durations: [...this.currentSetDurations] });
      this.currentSetReps = 0;
      this.currentSetDurations = [];
      this.updateSetDisplay();
    }
    // El contador grande siempre arranca en 0 al empezar una serie nueva.
    if (this.repsEl) this.repsEl.textContent = "0";

    this.prepping = true;
    this.calibrating = false;
    this.prepStartTs = performance.now();
    this.hangStableSince = null;
    this.armsDownSince = null;
    this.calibrationSamples = [];
    this.localBottomY = null;
    this.localTopY = null;
    this.barY = null;

    // Los fondos no se calibran ni se cuelgan de ninguna barra: el
    // estado arranca vacío y se fija solo cuando te pones arriba.
    if (this.counterKey === "dip") {
      this.prepping = false;
      this.state = null;
      this.dipHandsY = null;
      this.dipReleaseSince = null;
      this.setStatus("Ponte arriba con los brazos estirados para empezar.");
    } else {
      this.state = "down";
    }
  }

  updateSetDisplay() {
    if (this.setsEl) this.setsEl.textContent = String(this.sets.length + 1);
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

  /**
   * Registra una repetición. Común a todos los ejercicios: lo único que
   * cambia entre dominadas y fondos es CÓMO se detecta, no qué se
   * apunta después.
   */
  countRep(duration, now, label) {
    if (duration < MIN_REP_SECONDS) return false;   // ruido, no cuenta
    const d = Math.round(duration * 100) / 100;
    this.reps += 1;
    this.repDurations.push(d);
    this.currentSetReps += 1;
    this.currentSetDurations.push(d);
    this.lastRepTime = now;
    this.restAlerted = false;
    // Se muestran las reps de ESTA serie, no el total de la sesión (el
    // total sigue guardándose bien en this.reps al terminar).
    this.repsEl.textContent = String(this.currentSetReps);

    // Aviso al llegar al objetivo — una sola vez, y sin parar nada: se
    // puede seguir contando por encima del 100% si te apetece (se
    // guarda tal cual, el backend no lo recorta). Es solo un chivatazo,
    // la decisión de seguir o terminar la tomas tú con el botón.
    //
    // Va en un aviso APARTE (workout-goal-banner), no solo en el texto
    // de estado normal: ese cambia con cada repetición siguiente y el
    // mensaje del objetivo podía pasar sin que te dieras ni cuenta si no
    // estabas mirando esa línea justo en ese instante. El banner se
    // queda puesto todo lo que quieras, hasta que termines o recalibres.
    if (this.targetSets && this.targetReps && !this.targetAnnounced) {
      const meta = this.targetSets * this.targetReps;
      if (this.reps >= meta) {
        this.targetAnnounced = true;
        if (this.goalBannerEl) {
          this.goalBannerEl.hidden = false;
          this.goalBannerEl.textContent = `🎯 ¡Objetivo cumplido! (${meta}) Sigue si quieres, o termina cuando acabes.`;
        }
        this.setStatus(`🎯 ¡Objetivo cumplido (${meta})!`);
        try {
          const ctx = new (window.AudioContext || window.webkitAudioContext)();
          [0, 0.14].forEach((t, i) => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.frequency.value = i === 0 ? 880 : 1175;
            osc.connect(gain);
            gain.connect(ctx.destination);
            gain.gain.setValueAtTime(0.18, ctx.currentTime + t);
            osc.start(ctx.currentTime + t);
            osc.stop(ctx.currentTime + t + 0.13);
          });
        } catch (e) { /* si el navegador bloquea audio, no pasa nada */ }
        return true;
      }
    }
    this.setStatus(`¡${label} ${this.currentSetReps} de esta serie! (${duration.toFixed(1)}s)`);
    return true;
  }

  /**
   * Fondos: se cuentan por el ángulo del codo.
   *
   * Arriba el brazo está extendido; abajo el codo se dobla. Como un
   * ángulo no cambia con la distancia a la cámara, esto no necesita
   * calibración — a diferencia de las dominadas, que sí tienen que
   * medir dónde está la barra.
   *
   * Se usa el brazo que mejor se vea: en un fondo de perfil, el brazo
   * de atrás queda tapado por el cuerpo.
   *
   * Nariz-vs-codos por sí solo tiene dos fallos, que es lo que arregla
   * todo lo de abajo:
   *
   *  1. Estar de pie con los brazos sueltos ya cumple la condición de
   *     "arriba" (la nariz también queda muy por encima de los codos
   *     así), y levantar y bajar las manos sin tocar las barras mueve
   *     los codos igual que un fondo real. Arreglo: usamos las MANOS
   *     como referencia de que sigues agarrado. En un fondo real las
   *     manos están fijas en la barra durante todo el movimiento (solo
   *     se mueve el cuerpo), así que en cuanto se detecta "arriba" se
   *     guarda la altura de las manos; si en algún momento se desplazan
   *     más de la cuenta, cuenta como que te has soltado.
   *
   *  2. Girar el ángulo de la cámara (o agachar mucho la cabeza) puede
   *     hacer que la nariz aparezca por debajo de los hombros en la
   *     imagen, cosa imposible en un fondo real — y sin embargo
   *     "engañaría" a la relación nariz/codos igual que una repetición
   *     de verdad. Arreglo: comprobamos que la nariz esté SIEMPRE por
   *     encima de la línea de los hombros; si no, se descarta.
   *
   * Y al igual que en dominadas: si se pierde el agarre válido (manos
   * movidas, postura imposible, o no se te ve bien) durante un rato
   * seguido — no un solo frame ruidoso —, se da la serie por terminada
   * (ver registerDipRelease), en vez de sumar todos los fondos de la
   * sesión a la misma serie pase lo que pase.
   */
  processDip(lm, now) {
    const nose = lm[NOSE];
    const lShoulder = lm[L_SHOULDER], rShoulder = lm[R_SHOULDER];
    const lElbow = lm[L_ELBOW], rElbow = lm[R_ELBOW];
    const lWrist = lm[L_WRIST], rWrist = lm[R_WRIST];

    const shoulderVis = ((lShoulder.visibility ?? 1) + (rShoulder.visibility ?? 1)) / 2;
    const elbowVis = ((lElbow.visibility ?? 1) + (rElbow.visibility ?? 1)) / 2;
    const noseVis = nose.visibility ?? 1;
    const wristVis = ((lWrist.visibility ?? 1) + (rWrist.visibility ?? 1)) / 2;
    if (shoulderVis < DIP_MIN_VISIBILITY || elbowVis < DIP_MIN_VISIBILITY || noseVis < DIP_MIN_VISIBILITY || wristVis < DIP_MIN_VISIBILITY) {
      this.setStatus("No se te ven bien la cara, los hombros, los codos y las manos. Ajusta la cámara.");
      if (this.debugEl) this.debugEl.textContent = "buscando nariz, hombros, codos y manos…";
      this.registerDipRelease(now);
      return;
    }

    const shoulderWidth = Math.hypot(
      lShoulder.x - rShoulder.x, lShoulder.y - rShoulder.y
    );
    if (!shoulderWidth) return;

    const shoulderMidY = (lShoulder.y + rShoulder.y) / 2;
    const elbowMidY = (lElbow.y + rElbow.y) / 2;
    const handsY = (lWrist.y + rWrist.y) / 2;

    // Cuánto está la nariz POR ENCIMA de la línea de los codos, en
    // proporción al ancho de hombros (y crece hacia abajo en pantalla).
    // Arriba en un fondo la cabeza queda muy por encima; al bajar cae
    // hasta el nivel de los codos o por debajo.
    const above = (elbowMidY - nose.y) / shoulderWidth;

    // Sentido común: en un fondo real la nariz siempre queda por encima
    // de los hombros. Si no, es un ángulo de cámara o postura imposible.
    const noseAboveShoulders = (shoulderMidY - nose.y) / shoulderWidth >= DIP_NOSE_ABOVE_SHOULDER_MARGIN;
    if (!noseAboveShoulders) {
      this.setStatus("No pareces estar en posición de fondo. Comprueba el ángulo de la cámara.");
      if (this.debugEl) this.debugEl.textContent = "nariz no está por encima de los hombros — postura no válida";
      this.registerDipRelease(now);
      return;
    }

    // Si ya teníamos guardada la altura de las manos al ponerte arriba y
    // se han movido más de la cuenta, no estás en mitad de un fondo: te
    // has soltado de las barras, o nunca estuviste agarrado y solo
    // levantaste las manos.
    if (this.dipHandsY !== null) {
      const handsDrift = Math.abs(handsY - this.dipHandsY) / shoulderWidth;
      if (handsDrift > DIP_HANDS_MAX_DRIFT_FACTOR) {
        if (this.debugEl) {
          this.debugEl.textContent = `manos desplazadas: ${handsDrift.toFixed(2)} (máximo ${DIP_HANDS_MAX_DRIFT_FACTOR})`;
        }
        this.registerDipRelease(now);
        return;
      }
    }

    // Agarre válido este frame: reinicia el contador de "suelto".
    this.dipReleaseSince = null;

    if (this.state === null) {
      // Hay que empezar arriba, para no contar media repetición al entrar.
      if (above >= DIP_UP_FACTOR) {
        this.state = "top";
        this.dipHandsY = handsY; // ancla: aquí deben quedarse las manos mientras dure el fondo
        this.setStatus("¡Listo! Baja y sube.");
      } else {
        this.setStatus("Ponte arriba con los brazos estirados para empezar.");
      }
    } else if (this.state === "top") {
      if (above <= DIP_DOWN_FACTOR) {
        this.state = "bottom";
        this.repStartTime = now;      // la repetición empieza al bajar
      }
    } else if (above >= DIP_UP_FACTOR) {
      // Ha vuelto arriba: repetición completa.
      this.countRep((now - this.repStartTime) / 1000, now, "Fondo");
      this.state = "top";
      this.dipHandsY = handsY; // actualiza el ancla por si te has movido un poco desde el fondo anterior
    }

    if (this.debugEl) {
      this.debugEl.textContent =
        `nariz sobre codos: ${above.toFixed(2)} | estado: ${this.state ?? "esperando"} ` +
        `(abajo ≤${DIP_DOWN_FACTOR}, arriba ≥${DIP_UP_FACTOR})`;
    }
  }

  /**
   * Se ha perdido el agarre válido a las barras este frame (no se ve
   * bien, postura imposible, o las manos se han movido de donde
   * estaban). Igual que soltarte de la barra en dominadas: si esto se
   * mantiene un rato seguido — no un solo frame ruidoso, que podría ser
   * solo una oclusión pasajera — se da la serie en curso por terminada
   * (si tenía alguna repetición) y toca agarrarse otra vez para empezar
   * la siguiente. Antes de esto todos los fondos de la sesión se
   * apuntaban a la misma serie, sin importar cuántas veces te bajaras
   * de las barras entre medias.
   */
  registerDipRelease(now) {
    if (this.dipReleaseSince === null) this.dipReleaseSince = now;
    if (now - this.dipReleaseSince < ARMS_DOWN_STABLE_MS) return;

    this.dipReleaseSince = null;
    this.state = null;
    this.dipHandsY = null;

    if (this.currentSetReps > 0) {
      const closedReps = this.currentSetReps;
      this.sets.push({ reps: this.currentSetReps, durations: [...this.currentSetDurations] });
      this.currentSetReps = 0;
      this.currentSetDurations = [];
      this.updateSetDisplay();
      if (this.repsEl) this.repsEl.textContent = "0";
      this.setStatus(`Serie de ${closedReps} terminada. Agárrate a las barras para empezar la siguiente.`);
    } else {
      this.setStatus("Ponte arriba con los brazos estirados para empezar.");
    }
  }

  processResult(result, now) {
    if (!result.landmarks || !result.landmarks.length) {
      if (this.debugEl) this.debugEl.textContent = "sin detección — ¿sales entero en el encuadre?";
      return;
    }
    const lm = result.landmarks[0];

    // Cada ejercicio se detecta a su manera. Los fondos no necesitan
    // calibrar ninguna barra, así que salen antes de todo eso.
    if (this.counterKey === "dip") {
      this.processDip(lm, now);
      return;
    }

    const nose = lm[NOSE];
    const lShoulder = lm[L_SHOULDER];
    const rShoulder = lm[R_SHOULDER];
    const lElbow = lm[L_ELBOW];
    const rElbow = lm[R_ELBOW];
    const lWrist = lm[L_WRIST];
    const rWrist = lm[R_WRIST];
    const shoulderWidth = Math.hypot(lShoulder.x - rShoulder.x, lShoulder.y - rShoulder.y);
    const y = nose.y; // 0 = arriba del todo del encuadre, 1 = abajo del todo
    const wristMidY = (lWrist.y + rWrist.y) / 2;
    const elbowMidY = (lElbow.y + rElbow.y) / 2;
    const wristVisible = ((lWrist.visibility ?? 1) + (rWrist.visibility ?? 1)) / 2 > 0.4;
    const elbowVisible = ((lElbow.visibility ?? 1) + (rElbow.visibility ?? 1)) / 2 > 0.4;

    const shoulderMidYRaw = (lShoulder.y + rShoulder.y) / 2;
    // detección de "brazos en alto" usando la escala del frame actual
    // (para poder usarla ANTES de tener una calibración de referencia).
    // Si la muñeca se ve bien, manda ella sola (si la muñeca está claramente
    // abajo, un codo todavía algo elevado ya no debe contar como "colgado").
    // El codo solo se usa como reserva cuando no se ve bien la muñeca.
    const armsUpNow = wristVisible
      ? wristMidY < shoulderMidYRaw - HANG_MARGIN_FACTOR * shoulderWidth
      : elbowVisible && elbowMidY < shoulderMidYRaw - HANG_MARGIN_FACTOR * shoulderWidth;

    if (this.prepping) {
      const waitedSeconds = Math.floor((now - this.prepStartTs) / 1000);
      if (armsUpNow) {
        if (this.hangStableSince === null) this.hangStableSince = now;
        if (now - this.hangStableSince >= HANG_STABLE_MS) {
          // Llevas ya un ratito con los brazos en alto de verdad -> calibra ya,
          // da igual si has tardado 3 segundos o 30 en llegar a la barra.
          this.prepping = false;
          this.calibrating = true;
          this.calibrationStartTs = now;
          this.calibrationSamples = [];
        } else {
          this.setStatus("Te veo colgado… confirmando (no te muevas)");
        }
      } else {
        this.hangStableSince = null;
        this.setStatus(
          waitedSeconds < 8
            ? "Ve a la barra y cuélgate con los brazos estirados…"
            : `Esperando a verte colgado (llevas ${waitedSeconds}s)… comprueba que la cámara vea tus brazos y hombros enteros`
        );
      }
      if (this.debugEl) {
        this.debugEl.textContent = `brazos en alto: ${armsUpNow ? "sí" : "no"} | espera: ${waitedSeconds}s`;
      }
      return;
    }

    if (this.calibrating) {
      // Si en medio de la calibración bajas los brazos (falsa alarma),
      // aborta y vuelve a esperar en vez de calibrar con datos malos.
      if (!armsUpNow) {
        this.prepping = true;
        this.calibrating = false;
        this.hangStableSince = null;
        this.prepStartTs = now;
        this.calibrationSamples = [];
        return;
      }
      // Para calibrar la altura de "la barra" usamos la muñeca si se ve
      // bien; si no, el codo (menos preciso, pero mucho más fiable que los
      // dedos, que MediaPipe no trackea bien cuando están curvados
      // agarrando algo — probado, y hacía que la barra quedara mal puesta).
      const barRefY = wristVisible ? wristMidY : elbowMidY;
      this.calibrationSamples.push({ y, shoulderWidth, barRefY });
      const elapsed = now - this.calibrationStartTs;
      const remaining = Math.max(0, Math.ceil((CALIBRATION_MS - elapsed) / 1000));
      this.setStatus(`Calibrando, quédate colgado y quieto… (${remaining || 1}s)`);
      if (elapsed >= CALIBRATION_MS) {
        const ys = this.calibrationSamples.map((s) => s.y).sort((a, b) => a - b);
        const ws = this.calibrationSamples.map((s) => s.shoulderWidth).sort((a, b) => a - b);
        const wy = this.calibrationSamples.map((s) => s.barRefY).sort((a, b) => a - b);
        this.shoulderWidth = ws[Math.floor(ws.length / 2)];
        this.localBottomY = ys[Math.floor(ys.length / 2)];
        this.localTopY = this.localBottomY;
        // altura de la barra = altura de tu muñeca al colgar, con un
        // empujón extra hacia arriba (BAR_OFFSET_FACTOR) para que la línea
        // cuadre mejor con la barra real (agarras por encima de la muñeca).
        // No hay forma de saber tu escala real en cm sin un objeto de
        // referencia, pero con un ancho de hombros típico (~35-40cm) un
        // factor de 0.05 equivale a ~2cm. Sube/baja el número si hace falta.
        this.barY = wy[Math.floor(wy.length / 2)] - BAR_OFFSET_FACTOR * this.shoulderWidth;
        this.calibrating = false;
        this.repStartTime = now;
        this.lastRepTime = now;
        this.restAlerted = false;
        this.updateSetDisplay();
        this.setStatus("¡Listo! Empieza a hacer dominadas.");
      }
      return;
    }

    if (!this.shoulderWidth || this.barY === null) return;

    const scaleChange = Math.abs(shoulderWidth - this.shoulderWidth) / this.shoulderWidth;
    const scaleOk = scaleChange < SCALE_TOLERANCE;

    if (!armsUpNow || !scaleOk) {
      // No pareces estar colgado de la barra (o te has acercado/alejado de
      // la cámara) — no cuentes nada de lo que pase ahora mismo, y cuando
      // vuelvas a agarrar la barra, empieza a medir desde cero otra vez.
      this.localBottomY = null;
      this.localTopY = null;
      this.liftoffTime = null;

      if (!armsUpNow) {
        // Te has soltado de la barra de verdad (bajaste los brazos, no es
        // solo que te acercaras/alejaras de la cámara): esto es el final de
        // la serie en curso. Pero solo lo damos por bueno si se mantiene
        // un ratito seguido — un solo frame ruidoso (oclusión, ángulo raro
        // agarrando la barra) no debe cerrar la serie por error.
        if (this.armsDownSince === null) this.armsDownSince = now;
        if (now - this.armsDownSince >= ARMS_DOWN_STABLE_MS && this.currentSetReps > 0) {
          const closedReps = this.currentSetReps;
          this.armsDownSince = null;
          this.setStatus(`Serie de ${closedReps} terminada. Cuélgate otra vez para empezar la siguiente.`);
          this.beginPrep();
          return;
        }
      } else {
        // scaleOk falló pero los brazos siguen arriba: no cuenta como que
        // te soltaste, reinicia el contador de "brazos abajo".
        this.armsDownSince = null;
      }

      if (this.debugEl) {
        this.debugEl.textContent = !armsUpNow
          ? "esperando a que agarres la barra (brazos en alto)…"
          : "distancia a la cámara cambió demasiado, recalibra si sigue así";
      }
      return;
    }

    this.armsDownSince = null;

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
        this.countRep((now - this.repStartTime) / 1000, now, "Dominada");
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
    // El cronómetro de sesión y el de descanso tienen que seguir corriendo
    // aunque estés en "prepping" (esperando a colgarte) o calibrando: es
    // justo el rato de descanso entre series, no hay motivo para congelarlos.
    if (!this.running || !this.sessionStart) return;
    const now = performance.now();
    this.timerEl.textContent = this.formatTime((now - this.sessionStart) / 1000);

    if (this.lastRepTime === null) return;
    const restSeconds = (now - this.lastRepTime) / 1000;
    this.restEl.textContent = this.formatTime(restSeconds);

    if (restSeconds >= REST_ALERT_SECONDS && !this.restAlerted) {
      this.restAlerted = true;
      this.restAlertsTriggered += 1;
      beep();
      this.setStatus("⏰ ¡Descanso acabado! Volviendo a calibrar para la siguiente serie…");
      this.beginPrep();
    }
  }

  formatTime(totalSeconds) {
    const s = Math.max(0, Math.floor(totalSeconds));
    const m = Math.floor(s / 60);
    const r = s % 60;
    return `${m}:${String(r).padStart(2, "0")}`;
  }

  stopCamera() {
    if (!this.running && !this.stream && !this.poseLandmarker) return; // ya estaba parada — nada que hacer
    this.running = false;
    if (this.restIntervalId) clearInterval(this.restIntervalId);
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
    if (this.poseLandmarker) {
      try {
        this.poseLandmarker.close();
      } catch (e) {
        // Si ya estaba cerrado (llamar close() dos veces según la
        // versión de MediaPipe puede tirar), no es un fallo real — solo
        // asegúrate de no dejarlo a medias silenciosamente.
        console.warn("poseLandmarker.close() en una cámara ya parada:", e);
      }
      this.poseLandmarker = null;
    }
  }

  async finish() {
    if (this.reps === 0 && !confirm("No se ha contado ninguna dominada. ¿Guardar la sesión igualmente?")) {
      return;
    }
    this.finishBtn.disabled = true;
    this.finishBtn.textContent = "Guardando…";

    // Cierra la serie que estuviera en curso (si tenía reps) antes de mandar los datos.
    if (this.currentSetReps > 0) {
      this.sets.push({ reps: this.currentSetReps, durations: [...this.currentSetDurations] });
      this.currentSetReps = 0;
      this.currentSetDurations = [];
    }

    const sessionDuration = this.sessionStart ? (performance.now() - this.sessionStart) / 1000 : 0;
    this.stopCamera();

    const payload = {
      total_reps: this.reps,
      rep_durations: this.repDurations,
      session_duration_seconds: Math.round(sessionDuration),
      rest_alerts_triggered: this.restAlertsTriggered,
      sets: this.sets,
      total_sets: this.sets.length,
    };

    // Cuando esto se reproduce dentro de la sesión de un plan
    // (plan-session.js), es esa pantalla la que decide qué hacer con el
    // resultado — anotarlo y pasar al siguiente ejercicio, no guardar y
    // salir. Suelto (task_workout.html), sigue el fetch de siempre.
    if (typeof window.__workoutSubmit === "function") {
      try {
        await window.__workoutSubmit(payload);
      } catch (err) {
        // Sin este catch, un fallo aquí dejaba el botón en "Guardando…"
        // para siempre sin ningún error visible — silencioso del todo.
        console.error("Error en __workoutSubmit:", err);
        alert("Algo ha fallado al pasar al siguiente ejercicio. Prueba a recargar la página (lo hecho hasta ahora no se ha guardado todavía).");
        this.finishBtn.disabled = false;
        this.finishBtn.textContent = "Terminar sesión";
      }
      return;
    }

    try {
      const resp = await fetch(this.saveUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify(payload),
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

/**
 * Arranca el contador sobre el #workout-root que haya en pantalla.
 * Exportado para que plan-session.js pueda llamarlo por cada ejercicio
 * de cámara de una sesión de plan, en vez de solo al cargar la página.
 */
export function startWorkout() {
  const root = el("workout-root");
  if (!root) return null;
  const session = new WorkoutSession(root);
  session.start();
  return session;
}

// Uso suelto (task_workout.html): arranca solo al cargar la página.
// Cuando lo importa plan-session.js, __LIBRETA_EMBEDDED__ está puesto y
// esto no hace nada — el arranque lo decide esa pantalla, ejercicio a
// ejercicio. Se comprueba document.readyState porque, al ser un script
// de tipo módulo, se ejecuta DESPUÉS de parsear el HTML — a veces antes
// de "DOMContentLoaded", a veces después. Esperar el evento a ciegas es
// una carrera que a veces se pierde y deja la cámara sin encender.
if (!window.__LIBRETA_EMBEDDED__) {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startWorkout);
  } else {
    startWorkout();
  }
}
