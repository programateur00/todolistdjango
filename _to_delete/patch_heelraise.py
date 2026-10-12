import sys, shutil, re, os

CONST = r'''
// -- Elevación de talones (heel raise / calf raise), de pie ---------------------------------------------
// Pedido por Alex (2026-10-11). De pie, pies más o menos a la anchura de las caderas: se SUBE sobre la punta de los
// pies (los talones se despegan del suelo) y se baja. Una repetición = subir los talones y volver a apoyarlos.
// Se mide SOLO lo que sube el talón respecto a la punta del pie (que se queda en el suelo): por pie,
//   lift = media( punta.y - talón.y , punta.y - tobillo.y )   [en anchos de imagen, con el aspecto corregido]
// y se normaliza con el largo de pierna (cadera->tobillo). Al armar (de pie, quieto, talones apoyados) se guarda la
// lift de cada pie como "base" (la punta casi nunca está a la misma altura que el talón en reposo, depende del
// ángulo de la cámara), y todo se mide RELATIVO a esa base: así vale de frente y de perfil. Mismo criterio de
// vistas que kneeraises/heelkicks (de frente), pero sin exigirlo.
// Umbrales deducidos de la geometría (pierna de ~0.9 m, talón sube 6-12 cm -> 0.07-0.13 del largo de pierna;
// ruido de landmarks de pie ~0.02). PENDIENTES de afinar con un vídeo real de cámara.
const HEELRAISE_L_HEEL = 29, HEELRAISE_R_HEEL = 30;
const HEELRAISE_MIN_VISIBILITY = 0.5;       // talón, tobillo y punta de los dos pies para armar
const HEELRAISE_HIPS_MIN_VISIBILITY = 0.4;  // caderas para seguir (si no, cuenta como ausencia)
const HEELRAISE_FEET_LOST_VISIBILITY = 0.3; // armado: un pie con menos que esto se ignora (si no queda ninguno, frame ignorado)
const HEELRAISE_ARM_STABLE_MS = 700;        // de pie quieto, talones apoyados, antes de calibrar
const HEELRAISE_ARM_SETTLE_MS = 500;        // tras armar no se cuenta el primer acomodo
const HEELRAISE_ARM_MAX_JUMP = 0.05;        // salto de cadera por frame al armar, en largos de pierna
const HEELRAISE_ARM_MAX_LEG_DIFF = 0.20;    // al armar las dos piernas miden parecido
const HEELRAISE_UP = 0.045;                 // media de los pies: talón sube >=4.5% del largo de pierna -> "arriba"
const HEELRAISE_UP_EACH = 0.030;            // ...y CADA pie visible >=3% (un talón solo = andar, no vale)
const HEELRAISE_DOWN = 0.022;               // vuelta a "abajo": media <=2.2% -> cuenta la repetición
const HEELRAISE_MAX_UP_MS = 15000;          // arriba más de esto = se descarta y se vuelve a armar
const HEELRAISE_MIN_REP_SECONDS = 0.4;      // solo ruido de un frame suelto
const HEELRAISE_IDLE_CLOSE_MS = 8000;       // 8s sin repetir cierra la serie (como cossack/pistol); solo si ya hay reps
const HEELRAISE_BASE_ALPHA = 0.04;          // la base sigue a tu postura de pie (deriva lenta)...
const HEELRAISE_BASE_TRACK_BAND = 0.02;     // ...solo mientras estás claramente con los talones apoyados
const HEELRAISE_WAIT_MSG = "Ponte de pie, con los pies enteros (talones y puntas) en el encuadre y los talones apoyados en el suelo.";
'''

RESET = r'''    } else if (this.counterKey === "heelraise") {
      // Sin barra que calibrar: al armar se guarda la base talón-punta de cada pie y el largo de pierna
      // (ver el bloque HEELRAISE_* arriba).
      this.prepping = false;
      this.state = null;
      this.heelRaiseArmSince = null;
      this.heelRaisePrevHipY = null;
      this.heelRaiseAcc = null;
      this.heelRaiseRef = null;
      this.heelRaiseArmedAt = null;
      this.heelRaiseIdleSince = null;
      this.heelRaiseUpSince = null;
      this.setStatus(HEELRAISE_WAIT_MSG);
'''

METHOD = r'''  /**
   * Elevación de talones, de pie. Se mide cuánto sube cada talón respecto a la punta de su pie (ver el bloque
   * HEELRAISE_* de arriba), relativo a la base que se guarda al armar. Una repetición = subir los talones
   * (media >= HEELRAISE_UP y cada pie >= HEELRAISE_UP_EACH) y volver a apoyarlos (media <= HEELRAISE_DOWN).
   * Se cierra la serie tras HEELRAISE_IDLE_CLOSE_MS sin repetir.
   */
  processHeelRaise(lm, now) {
    const lH = lm[L_HIP], rH = lm[R_HIP];
    const feet = [
      { a: lm[L_ANKLE], h: lm[HEELRAISE_L_HEEL], t: lm[L_FOOT_INDEX], hip: lH },
      { a: lm[R_ANKLE], h: lm[HEELRAISE_R_HEEL], t: lm[R_FOOT_INDEX], hip: rH },
    ];
    const vis = (p) => (p ? (p.visibility ?? 1) : 0);

    // Cierre por inactividad: solo si ya hay reps en la serie y estás abajo (talones apoyados) esperando.
    if (this.state === "down" && this.currentSetReps > 0 && this.heelRaiseIdleSince !== null
      && now - this.heelRaiseIdleSince >= HEELRAISE_IDLE_CLOSE_MS) {
      this.closeActiveSet();
      return;
    }

    const hipsVis = Math.min(vis(lH), vis(rH));
    if (hipsVis < HEELRAISE_HIPS_MIN_VISIBILITY) {
      this.announceStatus("No se te ven las caderas. Ponte de pie, con las piernas enteras en el encuadre.", "heelraise_novis");
      if (this.debugEl) this.debugEl.textContent = `buscando caderas… vis ${hipsVis.toFixed(2)}`;
      this.heelRaiseArmSince = null;
      this.noteAbsence(now);
      return;
    }
    this.outOfFrameSince = null;

    const aspect = (this.video && this.video.videoWidth) ? (this.video.videoHeight / this.video.videoWidth) : 1.78;
    const dist = (a, b) => Math.hypot(a.x - b.x, (a.y - b.y) * aspect); // en unidades de ancho de imagen
    for (const f of feet) {
      f.vis = Math.min(vis(f.a), vis(f.h), vis(f.t));
      f.leg = dist(f.hip, f.a);
      // Lo que se levanta el talón/tobillo por encima de la punta del pie, en anchos de imagen (>0 = más arriba).
      f.lift = (((f.t.y - f.h.y) + (f.t.y - f.a.y)) / 2) * aspect;
    }
    const feetVis = Math.min(feet[0].vis, feet[1].vis);
    const hipY = (lH.y + rH.y) / 2;
    const avgLeg = (feet[0].leg + feet[1].leg) / 2;

    // --- Armar: de pie, quieto, talones apoyados, los dos pies enteros a la vista ---
    if (this.state === null) {
      const legsEven = Math.abs(feet[0].leg - feet[1].leg) <= HEELRAISE_ARM_MAX_LEG_DIFF * Math.max(feet[0].leg, feet[1].leg);
      const still = this.heelRaisePrevHipY != null
        && Math.abs(hipY - this.heelRaisePrevHipY) * aspect <= HEELRAISE_ARM_MAX_JUMP * avgLeg;
      this.heelRaisePrevHipY = hipY;
      if (feetVis >= HEELRAISE_MIN_VISIBILITY && legsEven && still) {
        if (this.heelRaiseArmSince == null) {
          this.heelRaiseArmSince = now;
          this.heelRaiseAcc = { l: 0, r: 0, leg: 0, n: 0 };
        }
        const a = this.heelRaiseAcc;
        a.l += feet[0].lift; a.r += feet[1].lift; a.leg += avgLeg; a.n += 1;
        if (now - this.heelRaiseArmSince >= HEELRAISE_ARM_STABLE_MS) {
          this.heelRaiseRef = { l: a.l / a.n, r: a.r / a.n, leg: a.leg / a.n };
          this.state = "down";
          this.heelRaiseArmSince = null;
          this.heelRaiseArmedAt = now;
          this.heelRaiseIdleSince = now;
          this.heelRaiseUpSince = null;
          this.announceStatus("¡Listo! Sube sobre las puntas de los pies y baja los talones.", "ready_to_go");
        } else {
          this.setStatus("De pie, talones apoyados… confirmando (no te muevas)");
        }
      } else {
        this.heelRaiseArmSince = null;
        this.setStatus(feetVis < HEELRAISE_MIN_VISIBILITY
          ? "No se te ven los pies. Aléjate un poco para que quepan las piernas enteras."
          : this.groundWaitingMessage());
      }
      if (this.debugEl) {
        this.debugEl.textContent = `[heelraise] armando — pies vis ${feetVis.toFixed(2)} | piernas ${feet[0].leg.toFixed(3)}/${feet[1].leg.toFixed(3)} | ` +
          `lift ${feet[0].lift.toFixed(3)}/${feet[1].lift.toFixed(3)} | parejas ${legsEven} quieto ${still}`;
      }
      return;
    }

    // Ya armado: pies fuera de encuadre un momento = frame ignorado. Los pies con poca visibilidad no cuentan.
    const used = feet.map((f, i) => ({ f, i })).filter(({ f }) => f.vis >= HEELRAISE_FEET_LOST_VISIBILITY);
    if (used.length === 0) return;

    const ref = this.heelRaiseRef;
    const refLeg = ref.leg;
    const rel = used.map(({ f, i }) => (f.lift - (i === 0 ? ref.l : ref.r)) / refLeg);
    const mean = rel.reduce((s, v) => s + v, 0) / rel.length;
    const minRel = Math.min(...rel);

    if (this.state === "down") {
      const settled = (now - this.heelRaiseArmedAt) >= HEELRAISE_ARM_SETTLE_MS;
      if (mean >= HEELRAISE_UP && minRel >= HEELRAISE_UP_EACH && settled) {
        this.state = "up";
        this.heelRaiseUpSince = now;
        this.repStartTime = now;
        this.setStatus("Arriba…");
      } else if (Math.abs(mean) <= HEELRAISE_BASE_TRACK_BAND) {
        // La base sigue a tu postura de pie (deriva lenta) mientras estás con los talones apoyados.
        const k = HEELRAISE_BASE_ALPHA;
        for (const { f, i } of used) {
          if (i === 0) ref.l = (1 - k) * ref.l + k * f.lift; else ref.r = (1 - k) * ref.r + k * f.lift;
        }
        ref.leg = (1 - k) * ref.leg + k * avgLeg;
      }
    } else if (this.state === "up") {
      if (now - this.heelRaiseUpSince > HEELRAISE_MAX_UP_MS) {
        // Llevas demasiado arriba: se descarta (no cuenta) y hay que volver a colocarse para armar de nuevo.
        this.state = null;
        this.heelRaiseArmSince = null;
        this.heelRaisePrevHipY = null;
        this.heelRaiseIdleSince = now;
        this.setStatus(this.groundWaitingMessage());
      } else if (mean <= HEELRAISE_DOWN) {
        this.countRep((now - this.repStartTime) / 1000, now, "Elevación de talones", HEELRAISE_MIN_REP_SECONDS);
        this.state = "down";
        this.heelRaiseIdleSince = now;
      }
    }

    if (this.debugEl) {
      this.debugEl.textContent =
        `[heelraise] subida media ${mean.toFixed(3)} (arriba ≥${HEELRAISE_UP}, abajo ≤${HEELRAISE_DOWN}) | cada pie ≥${HEELRAISE_UP_EACH}: ` +
        `${rel.map((v) => v.toFixed(3)).join("/")} | base ${ref.l.toFixed(3)}/${ref.r.toFixed(3)} | ` +
        `pies vis ${feetVis.toFixed(2)} | estado: ${this.state}`;
    }
  }

'''

def sub1(s, old, new, label):
    assert s.count(old) == 1, f"{label}: anchor count {s.count(old)}"
    return s.replace(old, new)

def patch_workout(path):
    s = open(path, encoding="utf-8").read()
    shutil.copy(path, path + ".bak-pre-heelraise")
    # 1. constants after COSSACKSQUAT_WAIT_MSG line
    m = re.search(r'^const COSSACKSQUAT_WAIT_MSG = .*\n', s, re.M)
    assert m, "WAIT_MSG"
    s = s[:m.end()] + CONST + s[m.end():]
    # 2. GROUND_STYLE_COUNTERS
    s = sub1(s, '"pistolsquat", "cossacksquat", "crunch"', '"pistolsquat", "cossacksquat", "heelraise", "crunch"', "GROUND")
    # 3. reset branch (before jumpingjack branch)
    s = sub1(s, '    } else if (this.counterKey === "jumpingjack") {\n      // Tampoco hay nada que calibrar',
             RESET + '    } else if (this.counterKey === "jumpingjack") {\n      // Tampoco hay nada que calibrar', "RESET")
    # 4. method before Jumping jacks doc
    s = sub1(s, '  /**\n   * Jumping jacks — DE FRENTE a la cámara, ciclo cerrado', METHOD + '  /**\n   * Jumping jacks — DE FRENTE a la cámara, ciclo cerrado', "METHOD")
    # 5. groundWaitingMessage case
    s = sub1(s, '      case "cossacksquat":\n        return "Ponte de pie, de frente',
             '      case "heelraise":\n        return HEELRAISE_WAIT_MSG;\n      case "cossacksquat":\n        return "Ponte de pie, de frente', "CASE")
    # 6. dispatch
    s = sub1(s, '    if (this.counterKey === "cossacksquat") {\n      this.processCossackSquat(lm, now);\n      return;\n    }\n',
             '    if (this.counterKey === "cossacksquat") {\n      this.processCossackSquat(lm, now);\n      return;\n    }\n'
             '    if (this.counterKey === "heelraise") {\n      this.processHeelRaise(lm, now);\n      return;\n    }\n', "DISPATCH")
    open(path, "w", encoding="utf-8", newline="").write(s)

for p in sys.argv[1:]:
    patch_workout(p)
    print("patched", p)
