import sys, os, re

CONSTS = r'''
// 2026-09-19 (frontpos-v1) -- COMPUERTA DE POSICION comun a rodillas altas y talones al gluteo (los dos ahora DE FRENTE).
// Motivo (logs reales 2026-09-19): (a) al caminar hacia la camara / ir a pulsar el boton entraban repeticiones falsas
// (primera rep de la serie 1 y las 2 ultimas de cada serie, con desniveles de +-2.0 imposibles en las rodillas);
// (b) talones al gluteo daba por 'levantado' un tobillo 'oculto' (visibilidad baja) aunque solo se viera la cara.
// Ahora NADA se arma ni se cuenta si no se te ve el cuerpo entero (hombros, caderas, rodillas y pies) DENTRO del encuadre,
// erguido y de frente, y ademas EN TU SITIO (sin caminar ni acercarte/alejarte de la camara).
const FRONTPOS_MIN_VIS = 0.5; // visibilidad minima de CADA punto exigido (hombros, caderas, rodillas y pies)
const FRONTPOS_EDGE_MARGIN = 0.02; // un punto a menos de esta fraccion del borde del encuadre se considera cortado
const FRONTPOS_MIN_TORSO_H = 0.07; // altura hombros->caderas (fraccion del alto del encuadre) minima: por debajo estas demasiado lejos
const FRONTPOS_MIN_SHOULDER_W = 0.10; // ancho de hombros minimo (fraccion del ancho): por debajo estas de lado o demasiado lejos
const FRONTPOS_MIN_THIGH_H = 0.06; // altura caderas->rodillas minima: por debajo no estas erguido
const FRONTPOS_WINDOW_MS = 900; // ventana sobre la que se mide 'te estas moviendo de sitio'
const FRONTPOS_SETTLED_MS = 650; // la ventana debe cubrir al menos esto de datos limpios para fiarse (evita armar justo al aparecer en encuadre)
const FRONTPOS_MAX_SWAY_X = 0.45; // recorrido horizontal del punto medio de caderas en la ventana, en anchos de hombros (marchar en el sitio da ~0.1-0.2)
const FRONTPOS_MAX_SWAY_Y = 0.35; // idem vertical (acercarte/alejarte o agacharte)
const FRONTPOS_MAX_SCALE_CHANGE = 0.14; // cambio relativo del ancho de hombros en la ventana (acercarte/alejarte de la camara)
const FRONTPOS_LOST_MS = 350; // fuera de posicion seguido esto => se descarta la subida en curso y se avisa (un parpadeo de 1-2 frames no)
const KNEERAISE_MAX_UP_SECONDS = 2; // una rodilla 'levantada' mas de esto no es marchar (es un paso o un equilibrio): se descarta sin contar
const HEELKICK_ARM_STEADY_MS = 400; // en su sitio, entero y de frente, sostenido esto (ademas de la ventana de FRONTPOS_SETTLED_MS) antes de armar
const HEELKICK_ARM_MAX_DIFF = 0.09; // mientras no esta armado se aprende el desnivel de reposo de los tobillos (camara/suelo torcidos) si la diferencia es menor que esto
const HEELKICK_MAX_UP_SECONDS = 1.5; // un talon 'arriba' mas de esto no es un talon al gluteo de marcha (es un paso, o estirar el cuadriceps): se descarta
const HEELKICK_HIDDEN_ONLY_MIN_SECONDS = 0.2; // subida sostenida SOLO por 'tobillo oculto' (sin desnivel real) debe durar al menos esto para contar
'''

POSCHECK = r'''  /**
   * 2026-09-19 (frontpos-v1): compuerta de posicion compartida por rodillas altas y talones al gluteo (de frente).
   * Devuelve {ok, reason, msg} si NO estas bien colocado (cuerpo entero visible y dentro del encuadre, erguido, de
   * frente, a buena distancia), o {ok:true, moving, settled, swayX, swayY, scale} si lo estas.
   * `moving` = te estas desplazando o acercando/alejando de la camara (ventana FRONTPOS_WINDOW_MS); `settled` = ya hay
   * datos limpios suficientes (FRONTPOS_SETTLED_MS) para fiarse de `moving`.
   * anklesMode: "both" = los dos pies deben verse dentro del encuadre; "one" = basta uno (el otro puede quedar
   * detras del gluteo en talones al gluteo).
   */
  frontPositionCheck(lm, now, anklesMode = "both") {
    const fail = (reason, msg) => ({ ok: false, moving: true, settled: false, reason, msg });
    const inFrame = (p) => p.x > FRONTPOS_EDGE_MARGIN && p.x < 1 - FRONTPOS_EDGE_MARGIN && p.y > FRONTPOS_EDGE_MARGIN && p.y < 1 - FRONTPOS_EDGE_MARGIN;
    const seen = (p) => !!p && (p.visibility ?? 1) >= FRONTPOS_MIN_VIS;
    const body = [L_SHOULDER, R_SHOULDER, L_HIP, R_HIP, L_KNEE, R_KNEE];
    for (const i of body) {
      if (!seen(lm[i])) return fail("cuerpo", "Colócate de frente a la cámara con el cuerpo entero a la vista: hombros, caderas, rodillas y pies. Aléjate un poco si hace falta.");
    }
    for (const i of body) {
      if (!inFrame(lm[i])) return fail("encuadre", "Te sales del encuadre. Aléjate un poco para que se te vea de los hombros a los pies.");
    }
    const lA = lm[L_ANKLE], rA = lm[R_ANKLE];
    const okL = seen(lA) && inFrame(lA), okR = seen(rA) && inFrame(rA);
    if (anklesMode === "both" ? !(okL && okR) : !(okL || okR)) {
      return fail("pies", "No se te ven los pies. Aléjate un poco para salir entero en el encuadre.");
    }
    const shMidY = (lm[L_SHOULDER].y + lm[R_SHOULDER].y) / 2;
    const hipMidX = (lm[L_HIP].x + lm[R_HIP].x) / 2;
    const hipMidY = (lm[L_HIP].y + lm[R_HIP].y) / 2;
    const kneeMidY = (lm[L_KNEE].y + lm[R_KNEE].y) / 2;
    const sw = Math.abs(lm[L_SHOULDER].x - lm[R_SHOULDER].x);
    if (sw < FRONTPOS_MIN_SHOULDER_W) return fail("lado", "Ponte de frente a la cámara, no de lado, y no te alejes demasiado.");
    if (hipMidY - shMidY < FRONTPOS_MIN_TORSO_H) return fail("lejos", "Acércate un poco a la cámara.");
    if (kneeMidY - hipMidY < FRONTPOS_MIN_THIGH_H) return fail("postura", "Ponte de pie, erguido, de frente a la cámara.");
    const lowestAnkleY = Math.max(okL ? lA.y : -1, okR ? rA.y : -1);
    if (lowestAnkleY < kneeMidY + 0.05) return fail("postura", "Ponte de pie, erguido, de frente a la cámara.");

    // Ventana de movimiento: punto medio de caderas + ancho de hombros (escala) en los ultimos FRONTPOS_WINDOW_MS.
    if (!this.frontPosSamples) this.frontPosSamples = [];
    const S = this.frontPosSamples;
    S.push({ t: now, x: hipMidX, y: hipMidY, w: sw });
    while (S.length > 1 && now - S[0].t > FRONTPOS_WINDOW_MS) S.shift();
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity, minW = Infinity, maxW = -Infinity, sumW = 0;
    for (const s of S) {
      if (s.x < minX) minX = s.x; if (s.x > maxX) maxX = s.x;
      if (s.y < minY) minY = s.y; if (s.y > maxY) maxY = s.y;
      if (s.w < minW) minW = s.w; if (s.w > maxW) maxW = s.w;
      sumW += s.w;
    }
    const avgW = sumW / S.length || sw;
    const swayX = (maxX - minX) / avgW;
    const swayY = (maxY - minY) / avgW;
    const scale = maxW / (minW || 1) - 1;
    const settled = now - S[0].t >= FRONTPOS_SETTLED_MS;
    const moving = swayX > FRONTPOS_MAX_SWAY_X || swayY > FRONTPOS_MAX_SWAY_Y || scale > FRONTPOS_MAX_SCALE_CHANGE;
    return { ok: true, moving, settled, swayX, swayY, scale };
  }

'''

HEEL_FN = r'''  /**
   * Talones al gluteo -- DE FRENTE a la camara (2026-09-19), de pie, marchando en el sitio: cada talon que sube hacia
   * el gluteo y vuelve a apoyarse cuenta UNA repeticion (antes: se vigilaba una sola pierna y cada ciclo sumaba DOS,
   * pensado para verse de perfil -- ya no hace falta, de frente se ven las dos piernas).
   *
   * Talon arriba = ese tobillo queda por encima del otro (fraccion de la longitud de pierna, con el desnivel de
   * reposo aprendido al armar) O el pie desaparece por detras (visibilidad del tobillo baja con la rodilla bien vista).
   * Solo una pierna 'arriba' a la vez; al volver a apoyarse se cuenta +1 y la siguiente subida puede ser de cualquier pierna.
   *
   * frontpos-v1 (2026-09-19): nada se arma ni se cuenta hasta verte entero (hombros a pies) dentro del encuadre, erguido,
   * de frente, y EN TU SITIO (ver frontPositionCheck) -- antes 'tobillo oculto' contaba aunque solo se viera la cara, y
   * caminar hacia la camara o hacia el boton colaba repeticiones falsas. Una repeticion se descarta si te moviste de sitio
   * mientras duraba, si el talon estuvo arriba demasiado rato (no es marcha), o si solo la sostuvo 'tobillo oculto' en
   * menos de HEELKICK_HIDDEN_ONLY_MIN_SECONDS.
   */
  processHeelKicks(lm, now) {
    const lHip = lm[L_HIP], rHip = lm[R_HIP];
    const lKnee = lm[L_KNEE], rKnee = lm[R_KNEE];
    const lAnkle = lm[L_ANKLE], rAnkle = lm[R_ANKLE];

    const vis = (
      (lHip.visibility ?? 1) + (rHip.visibility ?? 1) +
      (lKnee.visibility ?? 1) + (rKnee.visibility ?? 1) +
      (lAnkle.visibility ?? 1) + (rAnkle.visibility ?? 1)
    ) / 6;

    if (vis < HEELKICK_MIN_VISIBILITY) {
      this.announceStatus("No se te ve bien la cadera, la rodilla y el tobillo. Ponte de frente a la camara, con toda la pierna en el encuadre.");
      if (this.debugEl) this.debugEl.textContent = "buscando cadera, rodilla y tobillo de frente…";
      this.heelKickVisibleSince = null;
      this.heelKickSteadySince = null;
      this.noteAbsence(now, HEELKICK_OUT_OF_FRAME_MS);
      return;
    }
    this.outOfFrameSince = null;

    // Compuerta de posicion (ver frontPositionCheck): sin ella no se arma ni se cuenta nada.
    const pos = this.frontPositionCheck(lm, now, "one");
    if (!pos.ok) {
      if (this.frontPosBadSince == null) this.frontPosBadSince = now;
      const badFor = now - this.frontPosBadSince;
      if (badFor >= FRONTPOS_LOST_MS) {
        this.heelKickVisibleSince = null;
        this.heelKickSteadySince = null;
        this.heelKickUp = false;
        this.heelKickRepStart = null;
        this.announceStatus(pos.msg, "frontpos_" + pos.reason);
      }
      if (this.debugEl) this.debugEl.textContent = `fuera de posición (${pos.reason}) hace ${Math.round(badFor)}ms -- no cuenta nada hasta verte entero y de frente`;
      if (this.state !== null && this.heelKickLastActivityAt !== null && now - this.heelKickLastActivityAt >= HEELKICK_STILL_MS) {
        this.closeActiveSet();
        this.heelKickUp = false;
        this.heelKickRepStart = null;
      }
      return;
    }
    this.frontPosBadSince = null;
    const posDbg = ` | sway=${pos.swayX.toFixed(2)} y=${pos.swayY.toFixed(2)} esc=${pos.scale.toFixed(2)}${pos.settled ? "" : " (ajustando)"}`;

    if (this.heelKickVisibleSince === null) this.heelKickVisibleSince = now;
    if (now - this.heelKickVisibleSince < HEELKICK_VISIBLE_CONFIRM_MS) {
      if (this.debugEl) this.debugEl.textContent = "confirmando seguimiento…" + posDbg;
      return;
    }

    // Subida de cada tobillo respecto al otro, en fracciones de la longitud de pierna.
    const legLenH = Math.max(
      Math.hypot(lAnkle.x - lHip.x, lAnkle.y - lHip.y),
      Math.hypot(rAnkle.x - rHip.x, rAnkle.y - rHip.y)
    ) || 1;
    if ((lAnkle.visibility ?? 1) >= HEELKICK_ANKLE_SEEN_VIS) this.heelKickAnkleSeenAtL = now;
    if ((rAnkle.visibility ?? 1) >= HEELKICK_ANKLE_SEEN_VIS) this.heelKickAnkleSeenAtR = now;
    const hiddenL = (lAnkle.visibility ?? 1) < HEELKICK_ANKLE_HIDDEN_VIS && (lKnee.visibility ?? 1) >= HEELKICK_ANKLE_SEEN_VIS && now - (this.heelKickAnkleSeenAtL ?? -1e9) < HEELKICK_HIDDEN_MAX_MS;
    const hiddenR = (rAnkle.visibility ?? 1) < HEELKICK_ANKLE_HIDDEN_VIS && (rKnee.visibility ?? 1) >= HEELKICK_ANKLE_SEEN_VIS && now - (this.heelKickAnkleSeenAtR ?? -1e9) < HEELKICK_HIDDEN_MAX_MS;
    // rawDiff > 0 = el tobillo izquierdo va mas alto que el derecho.
    const rawDiff = (rAnkle.y - lAnkle.y) / legLenH;
    if (this.heelKickBias == null) this.heelKickBias = 0;
    if (!hiddenL && !hiddenR) {
      if (this.state === null) {
        if (Math.abs(rawDiff) < HEELKICK_ARM_MAX_DIFF) this.heelKickBias += 0.2 * (rawDiff - this.heelKickBias);
      } else if (Math.abs(rawDiff - this.heelKickBias) < 0.04) {
        this.heelKickBias += 0.02 * (rawDiff - this.heelKickBias);
      }
    }
    const diff = rawDiff - this.heelKickBias;
    let rawLiftL = diff, rawLiftR = -diff;
    // Con un tobillo oculto su 'y' no es fiable: el otro pie se da por apoyado (no puede 'subir' por culpa de un dato basura).
    if (hiddenL) rawLiftR = Math.min(rawLiftR, 0);
    if (hiddenR) rawLiftL = Math.min(rawLiftL, 0);
    let liftL = hiddenL ? Math.max(rawLiftL, HEELKICK_LIFT_HIDDEN_VALUE) : rawLiftL;
    let liftR = hiddenR ? Math.max(rawLiftR, HEELKICK_LIFT_HIDDEN_VALUE) : rawLiftR;
    this.heelKickSmoothAngleL = this.heelKickSmoothAngleL == null ? liftL : this.heelKickSmoothAngleL + HEELKICK_ANGLE_SMOOTHING_ALPHA * (liftL - this.heelKickSmoothAngleL);
    this.heelKickSmoothAngleR = this.heelKickSmoothAngleR == null ? liftR : this.heelKickSmoothAngleR + HEELKICK_ANGLE_SMOOTHING_ALPHA * (liftR - this.heelKickSmoothAngleR);
    liftL = this.heelKickSmoothAngleL;
    liftR = this.heelKickSmoothAngleR;

    if (this.state === null) {
      // Armado: en tu sitio, entero y de frente, sostenido HEELKICK_ARM_STEADY_MS (ademas de la ventana FRONTPOS_SETTLED_MS).
      // No exige las dos piernas apoyadas (marchando rapido casi nunca ocurre), solo estar quieto de sitio.
      const steady = pos.settled && !pos.moving;
      if (steady) {
        if (this.heelKickSteadySince == null) this.heelKickSteadySince = now;
      } else {
        this.heelKickSteadySince = null;
      }
      if (steady && now - this.heelKickSteadySince >= HEELKICK_ARM_STEADY_MS) {
        this.state = "active";
        this.heelKickSteadySince = null;
        this.heelKickLastActivityAt = now;
        this.heelKickUp = false;
        this.heelKickActiveSide = null;
        this.heelKickRepStart = null;
        this.heelKickRepTainted = false;
        if (!this.startupVoiceGiven) {
          this.startupVoiceGiven = true;
          this.announceStatus(
            "Piernas a la vista, de frente. ¡Listo! Lleva el talón hacia el glúteo, alternando las piernas. Para terminar, párate quieto un par de segundos, o sal del encuadre.",
            "startup_ready"
          );
        } else {
          this.setStatus("¡Listo! Lleva el talón hacia el glúteo, alternando las piernas.");
        }
      } else {
        this.setStatus(pos.moving ? "Quédate quieto en tu sitio un momento…" : "Te veo. Quieto un momento para empezar…");
        if (this.debugEl) this.debugEl.textContent = `esperando posición estable | ${steady ? "estable desde hace " + Math.round(now - this.heelKickSteadySince) + "ms" : "aún no estable"}${posDbg}`;
        return;
      }
    }

    // Serie en marcha: sin subida nueva ni repeticion completada durante HEELKICK_STILL_MS => has terminado.
    if (this.heelKickLastActivityAt !== null && now - this.heelKickLastActivityAt >= HEELKICK_STILL_MS) {
      this.closeActiveSet();
      this.heelKickUp = false;
      this.heelKickActiveSide = null;
      this.heelKickRepStart = null;
      return;
    }

    if (!this.heelKickUp) {
      const upL = liftL >= HEELKICK_LIFT_ENTER, upR = liftR >= HEELKICK_LIFT_ENTER;
      if (!pos.moving && (upL || upR)) {
        this.heelKickUp = true;
        this.heelKickActiveSide = (upL && upR) ? (liftL >= liftR ? "left" : "right") : (upL ? "left" : "right");
        this.heelKickRepStart = now;
        this.heelKickLastActivityAt = now;
        this.heelKickRepTainted = false;
        this.heelKickRepMaxRaw = 0;
      }
      if (this.debugEl) {
        this.debugEl.textContent =
          `esperando talón | izq=${liftL.toFixed(2)}${hiddenL ? " (oculto)" : ""} der=${liftR.toFixed(2)}${hiddenR ? " (oculto)" : ""} umbral_subida=${HEELKICK_LIFT_ENTER} | quieto desde hace: ${this.heelKickLastActivityAt ? Math.round(now - this.heelKickLastActivityAt) + "ms" : "-"}${posDbg}`;
      }
      return;
    }

    // Un talon esta arriba: ¿ha vuelto a apoyarse?
    const side = this.heelKickActiveSide || "left";
    const sideLabel = side === "left" ? "izquierda" : "derecha";
    const lift = side === "left" ? liftL : liftR;
    const rawLift = side === "left" ? rawLiftL : rawLiftR;
    const hidden = side === "left" ? hiddenL : hiddenR;
    if (pos.moving) this.heelKickRepTainted = true;
    if (rawLift > (this.heelKickRepMaxRaw || 0)) this.heelKickRepMaxRaw = rawLift;
    const upSeconds = (now - this.heelKickRepStart) / 1000;
    if (upSeconds > HEELKICK_MAX_UP_SECONDS) {
      // No es marcha (un paso, o estirar el cuadriceps): se descarta sin contar y sin cerrar la serie.
      this.heelKickUp = false;
      this.heelKickActiveSide = null;
      this.heelKickRepStart = null;
      if (this.debugEl) this.debugEl.textContent = `talón ${sideLabel} arriba ${upSeconds.toFixed(1)}s -- descartado (no es marcha)${posDbg}`;
      return;
    }
    if (lift > HEELKICK_LIFT_EXIT) {
      if (this.debugEl) {
        this.debugEl.textContent =
          `talón ${sideLabel} arriba subida=${lift.toFixed(2)} (bruta ${rawLift.toFixed(2)}, oculto=${hidden}) (umbral_bajada ${HEELKICK_LIFT_EXIT}) | quieto desde hace: ${this.heelKickLastActivityAt ? Math.round(now - this.heelKickLastActivityAt) + "ms" : "-"}${posDbg}`;
      }
      return;
    }

    const seconds = upSeconds;
    const tainted = this.heelKickRepTainted;
    const hiddenOnly = (this.heelKickRepMaxRaw || 0) < HEELKICK_LIFT_EXIT && seconds < HEELKICK_HIDDEN_ONLY_MIN_SECONDS;
    this.heelKickUp = false;
    this.heelKickActiveSide = null;
    this.heelKickRepStart = null;
    if (tainted || hiddenOnly) {
      if (this.debugEl) this.debugEl.textContent = `talón ${sideLabel} apoyado de nuevo -- rechazada (${tainted ? "te movías de sitio" : "solo 'tobillo oculto', demasiado corta"})${posDbg}`;
      return;
    }
    // +1 por cada talon que sube y baja (ya no se cuenta de 2 en 2).
    if (this.countRep(seconds, now, "Talón al glúteo", HEELKICK_MIN_REP_SECONDS)) {
      this.heelKickLastActivityAt = now;
    }
    if (this.debugEl) {
      this.debugEl.textContent = `talón ${sideLabel} apoyado de nuevo (+1)${posDbg}`;
    }
  }

'''

def patch(path, web):
    T = open(path, encoding='utf8').read()
    orig = T

    # ---- constantes
    m = re.search(r'^const HEELKICK_ANGLE_SMOOTHING_ALPHA = .*$', T, re.M)
    assert m
    T = T[:m.end()] + '\n' + CONSTS + T[m.end():]
    assert T.count('const KNEERAISE_STABLE_MS = 400;') == 1
    T = T.replace('const KNEERAISE_STABLE_MS = 400;', 'const KNEERAISE_STABLE_MS = 600; /* 2026-09-19 frontpos-v1: 400->600, ademas de la ventana FRONTPOS_SETTLED_MS */')

    # ---- posicion check: antes del doc de rodillas altas
    anchor = '  /**\n   * Rodillas altas -- DE PERFIL a la cámara'
    assert T.count(anchor) == 1
    T = T.replace(anchor, POSCHECK + anchor)

    # ---- rodillas altas
    s = T.index('  processKneeRaises(lm, now) {')
    e = T.index('  /**\n   * Talones al gluteo -- DE PERFIL')
    K = T[s:e]

    a = K.index('    this.outOfFrameSince = null;\n\n    // Un único aviso hablado')
    b_marker = '        "startup_ready"\n      );\n    }\n'
    b = K.index(b_marker, a) + len(b_marker)
    K = K[:a] + r'''    this.outOfFrameSince = null;

    // 2026-09-19 (frontpos-v1): compuerta de posicion (ver frontPositionCheck): sin verte entero, erguido, de frente y
    // en tu sitio no se arma ni se cuenta nada; caminar hacia la camara/el boton ya no cuela repeticiones falsas.
    const pos = this.frontPositionCheck(lm, now, "both");
    if (!pos.ok) {
      if (this.frontPosBadSince == null) this.frontPosBadSince = now;
      const badFor = now - this.frontPosBadSince;
      if (badFor >= FRONTPOS_LOST_MS) {
        this.kneeRaiseVisibleSince = null;
        this.kneeRaiseStableSince = null;
        this.kneeRaiseActiveSide = null;
        this.kneeRaiseRepStartTime = null;
        this.announceStatus(pos.msg, "frontpos_" + pos.reason);
      }
      if (this.debugEl) this.debugEl.textContent = `fuera de posición (${pos.reason}) hace ${Math.round(badFor)}ms -- no cuenta nada hasta verte entero y de frente`;
      if (this.state !== null && this.kneeRaiseLastActivityAt !== null && now - this.kneeRaiseLastActivityAt >= KNEERAISE_STILL_MS) {
        this.closeActiveSet();
        this.kneeRaiseActiveSide = null;
        this.kneeRaiseRepStartTime = null;
      }
      return;
    }
    this.frontPosBadSince = null;
    const posDbg = ` | sway=${pos.swayX.toFixed(2)} y=${pos.swayY.toFixed(2)} esc=${pos.scale.toFixed(2)}${pos.settled ? "" : " (ajustando)"}`;
''' + K[b:]

    old_arm = '''      const bothGrounded = dropFractionL >= KNEERAISE_RAISE_EXIT_FRACTION && dropFractionR >= KNEERAISE_RAISE_EXIT_FRACTION;
      if (bothGrounded) {
        if (this.kneeRaiseStableSince === null) this.kneeRaiseStableSince = now;
        if (now - this.kneeRaiseStableSince >= KNEERAISE_STABLE_MS) {
          this.state = "active";
          this.kneeRaiseStableSince = null;
          this.kneeRaiseActiveSide = null;
          this.kneeRaiseRepStartTime = null;
          this.kneeRaiseLastActivityAt = now;
        } else {
          this.setStatus("De pie, con las dos piernas apoyadas… confirmando (no te muevas)");
        }
      } else {
        this.kneeRaiseStableSince = null;
        this.setStatus("Ponte de pie, de frente a la cámara, con las dos piernas apoyadas, para empezar.");
      }'''
    new_arm = '''      const bothGrounded = dropFractionL >= KNEERAISE_RAISE_EXIT_FRACTION && dropFractionR >= KNEERAISE_RAISE_EXIT_FRACTION;
      const steady = pos.settled && !pos.moving;
      if (bothGrounded && steady) {
        if (this.kneeRaiseStableSince === null) this.kneeRaiseStableSince = now;
        if (now - this.kneeRaiseStableSince >= KNEERAISE_STABLE_MS) {
          this.state = "active";
          this.kneeRaiseStableSince = null;
          this.kneeRaiseActiveSide = null;
          this.kneeRaiseRepStartTime = null;
          this.kneeRaiseRepTainted = false;
          this.kneeRaiseLastActivityAt = now;
          if (!this.startupVoiceGiven) {
            this.startupVoiceGiven = true;
            this.announceStatus(
              "Piernas a la vista, de frente. ¡Listo! Marca el paso levantando las rodillas hacia el pecho. Para terminar, párate quieto un par de segundos, o sal del encuadre.",
              "startup_ready"
            );
          } else {
            this.setStatus("¡Listo! Marca el paso levantando las rodillas hacia el pecho.");
          }
        } else {
          this.setStatus("De pie, con las dos piernas apoyadas… confirmando (no te muevas)");
        }
      } else {
        this.kneeRaiseStableSince = null;
        this.setStatus(pos.moving ? "Quédate quieto en tu sitio un momento…" : "Ponte de pie, de frente a la cámara, con las dos piernas apoyadas, para empezar.");
      }'''
    assert K.count(old_arm) == 1
    K = K.replace(old_arm, new_arm)

    old = 'umbral=${KNEERAISE_RAISE_EXIT_FRACTION.toFixed(2)}`;'
    assert K.count(old) == 1
    K = K.replace(old, 'umbral=${KNEERAISE_RAISE_EXIT_FRACTION.toFixed(2)}` + posDbg;')
    old = '"ms" : "-"}`;'
    assert K.count(old) == 2, K.count(old)
    K = K.replace(old, '"ms" : "-"}` + posDbg;')

    old = '      if (raisedL || raisedR) {'
    assert K.count(old) == 1
    K = K.replace(old, '      if (!pos.moving && (raisedL || raisedR)) {')
    old = '        this.kneeRaiseLastActivityAt = now; // subida nueva empezada: ya cuenta como actividad\n'
    assert K.count(old) == 1
    K = K.replace(old, old + '        this.kneeRaiseRepTainted = false;\n')

    old = '''    if (dropFraction >= KNEERAISE_REARM_EXIT_FRACTION) {
      const seconds = (now - this.kneeRaiseRepStartTime) / 1000;
      if (this.countRep(seconds, now, "Rodilla arriba", KNEERAISE_MIN_REP_SECONDS)) {
        this.kneeRaiseLastActivityAt = now;
      }
      this.kneeRaiseActiveSide = null;
      this.kneeRaiseRepStartTime = null;
      if (this.debugEl) {
        this.debugEl.textContent = `pierna ${side === "left" ? "izquierda" : "derecha"} apoyada de nuevo | bajada_izq=${dropFractionL.toFixed(2)} bajada_der=${dropFractionR.toFixed(2)}`;
      }
      return;
    }'''
    new = '''    // frontpos-v1: si te moviste de sitio (caminar, acercarte/alejarte) durante esta subida, o la rodilla lleva
    // demasiado arriba para ser marcha, la repeticion NO cuenta.
    if (pos.moving) this.kneeRaiseRepTainted = true;
    if ((now - this.kneeRaiseRepStartTime) / 1000 > KNEERAISE_MAX_UP_SECONDS) {
      this.kneeRaiseActiveSide = null;
      this.kneeRaiseRepStartTime = null;
      if (this.debugEl) this.debugEl.textContent = `rodilla arriba demasiado rato -- descartada (no es marcha)` + posDbg;
      return;
    }
    if (dropFraction >= KNEERAISE_REARM_EXIT_FRACTION) {
      const seconds = (now - this.kneeRaiseRepStartTime) / 1000;
      const tainted = this.kneeRaiseRepTainted;
      if (!tainted && this.countRep(seconds, now, "Rodilla arriba", KNEERAISE_MIN_REP_SECONDS)) {
        this.kneeRaiseLastActivityAt = now;
      }
      this.kneeRaiseActiveSide = null;
      this.kneeRaiseRepStartTime = null;
      if (this.debugEl) {
        this.debugEl.textContent = `pierna ${side === "left" ? "izquierda" : "derecha"} apoyada de nuevo${tainted ? " -- rechazada (te movías de sitio)" : ""} | bajada_izq=${dropFractionL.toFixed(2)} bajada_der=${dropFractionR.toFixed(2)}` + posDbg;
      }
      return;
    }'''
    assert K.count(old) == 1
    K = K.replace(old, new)
    T = T[:s] + K + T[e:]

    # ---- talones al gluteo: reemplazo completo (doc + funcion)
    s = T.index('  /**\n   * Talones al gluteo -- DE PERFIL')
    e = T.index('  /**\n   * Rotación de brazo sujetando el codo')
    T = T[:s] + HEEL_FN + T[e:]

    # ---- init (beginPrep)
    old = '      this.kneeRaiseBias = null;\n'
    assert T.count(old) == 1, T.count(old)
    T = T.replace(old, old + '      this.kneeRaiseRepTainted = false;\n      this.frontPosBadSince = null;\n      this.frontPosSamples = [];\n')
    old = '      this.heelKickAnkleSeenAtR = null;\n      this.setStatus('
    assert T.count(old) == 1, T.count(old)
    T = T.replace(old, '      this.heelKickAnkleSeenAtR = null;\n      this.heelKickSteadySince = null;\n      this.heelKickActiveSide = null;\n      this.heelKickRepTainted = false;\n      this.heelKickRepMaxRaw = 0;\n      this.heelKickBias = null;\n      this.frontPosBadSince = null;\n      this.frontPosSamples = [];\n      this.setStatus(')

    # ---- build
    if web:
        old = '+hipforwardback-v3";'
        assert T.count(old) == 1
        T = T.replace(old, '+hipforwardback-v3+frontpos-v1";')
    else:
        old = 'const WORKOUT_JS_BUILD = "2026-09-04-log-buffer-x4";'
        assert T.count(old) == 1
        T = T.replace(old, 'const WORKOUT_JS_BUILD = "2026-09-19-frontpos-v1";')

    open(path, 'w', encoding='utf8', newline='').write(T)
    print('patched', path, len(orig), '->', len(T))

h = os.path.expanduser('~/mnt')
patch(h + '/mobile-app/www/js/workout.js', False)
patch(h + '/libreta-todo-django/static/js/workout.js', True)
