/**
 * Planes en la app.
 *
 * Tres pantallas con propósitos distintos:
 *
 *  - lista: qué planes tienes y cómo van
 *  - detalle: la revisión (el domingo, no cada día)
 *  - sesión: lo que haces hoy, sin elegir nada
 *
 * Lo importante es lo último: al pulsar el play de una tarea de plan se
 * entra directo aquí. El plan ya decidió qué ejercicios y con qué
 * objetivo, que es para lo que existe.
 */

import { api } from "./api.js";
import { READING_PLAN_FORM_IN_APP } from "./features.js";
import { needsWarmup } from "./warmup-view.js";
import { enterRunScreen } from "./run-screen.js";
import { failureChartHtml, bindFailureChart } from "./charts.js";

const view = document.getElementById("view");

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

/** "francés" -> "Francés" -- mismo capfirst que usa la web en los
 *  desplegables de idioma (plan_form.html: `{{ lang|capfirst }}`). */
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);

function topbar(eyebrow, title, backHref) {
  return `
    <header class="topbar">
      <div class="topbar__title">
        <span class="topbar__eyebrow">${esc(eyebrow)}</span>
        <h1>${esc(title)}</h1>
      </div>
      ${backHref ? `<a href="${backHref}" class="stats-link">← Volver</a>` : ""}
    </header>`;
}

/** El objetivo de un ejercicio, en texto. Running y Estudio no tienen
 *  series/repeticiones, así que llevan su propio formato — y Estudio
 *  puede tener start_sets/start_reps con el valor por defecto del
 *  modelo (3×8) sin que signifiquen nada, así que se mira primero si
 *  hay vídeo/playlist/minutos antes que las series. */
function targetText(i) {
  if (i.progression === "distance") {
    const dist = i.target_distance_km ? `${i.target_distance_km} km` : "";
    const pace = i.target_pace_seconds_per_km ? paceLabel(i.target_pace_seconds_per_km) : "";
    return [dist, pace].filter(Boolean).join(" a ") || "Sin objetivo";
  }
  if (i.requires_computer) return i.watch_site === "ilerna" ? "Clases de Ilerna (en el ordenador)" : "Curso de Udemy (en el ordenador)";
  if (i.youtube_playlist_id) return "Playlist de YouTube";
  if (i.youtube_video_id) return "Vídeo de YouTube";
  if (i.target_minutes) return `${i.target_minutes} min`;
  if (!i.slug) return "Cumplimiento diario";
  const peso = i.target_weight_kg ? ` · ${i.target_weight_kg} kg` : "";
  // "Al fallo" (PROG_FAILURE): ni target_reps ni target_seconds -- no hay
  // número de reps/segundos que pedir de antemano, solo el nº de series
  // (ver PlanItem.PROG_FAILURE en el backend). Antes esto caía al `|| i.work`
  // de abajo, que ni siquiera existe en este JSON (solo lo lleva el
  // formato de sesión de hoy) -- mostraba "3 × undefineds". Mismo texto
  // que ya usa el backend (WorkoutSession.target_label/PlanItem.__str__):
  // "N series al fallo".
  if (i.target_reps) return `${i.target_sets} × ${i.target_reps}` + peso;
  if (i.target_seconds) return `${i.target_sets} × ${i.target_seconds}s` + peso;
  if (i.target_sets) return `${i.target_sets} series al fallo` + peso;
  return "Sin objetivo" + peso;
}

/** Mismo listado que Task.PACE_PRESETS en el servidor. */
const PACE_PRESETS = [
  [900, "Paseo tranquilo (15:00/km)"],
  [720, "Paseo normal (12:00/km)"],
  [600, "Andar a paso ligero (10:00/km)"],
  [480, "Trote suave (8:00/km)"],
  [390, "Correr (6:30/km)"],
  [330, "Correr a buen ritmo (5:30/km)"],
  [270, "Correr rápido (4:30/km)"],
  [210, "Correr muy rápido (3:30/km)"],
];
function paceLabel(seconds) {
  const found = PACE_PRESETS.find(([s]) => s === seconds);
  if (found) return found[1].replace(/ \(.*\)/, "");
  const m = Math.floor(seconds / 60);
  const s = String(seconds % 60).padStart(2, "0");
  return `${m}:${s}/km`;
}

/**
 * Resumen de una semana (12 Week Year): done/total ya calculado por el
 * backend (ver Occurrence.weekly_completion en models.py). Duplicado a
 * propósito de app.js — mismo criterio que `esc`: cada vista es un
 * módulo suelto, sin depender de las demás.
 */
function weekSummary(weekly, label = "Esta semana") {
  if (!weekly) return "";
  const pct = weekly.pct;
  const bar =
    pct !== null
      ? `<div class="stats-bar"><div class="stats-bar__done" style="width:${pct}%"></div></div>`
      : "";
  const meta = weekly.total
    ? `${weekly.done} ${weekly.done === 1 ? "tarea" : "tareas"} de ${weekly.total} ${weekly.total === 1 ? "hecha" : "hechas"}`
    : "Todavía no hay tareas esta semana";
  return `
    <section class="week-summary" aria-label="Progreso de la semana">
      <div class="week-summary__top">
        <span class="week-summary__label">${esc(label)}</span>
        <span class="week-summary__pct">${pct !== null ? pct + "%" : "—"}</span>
      </div>
      ${bar}
      <p class="week-summary__meta">${esc(meta)}</p>
    </section>`;
}

// ------------------------------------------------------------- lista

/** "2026-03-02T10:15:00+01:00" -> "2 mar 2026" (para «Cerrado el …»). */
function shortDate(iso) {
  const d = iso ? new Date(iso) : null;
  if (!d || Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("es-ES", { day: "numeric", month: "short", year: "numeric" });
}

export async function renderPlanList() {
  view.innerHTML = `<p class="app-loading">Cargando planes…</p>`;
  const { data, fromCache } = await api.plans();
  // Igual que la web: los planes CERRADOS no se mezclan con los activos
  // (antes salían en la misma lista marcados como «pausado», que es otra
  // cosa), van aparte en «Planes cerrados» -- la misma que promete la
  // confirmación de «Cerrar plan».
  const openPlans = data.plans.filter((p) => !p.closed_at);
  const closedPlans = data.plans
    .filter((p) => p.closed_at)
    .sort((a, b) => String(b.closed_at).localeCompare(String(a.closed_at)));

  view.innerHTML = `
    ${topbar("progresión", "Planes")}
    <div class="plan-list-actions">
      <a class="primary-btn plan-list-actions__cta" href="#/plan-ia">✨ Generación automática</a>
      <div class="plan-list-actions__row">
        <a class="ghost-btn" href="#/plan-nuevo">+ Nuevo plan a mano</a>
        ${READING_PLAN_FORM_IN_APP ? `<a class="ghost-btn" href="#/lectura-plan">📖 Plan de lectura (PDF)</a>` : ""}
        <a class="ghost-btn" href="#/revision">Revisión semanal →</a>
        <a class="ghost-btn" href="#/retos">🏆 Retos</a>
      </div>
    </div>
    ${
      openPlans.length
        ? `<ul class="plan-list">${openPlans
            .map(
              (p) => `<li class="plan-card ${p.is_active ? "" : "plan-card--off"}">
                <a href="#/plan/${p.uuid}">
                  <p class="plan-card__name">${esc(p.name)}</p>
                  <p class="plan-card__meta">
                    Semana ${p.week} de ${p.weeks}${p.is_active ? "" : " · pausado"}
                  </p>
                  ${
                    p.headline
                      ? `<p class="plan-card__head">
                           ${esc(p.headline.name)}: <strong>${targetText(p.headline)}</strong>
                           ${p.headline.remaining ? `<span class="plan-item__left">faltan ${p.headline.remaining}</span>` : ""}
                         </p>`
                      : ""
                  }
                  ${
                    p.progress_pct !== null
                      ? `<div class="plan-bar"><div class="plan-bar__fill" style="width:${p.progress_pct}%"></div></div>`
                      : ""
                  }
                </a>
              </li>`
            )
            .join("")}</ul>`
        : `<p class="empty">
             Todavía no tienes planes. Un plan es un objetivo con progresión:
             al crearlo te aparece su tarea y solo tienes que darle al play.
           </p>`
    }
    ${
      closedPlans.length
        ? `<details class="done-details">
             <summary class="done-summary">Planes cerrados <span class="task-section__count">${closedPlans.length}</span></summary>
             <ul class="plan-list">${closedPlans
               .map((p) => {
                 // La «foto» del cierre; si el servidor es antiguo y no la
                 // manda, el progreso de ahora.
                 const pct = p.final_progress_pct !== undefined ? p.final_progress_pct : p.progress_pct;
                 return `<li class="plan-card plan-card--off">
                   <a href="#/plan-cerrar/${p.uuid}">
                     <p class="plan-card__name">
                       ${esc(p.name)}
                       <span class="count-pill ${p.is_completed ? "count-pill--done" : "count-pill--not-done"}">${p.is_completed ? "completado" : "incompleto"}</span>
                     </p>
                     <p class="plan-card__meta">Cerrado el ${esc(shortDate(p.closed_at))}</p>
                     ${
                       pct !== null && pct !== undefined
                         ? `<div class="plan-bar"><div class="plan-bar__fill" style="width:${pct}%"></div></div>
                            <p class="plan-card__meta">${pct}%</p>`
                         : ""
                     }
                   </a>
                 </li>`;
               })
               .join("")}</ul>
           </details>`
        : ""
    }`;
}

// ----------------------------------------------------------- detalle

export async function renderPlan(uuid) {
  view.innerHTML = `<p class="app-loading">Cargando…</p>`;
  const { data } = await api.plan(uuid);
  const p = data.plan;
  // Estudio · Idiomas no lleva PlanItem (p.headline sale null) -- el
  // "objetivo" es el temario entero (CourseModule), no un ejercicio o
  // hábito con progresión -- ver renderLanguagePlanConfirm / course_progress
  // en api.plan_json.
  const isLanguagePlan = p.plan_type === "study" && p.study_subtype === "language";
  const courseProgress = data.plan.course_progress;

  // Botones de un objetivo, como en la web: Editar / Quitar. Los objetivos de
  // Udemy/Ilerna se cambian desde el ordenador, así que ahí no hay Editar.
  const itemActions = (i) => `
      <div class="plan-item__actions">
        ${i.requires_computer ? "" : `<a class="ghost-btn" href="#/plan/${p.uuid}/objetivo/${i.id}">Editar</a>`}
        <button type="button" class="ghost-btn ghost-btn--danger" data-del-item="${i.id}">Quitar</button>
      </div>`;

  const itemBlock = (i) => `
    <article class="plan-item">
      <header class="plan-item__head">
        <h3>${esc(i.name)}</h3>
        <span class="plan-item__prog">escalón ${i.step + 1}</span>
      </header>
      <p class="plan-item__now">
        Hoy: <strong>${targetText(i)}</strong>
        ${i.remaining ? `<span class="plan-item__left">faltan ${i.remaining} sesiones</span>` : ""}
        ${i.done ? `<span class="plan-item__done">✓ destino</span>` : ""}
      </p>
      ${
        i.sessions_to_next_step && !i.done
          ? `<p class="plan-item__step-hint">Llevas ${i.sessions_into_step} de ${i.sessions_per_step} sesiones para subir al siguiente escalón</p>`
          : ""
      }
      ${itemActions(i)}
    </article>`;

  view.innerHTML = `
    ${topbar(`semana ${p.week} de ${p.weeks}`, p.name, "#/planes")}
    ${p.notes ? `<p class="plan-notes">${esc(p.notes)}</p>` : ""}

    ${
      p.plan_type === "sport"
        ? data.plan.items && data.plan.items.length
          ? p.progress_pct !== null
            ? `<section class="plan-head">
                 <p class="plan-head__eyebrow">Progreso del plan</p>
                 <div class="plan-bar"><div class="plan-bar__fill" style="width:${p.progress_pct}%"></div></div>
                 <p class="plan-head__meta">${p.progress_pct}% del camino · todos los objetivos cuentan por igual</p>
               </section>`
            : ""
          : `<p class="empty">Este plan todavía no tiene objetivo — añádelo para que la tarea diaria sepa qué hacer.</p>`
        : p.headline
        ? `<section class="plan-head">
             <p class="plan-head__eyebrow">Objetivo destacado</p>
             <h2 class="plan-head__name">${esc(p.headline.name)}</h2>
             <div class="plan-head__now">
               <span class="plan-head__label">Hoy te toca</span>
               <span class="plan-head__target">${targetText(p.headline)}</span>
             </div>
             ${
               p.progress_pct !== null
                 ? `<div class="plan-bar"><div class="plan-bar__fill" style="width:${p.progress_pct}%"></div></div>
                    <p class="plan-head__meta">${p.progress_pct}% del camino${
                     p.headline.remaining ? ` · faltan ${p.headline.remaining} sesiones` : ""
                   }</p>
                    ${
                      p.headline.sessions_to_next_step && !p.headline.done
                        ? `<p class="plan-head__meta">Llevas ${p.headline.sessions_into_step} de ${p.headline.sessions_per_step} sesiones para el siguiente escalón</p>`
                        : ""
                    }`
                 : ""
             }
             ${itemActions(p.headline)}
           </section>`
        : isLanguagePlan
          ? `<section class="plan-head">
               <p class="plan-head__eyebrow">Curso de idioma</p>
               <h2 class="plan-head__name">${esc(cap(p.language_name))} · nivel ${esc(p.level_from || "A1")} → ${esc(p.level_to || "C2")}</h2>
               ${
                 courseProgress && courseProgress.total === 0
                   // Sin ningún vídeo en el temario (algo falló al crearlo, plan antiguo):
                   // "0% · 0 de 0 vídeos" no dice qué hacer. Reasignarlos se hace en la web.
                   ? `<p class="plan-head__meta">Este curso todavía no tiene vídeos — algo falló al crearlo. Ábrelo en la web y pulsa «Reintentar asignar cursos del catálogo».</p>`
                   : p.progress_pct !== null
                   ? `<div class="plan-bar"><div class="plan-bar__fill" style="width:${p.progress_pct}%"></div></div>
                      <p class="plan-head__meta">${p.progress_pct}% del temario${
                       courseProgress ? ` · ${courseProgress.watched} de ${courseProgress.total} vídeos` : ""
                     }</p>`
                   : ""
               }
               ${courseProgress?.next_title ? `<p class="plan-head__meta">Hoy toca: ${esc(courseProgress.next_title)}</p>` : ""}
             </section>`
          : p.plan_type !== "general"
            ? `<p class="empty">Este plan todavía no tiene objetivo — añádelo para que la tarea diaria sepa qué hacer.</p>`
            : ""
    }

    ${failureChartHtml(data.plan.failure_chart)}

    ${
      p.requires_computer
        ? `<p class="field__hint">💻 Este plan cuenta el tiempo con la extensión de Chrome, así que su objetivo se cambia desde el ordenador. Aquí puedes ver el progreso.</p>`
        : ""
    }

    <div class="plan-actions">
      ${
        p.plan_type === "sport" || (p.plan_type === "study" && !isLanguagePlan && !p.requires_computer)
          ? `<a class="primary-btn" href="#/plan/${p.uuid}/objetivo-nuevo">+ Añadir objetivo</a>`
          : ""
      }
      <div class="plan-actions__row">
        <a class="ghost-btn" href="#/plan-editar/${p.uuid}">Editar plan</a>
        ${!p.closed_at ? `<a class="ghost-btn" href="#/plan-cerrar/${p.uuid}">Cerrar plan</a>` : ""}
      </div>
      <button type="button" class="ghost-btn ghost-btn--danger" id="delete-plan-btn">Eliminar plan</button>
    </div>

    ${
      p.plan_type === "sport" && data.plan.items && data.plan.items.length
        ? `<h2 class="section-title">Objetivos</h2>` + data.plan.items.map(itemBlock).join("")
        : data.plan.items && data.plan.items.length > 1
          ? `<h2 class="section-title">Resto de objetivos</h2>` +
            data.plan.items.filter((i) => !i.is_headline).map(itemBlock).join("")
          : ""
    }

    ${
      p.history && p.history.length
        ? `<h2 class="section-title">Lo que has hecho</h2>
           <table class="plan-table">
             <thead><tr><th>Día</th><th>Pedía</th><th>Hiciste</th><th>Logro</th></tr></thead>
             <tbody>${p.history
               .map(
                 (h) => `<tr>
                   <td>${esc(h.date)}</td><td>${esc(h.target)}</td><td>${esc(h.done)}</td>
                   <td>${
                     h.pct !== null
                       ? `<span class="plan-pct ${h.pct >= 100 ? "plan-pct--full" : "plan-pct--partial"}">${h.pct}%</span>`
                       : "—"
                   }</td>
                 </tr>`
               )
               .join("")}</tbody>
           </table>`
        : ""
    }`;

  bindFailureChart(view);

  view.querySelectorAll("[data-del-item]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      if (!confirm("¿Quitar este objetivo?")) return;
      try {
        await api.deletePlanItem(uuid, btn.dataset.delItem);
        api.clearCache();
        window.__toast?.("Objetivo eliminado.");
        renderPlan(uuid);
      } catch (err) {
        window.__toast?.(err.message, "error");
      }
    })
  );

  document.getElementById("delete-plan-btn")?.addEventListener("click", async () => {
    if (!confirm(`¿Eliminar «${p.name}»? Esto no se puede deshacer.`)) return;
    try {
      await api.deletePlan(uuid);
      api.clearCache();
      window.__toast?.("Plan eliminado.");
      location.hash = "#/planes";
    } catch (err) {
      window.__toast?.(err.message, "error");
    }
  });
}

// ------------------------------------------------------------ sesión

export async function renderPlanSession(taskUuid, planUuid) {
  view.innerHTML = `<p class="app-loading">Preparando la sesión…</p>`;
  const { data } = await api.planSession(taskUuid, planUuid);
  const { plan, items, task } = data;
  if (await needsWarmup(task)) {
    location.hash = `#/calentamiento/${taskUuid}?next=${encodeURIComponent(`/plan-sesion/${taskUuid}/${planUuid}`)}`;
    return;
  }

  // La tarea de un plan puede resolverse de tres formas muy distintas
  // (running por Health Connect, un vídeo, o un circuito de ejercicios
  // con cámara) — esto solía asumir SIEMPRE circuito, así que un plan
  // de running nunca encontraba nada que "jugar" aquí y se quedaba
  // colgado. Ahora se mira primero qué tipo de tarea es de verdad, y
  // se manda a la pantalla que ya sabe hacer eso — no hace falta
  // duplicar esa lógica aquí.
  if (task.workout_kind === "distance" || task.workout_kind === "video") {
    location.hash = `#/entreno/${taskUuid}`;
    return;
  }

  if (!items.length) {
    view.innerHTML = `
      ${topbar("sesión", plan.name, "#/")}
      <p class="empty">Este plan todavía no tiene ejercicios que entrenar.</p>`;
    return;
  }

  view.innerHTML = `
    ${topbar("sesión de hoy", plan.name, "#/")}
    <div class="circuit__mode-select" id="mode-select">
      <p class="circuit__mode-hint">${items.length} ejercicio(s) · esto es lo que te toca hoy</p>
      <ul class="run-preview">
        ${items
          .map(
            (i) => `<li>
              <span>${esc(i.name)}</span>
              <span>${targetText(i)}</span>
            </li>`
          )
          .join("")}
      </ul>
      <div class="circuit__mode-buttons">
        <button type="button" class="primary-btn" id="start-order">Empezar</button>
        <button type="button" class="ghost-btn" id="start-random">Aleatorio</button>
      </div>
      <p class="field__hint">Los objetivos suben solos cuando los vas cumpliendo.</p>
    </div>
    <div id="run-host"></div>`;

  let __mod;
  try {
    __mod = await import("./session-runner.js");
  } catch (impErr) {
    throw new Error(`No se pudo cargar ./session-runner.js: ${impErr.message}`);
  }
  const { SessionRunner, loadSessionDraft, clearSessionDraft } = __mod;
  // Clave de esta sesión (tarea + plan) para poder retomarla si hay que
  // salir a medias -- ver session-runner.js/saveDraft().
  const draftKey = `${taskUuid}:${planUuid}`;
  const draft = loadSessionDraft(draftKey);

  const onFinish = async (breakdown, meta = {}) => {
    try {
      // finish:false — la tarea no se cierra aquí, falta el
      // enfriamiento obligatorio (ver warmup-view.js).
      await api.savePlanSession(taskUuid, planUuid, {
        breakdown, finish: false, session_seconds: meta.session_seconds,
      });
      api.clearCache();
    } catch (err) {
      window.__toast?.(
        err.queued ? "Sin conexión: guardado y se enviará solo." : err.message,
        err.queued ? "info" : "error"
      );
    }
    location.hash = `#/enfriamiento/${taskUuid}`;
  };

  const begin = (list) => {
    document.getElementById("mode-select").hidden = true;
    const runner = new SessionRunner(document.getElementById("run-host"), list, onFinish, draftKey);
    enterRunScreen({ view, host: document.getElementById("run-host"), runner, label: targetText });
    // Si sales de la sesión a medias (← Volver, atrás, otra pestaña…), el
    // router llama a esto antes de pintar la siguiente pantalla -- para
    // los circuitos y el calentamiento ya paraba cámara/voz, aquí nunca
    // se había enganchado.
    window.__currentViewCleanup = () => runner.destroy();
    return runner;
  };

  // Sesión sin terminar de una vez anterior (se salió a medias, se cerró
  // la app, llamada, lo que sea) -- se ofrece continuar por donde se
  // dejó, en el mismo orden en que se estaba jugando entonces.
  if (draft) {
    if (confirm("Tienes una sesión de este plan sin terminar. ¿Quieres continuar donde la dejaste?")) {
      begin(draft.items).start({ index: draft.index, breakdown: draft.breakdown, elapsedMs: draft.elapsedMs });
    } else {
      clearSessionDraft(draftKey);
    }
  }

  document.getElementById("start-order").addEventListener("click", () => begin([...items]).start());
  document.getElementById("start-random").addEventListener("click", () =>
    begin([...items].sort(() => Math.random() - 0.5)).start()
  );
}

// -------------------------------------------------------- revisión semanal

export async function renderWeeklyReview() {
  view.innerHTML = `<p class="app-loading">Cargando la revisión…</p>`;
  const { data } = await api.weeklyReview();

  const planCard = (p) => `
    <li class="plan-card">
      <a href="#/plan/${p.uuid}">
        <p class="plan-card__name">${esc(p.name)}</p>
        <p class="plan-card__meta">Semana ${p.week} de ${p.weeks}</p>

        <p class="review-label">Ejecución de esta semana</p>
        ${
          p.weekly && p.weekly.total
            ? `<div class="stats-bar"><div class="stats-bar__done" style="width:${p.weekly.pct}%"></div></div>
               <p class="plan-card__head">${p.weekly.pct}% · ${p.weekly.done} ${p.weekly.done === 1 ? "sesión" : "sesiones"} de ${p.weekly.total}</p>`
            : `<p class="plan-card__head">Todavía no ha tocado esta semana.</p>`
        }

        ${
          p.progress_pct !== null
            ? `<p class="review-label">Camino hacia el objetivo</p>
               <div class="plan-bar"><div class="plan-bar__fill" style="width:${p.progress_pct}%"></div></div>
               <p class="plan-card__meta">${p.progress_pct}% recorrido</p>`
            : ""
        }
      </a>
    </li>`;

  view.innerHTML = `
    ${topbar("domingo, o cuando toque", "Revisión semanal", "#/planes")}
    ${weekSummary(data.weekly, "Global — todo lo que llevas")}
    <h2 class="section-title">Tus objetivos esta semana</h2>
    ${
      data.plans.length
        ? `<ul class="plan-list">${data.plans.map(planCard).join("")}</ul>`
        : `<p class="empty">No tienes objetivos activos ahora mismo.</p>`
    }`;
}

// -------------------------------------------------- crear/editar plan

const WEEKDAYS = [
  ["0", "Lunes"], ["1", "Martes"], ["2", "Miércoles"], ["3", "Jueves"],
  ["4", "Viernes"], ["5", "Sábado"], ["6", "Domingo"],
];
const PLAN_TYPES = [
  ["sport", "Deporte"], ["study", "Estudio"], ["general", "General"],
];
// Estudio · Idiomas -- mismo Plan.STUDY_SUBTYPE_CHOICES que la web.
// "" (Hábito simple) es el flujo normal (vídeo/playlist en el paso de
// objetivo, ver renderPlanItemForm); "language" arma un temario del
// catálogo verificado en dos pasos, ver renderPlanForm/renderLanguagePlanConfirm.
const STUDY_SUBTYPES = [
  ["", "Hábito simple — sin materia concreta"],
  ["language", "Idioma (curso con vídeos por nivel)"],
];
// Mismo MCER que Plan.CEFR_LEVEL_CHOICES en el servidor.
const CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];
// Mismos presets que plan_form.html en la web.
const DAILY_MINUTES_PRESETS = [
  [15, "15 min"], [30, "30 min"], [45, "45 min"], [60, "1 h"], [90, "1 h 30"], [120, "2 h"],
];
// Solo para el generador con IA (showAIPromptStep) -- Estudio se crea a
// mano ("+ Nuevo plan a mano"), no hace falta que la IA proponga nada
// ahí. PLAN_TYPES (con Estudio incluido) se queda igual para el
// formulario manual de creación/edición.
const AI_PLAN_TYPES = PLAN_TYPES.filter(([v]) => v !== "study");
// Cuestionario estructurado de Deporte — nivel, foco corporal, equipamiento,
// minutos y lesiones. Mismos valores que ai.FITNESS_LEVEL_CHOICES /
// ai.FOCUS_AREA_CHOICES en el backend: se le pasan a la IA como hechos en
// vez de esperar que los adivine de una frase corta como "ponerme en forma".
const FITNESS_LEVELS = [
  ["beginner", "Principiante"], ["intermediate", "Intermedio"], ["advanced", "Avanzado"],
];
const FOCUS_AREAS = [
  ["", "Cuerpo completo"], ["upper_body", "Tren superior"],
  ["lower_body", "Tren inferior / core"], ["running", "Running / cardio"],
];
// Mismo criterio que ai._NEEDS_BAR_EQUIPMENT en el servidor -- solo se usa
// aquí para el aviso "(barra/paralelas)" en el selector de ejercicios; el
// descarte de verdad (si "no tengo barra" está marcado) lo hace el propio
// backend en ai._select_sport_exercises / _select_exercises_from_slugs.
const NEEDS_BAR_SLUGS = new Set([
  "pullup", "wide-pullup", "chinup", "commando-pullup", "weighted-pullup", "wide-weighted-pullup", "jumping-pullup",
  "dips", "weighted-dips", "l-sit", "l-sit-hold", "toes-to-bar",
]);
// Mismos valores que ai.BODY_SEX_CHOICES en el backend.
const BODY_SEXES = [
  ["", "Prefiero no decirlo"], ["female", "Mujer"], ["male", "Hombre"],
];
const PACE_PRESETS_FULL = [
  [900, "Paseo tranquilo (15:00/km)"], [720, "Paseo normal (12:00/km)"],
  [600, "Andar a paso ligero (10:00/km)"], [480, "Trote suave (8:00/km)"],
  [390, "Correr (6:30/km)"], [330, "Correr a buen ritmo (5:30/km)"],
  [270, "Correr rápido (4:30/km)"], [210, "Correr muy rápido (3:30/km)"],
];

// ------------------------------------------------------ generar con IA

/** Fila de la tabla "semana a semana" de la vista previa, en texto. */
function aiWeekRow(row) {
  if (row.distance_km) return `${row.distance_km} km`;
  if (row.reps) return `${row.sets} × ${row.reps}${row.weight_kg ? ` · ${row.weight_kg} kg` : ""}`;
  if (row.seconds) return `${row.sets} × ${row.seconds}s`;
  // "Al fallo" (PROG_FAILURE): ni reps ni segundos, solo series -- mismo
  // texto que ya usa el backend (target_label) y targetText() más arriba.
  if (row.sets) return `${row.sets} series al fallo`;
  return "cumplir";
}

function aiProgLabel(p) {
  if (p.is_running) return "distancia";
  if (p.progression === "double") return "doble progresión";
  if (p.progression === "completion") return "cumplimiento";
  return "repeticiones";
}

/**
 * Pantalla en dos pasos, sin ruta propia para el segundo (el borrador
 * vive solo en memoria del navegador entre "generar" y "confirmar" — no
 * hace falta guardarlo en ningún sitio hasta que el usuario lo confirma).
 */
export async function renderPlanAI() {
  await showAIPromptStep();
}

async function showAIPromptStep(prefill = {}) {
  const planType = prefill.planType || "sport";
  const weeks = prefill.weeks || 12;
  const days = prefill.days || ["0", "2", "4"];
  const promptText = prefill.prompt || "";
  const fitnessLevel = prefill.fitnessLevel || "";
  const focusArea = prefill.focusArea || "";
  const noBarEquipment = prefill.noBarEquipment || false;
  const sessionMinutes = prefill.sessionMinutes || "";
  const limitations = prefill.limitations || "";
  const bodyWeightKg = prefill.bodyWeightKg || "";
  const heightCm = prefill.heightCm || "";
  const sex = prefill.sex || "";
  // Por defecto 20 (chaleco lastrado típico) -- obligatorio, igual que en
  // la web: así 0 sirve como señal explícita de "no tengo nada de peso
  // extra", que descarta dominadas/fondos/sentadillas con peso.
  const maxLoadKg = prefill.maxLoadKg ?? 20;
  const selectedExercises = prefill.selectedExercises || [];
  // Orden real de marcado (no el orden fijo del catálogo con el que se
  // pintan los checkboxes, agrupados por zona) — se actualiza con cada
  // clic más abajo y es lo que de verdad se manda como selected_exercises
  // al generar el plan (ver el listener de "submit" al final de esta
  // función). Semilla con selectedExercises tal cual: si venimos de un
  // intento anterior (prefill), ese SÍ es el orden real que se mandó.
  const exerciseOrder = selectedExercises.slice();

  // El selector de ejercicios concretos necesita el catálogo completo --
  // se pide antes de pintar el formulario, igual que ya hace
  // renderPlanItemForm más abajo en este mismo fichero.
  view.innerHTML = `<p class="app-loading">Cargando…</p>`;
  const { data: exData } = await api.exercises();
  const exerciseGroups = FOCUS_AREAS
    .filter(([value]) => value)
    .map(([value, label]) => ({
      value, label,
      items: exData.exercises.filter((ex) => ex.body_area === value),
    }))
    .filter((g) => g.items.length);

  view.innerHTML = `
    ${topbar("plan · auto", "Generación automática", "#/planes")}
    <p class="field__hint">
      Describe qué quieres conseguir y la IA propone un plan con objetivos
      medibles y su progresión semana a semana. Tú decides el tipo de plan,
      cuántas semanas dura y qué días entrenas — eso no lo toca la IA.
    </p>
    <form class="task-form" id="ai-form">
      <fieldset class="field">
        <legend class="field__label">Tipo de plan</legend>
        <div class="repeat-options">
          ${AI_PLAN_TYPES.map(
            ([v, l]) => `<label class="repeat-option">
              <input type="radio" name="plan_type" value="${v}" class="ai-plan-type-radio" ${planType === v ? "checked" : ""}>
              <span>${l}</span>
            </label>`
          ).join("")}
        </div>
      </fieldset>

      <div id="ai-sport-fields">
        <fieldset class="field">
          <legend class="field__label">Nivel físico de partida</legend>
          <div class="repeat-options">
            ${FITNESS_LEVELS.map(
              ([v, l]) => `<label class="repeat-option">
                <input type="radio" name="fitness_level" class="ai-fitness-level-radio" value="${v}" ${fitnessLevel === v ? "checked" : ""}>
                <span>${l}</span>
              </label>`
            ).join("")}
          </div>
          <span class="field__hint">Sin esto, la IA tira a lo mínimo seguro para no pasarse.</span>
        </fieldset>

        <fieldset class="field">
          <legend class="field__label">Foco corporal</legend>
          <div class="repeat-options">
            ${FOCUS_AREAS.map(
              ([v, l]) => `<label class="repeat-option">
                <input type="radio" name="focus_area" value="${v}" ${focusArea === v ? "checked" : ""}>
                <span>${l}</span>
              </label>`
            ).join("")}
          </div>
        </fieldset>

        <fieldset class="field">
          <legend class="field__label">Datos físicos (opcional, pero ayudan)</legend>
          <div class="field-row">
            <label class="field">
              <span class="field__label">Peso corporal (kg)</span>
              <input type="number" name="body_weight_kg" min="20" max="300" step="0.5" value="${esc(bodyWeightKg)}" placeholder="Ej: 75">
            </label>
            <label class="field">
              <span class="field__label">Altura (cm)</span>
              <input type="number" name="height_cm" min="100" max="250" value="${esc(heightCm)}" placeholder="Ej: 178">
            </label>
          </div>
          <div class="repeat-options">
            ${BODY_SEXES.map(
              ([v, l]) => `<label class="repeat-option">
                <input type="radio" name="sex" value="${v}" ${sex === v ? "checked" : ""}>
                <span>${l}</span>
              </label>`
            ).join("")}
          </div>
          <span class="field__hint">
            Un entrenador de verdad los tiene en cuenta: a igualdad de repeticiones en dominadas o
            fondos, alguien más pesado mueve más masa. No cambian tu nivel — solo afinan el punto
            de partida.
          </span>
        </fieldset>

        <label class="field field--inline">
          <input type="checkbox" name="no_bar_equipment" ${noBarEquipment ? "checked" : ""}>
          <span class="field__label">No tengo barra de dominadas ni paralelas en casa</span>
        </label>

        <div class="field-row">
          <label class="field">
            <span class="field__label">Minutos por sesión (opcional)</span>
            <input type="number" name="session_minutes" min="5" max="180" value="${esc(sessionMinutes)}" placeholder="Ej: 30">
          </label>
        </div>

        <label class="field">
          <span class="field__label">Peso máximo de lastre disponible en kg</span>
          <input type="number" name="max_load_kg" min="0" max="100" step="0.5" required value="${esc(maxLoadKg)}">
          <span class="field__hint">
            Pon 0 si no tienes nada de peso extra en casa (chaleco lastrado, discos...) — con 0,
            no se te van a proponer dominadas, fondos ni sentadillas con peso. Con un número, se
            usa como tope de la meta si el plan incluye alguno de esos ejercicios.
          </span>
        </label>

        <fieldset class="field" id="ai-exercises-field">
          <legend class="field__label">Ejercicios concretos (opcional)</legend>
          <span class="field__hint">
            Se filtra solo según el foco corporal de arriba: tren superior enseña
            solo tren superior, tren inferior/core solo eso, running solo running —
            cuerpo completo los enseña todos. Marca lo que quieras hacer y el plan
            se hace SOLO con eso (el nivel sigue usándose para calcular con qué
            series/repeticiones/peso empezar y hasta dónde llegar). Déjalo vacío
            para que la app elija por ti dentro de esa misma zona. El número que
            aparece al marcar uno es el orden en el que entrará en el plan —
            usa las flechitas para reordenarlos sin tener que desmarcar nada.
          </span>
          ${exerciseGroups
            .map(
              (g) => `
            <div class="exercise-group" data-body-area="${g.value}">
              <p class="field__label" style="margin-top:10px;">${esc(g.label)}</p>
              <div class="repeat-options">
                ${g.items
                  .map(
                    (ex) => `
                  <label class="repeat-option exercise-toggle">
                    <input type="checkbox" name="exercises" value="${ex.slug}" ${selectedExercises.includes(ex.slug) ? "checked" : ""}>
                    <span>${esc(ex.name)}${NEEDS_BAR_SLUGS.has(ex.slug) ? " (barra/paralelas)" : ""}</span>
                    <span class="exercise-toggle__order" hidden></span>
                    <span class="exercise-toggle__move" hidden>
                      <button type="button" class="exercise-toggle__move-btn" data-move="-1" aria-label="Subir en el orden">↑</button>
                      <button type="button" class="exercise-toggle__move-btn" data-move="1" aria-label="Bajar en el orden">↓</button>
                    </span>
                  </label>`
                  )
                  .join("")}
              </div>
            </div>`
            )
            .join("")}
        </fieldset>

        <label class="field">
          <span class="field__label">Lesión o limitación a tener en cuenta (opcional)</span>
          <input type="text" name="limitations" maxlength="200" value="${esc(limitations)}" placeholder="Ej: molestia en la rodilla derecha">
        </label>
      </div>

      <label class="field">
        <span class="field__label" id="ai-prompt-label">¿Qué quieres conseguir?</span>
        <textarea name="prompt" rows="4" maxlength="800" id="ai-prompt-textarea"
          placeholder="Ej: quiero ponerme fuerte de tren superior, ahora mismo hago 2 dominadas.">${esc(promptText)}</textarea>
        <span class="field__hint" id="ai-prompt-hint">Cuanto más concreto, mejor plan sale — di de dónde partes si lo sabes.</span>
      </label>
      <label class="field">
        <span class="field__label">Semanas</span>
        <input type="number" name="weeks" min="1" value="${weeks}">
      </label>
      <fieldset class="field">
        <legend class="field__label">Qué días entrenas</legend>
        <div class="repeat-options">
          ${WEEKDAYS.map(
            ([v, l]) => `<label class="repeat-option">
              <input type="checkbox" name="custom_days" value="${v}" ${days.includes(v) ? "checked" : ""}>
              <span>${l}</span>
            </label>`
          ).join("")}
        </div>
      </fieldset>
      <div class="task-form__actions">
        <button type="submit" class="primary-btn" id="ai-gen-btn">✨ Generar plan</button>
      </div>
    </form>`;

  // El cuestionario de nivel/foco/equipamiento solo pinta algo para
  // Deporte — Estudio y General no tienen catálogo de ejercicios. Se exige
  // el nivel (radios sin opción en blanco) para forzar una respuesta
  // concreta en vez de dejar que la IA la adivine de la frase libre. Con
  // nivel + foco ya hay suficiente para un plan serio, así que en Deporte
  // el texto libre pasa a ser opcional — Estudio y General no tienen
  // ningún otro campo, así que ahí sigue siendo obligatorio.
  const sportFields = document.getElementById("ai-sport-fields");
  const planTypeRadios = document.querySelectorAll(".ai-plan-type-radio");
  const fitnessLevelRadios = document.querySelectorAll(".ai-fitness-level-radio");
  const promptTextarea = document.getElementById("ai-prompt-textarea");
  const promptLabel = document.getElementById("ai-prompt-label");
  const promptHint = document.getElementById("ai-prompt-hint");
  function refreshSportFields() {
    let isSport = true;
    for (const r of planTypeRadios) if (r.checked) isSport = r.value === "sport";
    sportFields.style.display = isSport ? "block" : "none";
    for (const r of fitnessLevelRadios) r.required = isSport;
    promptTextarea.required = !isSport;
    if (isSport) {
      promptLabel.textContent = "¿Algo más que contarle a la IA? (opcional)";
      promptHint.textContent = "Con el nivel y el foco de arriba ya alcanza para un buen plan — añade esto solo si quieres precisar más (tu marca actual, un objetivo con fecha...).";
    } else {
      promptLabel.textContent = "¿Qué quieres conseguir?";
      promptHint.textContent = "Cuanto más concreto, mejor plan sale — di de dónde partes si lo sabes.";
    }
  }
  for (const r of planTypeRadios) r.addEventListener("change", refreshSportFields);
  refreshSportFields();

  // Filtra el selector de ejercicios según el foco corporal, igual que en
  // la web (plan_ai_form.html): los grupos que no tocan se DESACTIVAN (no
  // solo se esconden) para que, si tenías algo marcado ahí, no se envíe
  // igualmente al cambiar de foco sin querer -- pero sigue marcado por si
  // vuelves a esa zona.
  const exerciseGroupEls = document.querySelectorAll("#ai-exercises-field .exercise-group");
  const focusAreaRadios = document.querySelectorAll('input[name="focus_area"]');
  function refreshExerciseGroups() {
    let focus = "";
    for (const r of focusAreaRadios) if (r.checked) focus = r.value;
    exerciseGroupEls.forEach((group) => {
      const show = !focus || group.dataset.bodyArea === focus;
      group.style.display = show ? "" : "none";
      group.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
        cb.disabled = !show;
      });
    });
  }
  for (const r of focusAreaRadios) r.addEventListener("change", refreshExerciseGroups);
  refreshExerciseGroups();

  // Numera y permite reordenar los ejercicios marcados A LA VEZ que se van
  // marcando (en vez de un paso aparte). exerciseOrder (declarado arriba)
  // es lo que de verdad se manda como selected_exercises al generar el
  // plan — el orden de los checkboxes en el HTML es fijo (agrupados por
  // zona), así que sin esto el plan siempre salía en ese orden de
  // catálogo, nunca en el orden real en que se habían marcado.
  const exerciseCheckboxes = Array.from(document.querySelectorAll('#ai-exercises-field input[name="exercises"]'));
  function partsForExercise(cb) {
    const label = cb.closest("label");
    return { badge: label.querySelector(".exercise-toggle__order"), move: label.querySelector(".exercise-toggle__move") };
  }
  function renderExerciseOrder() {
    exerciseCheckboxes.forEach((cb) => {
      const idx = exerciseOrder.indexOf(cb.value);
      const { badge, move } = partsForExercise(cb);
      const on = idx !== -1;
      badge.hidden = !on;
      move.hidden = !on;
      if (on) badge.textContent = String(idx + 1);
    });
  }
  function moveExercise(slug, dir) {
    const idx = exerciseOrder.indexOf(slug);
    const target = idx + dir;
    if (idx === -1 || target < 0 || target >= exerciseOrder.length) return;
    const tmp = exerciseOrder[idx];
    exerciseOrder[idx] = exerciseOrder[target];
    exerciseOrder[target] = tmp;
    renderExerciseOrder();
  }
  exerciseCheckboxes.forEach((cb) => {
    cb.addEventListener("change", () => {
      const idx = exerciseOrder.indexOf(cb.value);
      if (cb.checked && idx === -1) exerciseOrder.push(cb.value);
      else if (!cb.checked && idx !== -1) exerciseOrder.splice(idx, 1);
      renderExerciseOrder();
    });
    // Los botones ↑/↓ viven DENTRO del <label> (para quedar pegados al
    // ejercicio) — sin frenar el evento aquí, el navegador reenviaría el
    // clic al checkbox del label y lo desmarcaría sin querer.
    partsForExercise(cb).move.querySelectorAll("[data-move]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        moveExercise(cb.value, parseInt(btn.dataset.move, 10));
      });
    });
  });
  renderExerciseOrder();

  document.getElementById("ai-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {
      plan_type: fd.get("plan_type") || "sport",
      prompt: fd.get("prompt"),
      weeks: parseInt(fd.get("weeks"), 10) || 12,
      custom_days: fd.getAll("custom_days"),
      fitness_level: fd.get("fitness_level") || "",
      focus_area: fd.get("focus_area") || "",
      no_bar_equipment: fd.get("no_bar_equipment") === "on",
      session_minutes: fd.get("session_minutes") ? parseInt(fd.get("session_minutes"), 10) : null,
      limitations: fd.get("limitations") || "",
      body_weight_kg: fd.get("body_weight_kg") ? parseFloat(fd.get("body_weight_kg")) : null,
      height_cm: fd.get("height_cm") ? parseInt(fd.get("height_cm"), 10) : null,
      sex: fd.get("sex") || "",
      max_load_kg: fd.get("max_load_kg") ? parseFloat(fd.get("max_load_kg")) : null,
      // exerciseOrder, no fd.getAll("exercises"): FormData.getAll devuelve
      // los checkboxes en el orden fijo en que aparecen en el HTML
      // (agrupados por zona corporal), no en el orden real en que se
      // fueron marcando. Se filtra a los que siguen marcados de verdad
      // (por si alguno quedó desactivado al cambiar de foco corporal).
      selected_exercises: exerciseOrder.filter((slug) => fd.getAll("exercises").includes(slug)),
    };
    const btn = document.getElementById("ai-gen-btn");
    btn.disabled = true;
    btn.textContent = "Generando… (puede tardar unos segundos)";
    try {
      // api.generatePlan (como todo lo que pasa por api.write/post) resuelve
      // el cuerpo de la respuesta tal cual -- {ok, draft} -- no envuelto en
      // {data}. Eso solo lo hace api.get. Desestructurar "data" aquí daba
      // undefined y reventaba en la siguiente línea con "Cannot read
      // properties of undefined (reading 'draft')".
      const { draft } = await api.generatePlan(payload);
      showAIPreviewStep(draft, payload);
    } catch (err) {
      window.__toast?.(err.message, "error");
      btn.disabled = false;
      btn.textContent = "✨ Generar plan";
    }
  });
}

function aiItemBlock(draft, it, idx) {
  const f = it.fields;
  const p = it.preview;
  const title = draft.plan_type === "sport" ? p.exercise_name : "Objetivo";
  let body = `
    <label class="field">
      <span class="field__label">Cómo llamarlo (opcional)</span>
      <input type="text" data-item="${idx}" data-key="label" maxlength="80" value="${esc(f.label || "")}">
    </label>`;

  if (draft.plan_type === "sport") {
    body += `
    `;

    if (p.is_running) {
      body += `
      <div class="field-row">
        <label class="field"><span class="field__label">Distancia partida (km)</span>
          <input type="number" step="0.1" min="0.1" data-item="${idx}" data-key="start_distance_km" value="${f.start_distance_km ?? ""}"></label>
        <label class="field"><span class="field__label">Distancia destino (km)</span>
          <input type="number" step="0.1" min="0.1" data-item="${idx}" data-key="goal_distance_km" value="${f.goal_distance_km ?? ""}"></label>
      </div>
      <div class="field-row">
        <label class="field"><span class="field__label">Ritmo partida (seg/km)</span>
          <input type="number" min="60" data-item="${idx}" data-key="start_pace_seconds_per_km" value="${f.start_pace_seconds_per_km ?? ""}"></label>
        <label class="field"><span class="field__label">Ritmo destino (seg/km)</span>
          <input type="number" min="60" data-item="${idx}" data-key="goal_pace_seconds_per_km" value="${f.goal_pace_seconds_per_km ?? ""}"></label>
      </div>`;
    } else {
      body += `
      <div class="field-row">
        <label class="field"><span class="field__label">Series partida</span>
          <input type="number" min="1" data-item="${idx}" data-key="start_sets" value="${f.start_sets ?? ""}"></label>
        ${
          p.is_timed
            ? `<label class="field"><span class="field__label">Segundos partida</span>
                 <input type="number" min="1" data-item="${idx}" data-key="start_seconds" value="${f.start_seconds ?? ""}"></label>`
            : `<label class="field"><span class="field__label">Repeticiones partida</span>
                 <input type="number" min="1" data-item="${idx}" data-key="start_reps" value="${f.start_reps ?? ""}"></label>`
        }
      </div>`;
      if (p.progression !== "completion") {
        body += `
        <div class="field-row">
          ${
            p.is_timed
              ? `<label class="field"><span class="field__label">Segundos destino</span>
                   <input type="number" min="1" data-item="${idx}" data-key="goal_seconds" value="${f.goal_seconds ?? ""}"></label>`
              : `<label class="field"><span class="field__label">Repeticiones destino</span>
                   <input type="number" min="1" data-item="${idx}" data-key="goal_reps" value="${f.goal_reps ?? ""}"></label>`
          }
        </div>`;
      }
      if (p.progression === "double") {
        body += `
        <div class="field-row">
          <label class="field"><span class="field__label">Peso partida (kg)</span>
            <input type="number" step="0.5" min="0" data-item="${idx}" data-key="start_weight_kg" value="${f.start_weight_kg ?? ""}"></label>
          <label class="field"><span class="field__label">Peso destino (kg)</span>
            <input type="number" step="0.5" min="0" data-item="${idx}" data-key="goal_weight_kg" value="${f.goal_weight_kg ?? ""}"></label>
        </div>`;
      }
    }
  } else {
    body += `
    <label class="field">
      <span class="field__label">Minutos objetivo por sesión (opcional)</span>
      <input type="number" min="1" data-item="${idx}" data-key="target_minutes" value="${f.target_minutes ?? ""}">
      <span class="field__hint">En blanco = sesión libre con temporizador manual.</span>
    </label>`;
  }

  const weekly = (p.weekly || []).length
    ? `<details class="plan-details">
         <summary>Ver progresión semana a semana</summary>
         <table class="plan-table">
           <thead><tr><th>Semana</th><th>Objetivo</th></tr></thead>
           <tbody>${p.weekly.map((row) => `<tr><td>${row.week}</td><td>${aiWeekRow(row)}</td></tr>`).join("")}</tbody>
         </table>
       </details>`
    : "";

  return `
    <section class="plan-item">
      <header class="plan-item__head">
        <h3>${esc(title)}</h3>
        ${draft.plan_type === "sport" ? `<span class="plan-item__prog">${aiProgLabel(p)}</span>` : ""}
      </header>
      ${body}
      ${weekly}
    </section>`;
}

function showAIPreviewStep(draft, genPayload) {
  view.innerHTML = `
    ${topbar("plan · auto · borrador", "Revisa tu plan", "#/planes")}
    <p class="field__hint">
      Esto es lo que propone la IA. Todavía no se ha guardado nada — puedes
      tocar cualquier número antes de confirmar, o pedir otra propuesta.
    </p>
    <form class="task-form" id="ai-confirm-form">
      <label class="field">
        <span class="field__label">Nombre del plan</span>
        <input type="text" id="ai-name" maxlength="80" required value="${esc(draft.plan_fields.name)}">
      </label>
      <label class="field">
        <span class="field__label">Notas</span>
        <textarea id="ai-notes" rows="2">${esc(draft.plan_fields.notes || "")}</textarea>
      </label>
      <label class="field">
        <span class="field__label">Hora</span>
        <input type="time" id="ai-due-time" required>
        <span class="field__hint">A esta hora avisa la app y, si sigue sin hacerse, se marca sola como no hecha.</span>
      </label>
      <label class="field">
        <span class="field__label">Recompensa al cerrar el ciclo (opcional)</span>
        <input type="text" id="ai-reward" maxlength="200" placeholder="Ej: unas zapatillas nuevas">
      </label>
      <p class="field__hint">
        ${draft.plan_fields.weeks} semanas · ${draft.plan_fields.custom_days.length} día${draft.plan_fields.custom_days.length === 1 ? "" : "s"} a la semana
        (esto ya no se cambia aquí — «Cambiar la petición» para elegir otro).
      </p>
      ${
        draft.plan_type === "general"
          ? `<p class="empty">Un plan General no lleva objetivos aparte — la propia tarea diaria es el hábito.</p>`
          : draft.items.map((it, idx) => aiItemBlock(draft, it, idx)).join("")
      }
      <div class="task-form__actions">
        <button type="submit" class="primary-btn">Guardar plan</button>
      </div>
    </form>
    <div class="task-form__actions" style="margin-top:8px;">
      <button type="button" class="ghost-btn" id="ai-regen-btn">↻ Generar otra vez</button>
      <button type="button" class="ghost-btn" id="ai-back-btn">Cambiar la petición</button>
    </div>`;

  document.getElementById("ai-back-btn").addEventListener("click", async () => {
    await showAIPromptStep({
      planType: draft.plan_type,
      weeks: draft.plan_fields.weeks,
      days: draft.plan_fields.custom_days.map(String),
      prompt: genPayload.prompt,
      fitnessLevel: genPayload.fitness_level,
      focusArea: genPayload.focus_area,
      noBarEquipment: genPayload.no_bar_equipment,
      sessionMinutes: genPayload.session_minutes,
      limitations: genPayload.limitations,
      bodyWeightKg: genPayload.body_weight_kg,
      heightCm: genPayload.height_cm,
      sex: genPayload.sex,
      maxLoadKg: genPayload.max_load_kg,
      selectedExercises: genPayload.selected_exercises,
    });
  });

  document.getElementById("ai-regen-btn").addEventListener("click", async () => {
    const btn = document.getElementById("ai-regen-btn");
    btn.disabled = true;
    btn.textContent = "Generando…";
    try {
      const { draft } = await api.generatePlan(genPayload);
      showAIPreviewStep(draft, genPayload);
    } catch (err) {
      window.__toast?.(err.message, "error");
      btn.disabled = false;
      btn.textContent = "↻ Generar otra vez";
    }
  });

  document.getElementById("ai-confirm-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    try {
      const planPayload = {
        name: document.getElementById("ai-name").value,
        notes: document.getElementById("ai-notes").value,
        plan_type: draft.plan_type,
        started_on: draft.plan_fields.started_on,
        weeks: draft.plan_fields.weeks,
        custom_days: draft.plan_fields.custom_days.map(String),
        due_time: document.getElementById("ai-due-time").value || null,
        is_active: true,
        reward: document.getElementById("ai-reward").value,
      };
      const { plan: createdPlan } = await api.createPlan(planPayload);
      const planUuid = createdPlan.uuid;

      for (let idx = 0; idx < (draft.items || []).length; idx++) {
        const itemFields = Object.assign({}, draft.items[idx].fields);
        view.querySelectorAll(`[data-item="${idx}"]`).forEach((el) => {
          const key = el.dataset.key;
          itemFields[key] = el.type === "checkbox" ? el.checked : (el.value.trim() || null);
        });
        await api.createPlanItem(planUuid, itemFields);
      }

      api.clearCache();
      window.__toast?.("Plan creado con generación automática.");
      location.hash = `#/plan/${planUuid}`;
    } catch (err) {
      btn.disabled = false;
      window.__toast?.(err.message, "error");
    }
  });
}

export async function renderPlanForm(uuid) {
  view.innerHTML = `<p class="app-loading">Cargando…</p>`;
  let plan = null;
  if (uuid) {
    const { data } = await api.plan(uuid);
    plan = data.plan;
  }
  const days = plan?.custom_days || ["0", "2", "4"];
  const isLanguagePlan = plan?.plan_type === "study" && plan?.study_subtype === "language";

  view.innerHTML = `
    ${topbar("plan", plan ? `Editar «${plan.name}»` : "Nuevo plan", plan ? `#/plan/${uuid}` : "#/planes")}
    <form class="task-form" id="plan-form">
      <label class="field">
        <span class="field__label">Nombre del objetivo</span>
        <input type="text" name="name" maxlength="80" required value="${esc(plan?.name || "")}" placeholder="Ponerme en forma">
      </label>
      <label class="field">
        <span class="field__label">Notas</span>
        <textarea name="notes" rows="2">${esc(plan?.notes || "")}</textarea>
      </label>
      <fieldset class="field">
        <legend class="field__label">Tipo de plan</legend>
        <div class="repeat-options">
          ${PLAN_TYPES.map(
            ([v, l]) => `<label class="repeat-option">
              <input type="radio" name="plan_type" value="${v}"
                ${(plan ? plan.plan_type === v : v === "sport") ? "checked" : ""}
                ${plan ? "disabled" : ""}>
              <span>${l}</span>
            </label>`
          ).join("")}
        </div>
        ${
          plan
            ? `<input type="hidden" name="plan_type" value="${plan.plan_type}">
               <span class="field__hint">El tipo no se puede cambiar una vez creado — crea uno nuevo si necesitas otro.</span>`
            : `<span class="field__hint">
                 Deporte: objetivos con progresión (ejercicios, running). Estudio: un
                 vídeo, playlist o temporizador que se completa cada día. General: un
                 hábito cualquiera, sin más. Los planes de Udemy, Ilerna y lectura (PDF)
                 se crean desde el ordenador.
               </span>`
        }
      </fieldset>

      <label class="field" id="study-subtype-field">
        <span class="field__label">Materia (opcional)</span>
        <select name="study_subtype" class="study-subtype-select" ${plan ? "disabled" : ""}>
          ${STUDY_SUBTYPES.map(
            ([v, l]) => `<option value="${v}" ${(plan ? (plan.study_subtype === v || (v === "" && !plan.study_subtype)) : v === "") ? "selected" : ""}>${l}</option>`
          ).join("")}
        </select>
        ${
          plan
            ? `<input type="hidden" name="study_subtype" value="${plan.study_subtype === "language" ? "language" : ""}">
               <span class="field__hint">No se puede cambiar una vez creado — crea un plan nuevo si necesitas otro.</span>`
            : `<span class="field__hint">
                 Idiomas: el plan se basa en llegar a un nivel MCER de un idioma concreto — el
                 siguiente paso asigna cursos ya verificados del catálogo (sin IA) para revisarlos
                 antes de guardar el plan.
               </span>`
        }
      </label>

      <div id="language-fields">
        <label class="field">
          <span class="field__label">Idioma</span>
          <select name="language_name" id="language-name-select">
            <option value="">— elige un idioma —</option>
            ${plan?.language_name ? `<option value="${esc(plan.language_name)}" selected>${esc(cap(plan.language_name))}</option>` : ""}
          </select>
          <span class="field__hint">
            Solo salen los idiomas con algún curso ya verificado en el catálogo.
          </span>
        </label>
        <div class="field-row">
          <label class="field">
            <span class="field__label">Nivel de partida</span>
            <select name="level_from">
              <option value="">— sin especificar (A1) —</option>
              ${CEFR_LEVELS.map((l) => `<option value="${l}" ${plan?.level_from === l ? "selected" : ""}>${l}</option>`).join("")}
            </select>
          </label>
          <label class="field">
            <span class="field__label">Nivel al que quieres llegar</span>
            <select name="level_to">
              <option value="">— sin especificar (C2) —</option>
              ${CEFR_LEVELS.map((l) => `<option value="${l}" ${plan?.level_to === l ? "selected" : ""}>${l}</option>`).join("")}
            </select>
          </label>
        </div>
        <fieldset class="field">
          <legend class="field__label">Idiomas que ya sabes</legend>
          <div class="repeat-options" id="known-languages-options"></div>
          <span class="field__hint">
            Marca todos los que sepas — se ofrecen los cursos explicados en cualquiera de ellos,
            más los neutros. Solo salen los idiomas nativos que ya usa algún curso.
          </span>
        </fieldset>
        <div class="field" id="daily-minutes-field">
          <span class="field__label">Minutos de vídeo al día</span>
          <div class="repeat-options" id="daily-minutes-presets">
            ${DAILY_MINUTES_PRESETS.map(
              ([m, l]) => `<label class="repeat-option">
                <input type="radio" name="daily_minutes_preset" value="${m}">
                <span>${l}</span>
              </label>`
            ).join("")}
            <label class="repeat-option">
              <input type="radio" name="daily_minutes_preset" value="custom">
              <span>Personalizado</span>
            </label>
          </div>
          <div class="field-row" id="daily-minutes-custom" hidden>
            <label class="field">
              <span class="field__label">Horas</span>
              <input type="number" min="0" max="12" id="daily-minutes-hours" placeholder="0">
            </label>
            <label class="field">
              <span class="field__label">Minutos</span>
              <input type="number" min="0" max="59" id="daily-minutes-minutes" placeholder="0">
            </label>
          </div>
          <input type="hidden" name="language_daily_minutes" id="language-daily-minutes-value"
            value="${plan?.language_daily_minutes || ""}">
          <p class="field__hint" id="daily-minutes-error" hidden>Elige cuántos minutos quieres ver al día.</p>
        </div>
        <label class="field">
          <span class="field__label">Test cada cuántos vídeos (opcional)</span>
          <input type="number" name="quiz_every_n_videos" min="1" placeholder="Ej: 1 (cada vídeo) o 5"
            value="${plan?.quiz_every_n_videos ?? ""}">
        </label>
      </div>

      <div class="field-row" id="weeks-field">
        <label class="field">
          <span class="field__label">Empieza el</span>
          <input type="date" name="started_on" value="${plan?.started_on || ""}">
        </label>
        <label class="field">
          <span class="field__label">Semanas</span>
          <input type="number" name="weeks" id="weeks-input" min="1" value="${plan?.weeks ?? 12}">
        </label>
      </div>
      <fieldset class="field">
        <legend class="field__label">Qué días</legend>
        <div class="repeat-options">
          ${WEEKDAYS.map(
            ([v, l]) => `<label class="repeat-option">
              <input type="checkbox" name="custom_days" value="${v}" ${days.includes(v) ? "checked" : ""}>
              <span>${l}</span>
            </label>`
          ).join("")}
        </div>
        <span class="field__hint">El plan crea su propia tarea con estos días.</span>
      </fieldset>
      <label class="field">
        <span class="field__label">Hora</span>
        <input type="time" name="due_time" value="${plan?.due_time || ""}" required>
        <span class="field__hint">A esta hora avisa la app y, si sigue sin hacerse, se marca sola como no hecha.</span>
      </label>
      <label class="field field--inline">
        <input type="checkbox" name="is_active" ${(plan ? plan.is_active : true) ? "checked" : ""}>
        <span class="field__label">Plan activo</span>
      </label>
      <label class="field">
        <span class="field__label">Recompensa al cerrar el ciclo (opcional)</span>
        <input type="text" name="reward" maxlength="200" placeholder="Ej: unas zapatillas nuevas" value="${esc(plan?.reward || "")}">
      </label>
      ${
        !plan
          ? `<p class="field__hint">
               Los objetivos (ejercicio y progresión en Deporte; vídeo o playlist en Estudio ·
               Hábito simple) se añaden en el siguiente paso. Estudio · Idiomas los asigna solo,
               del catálogo, y te los enseña para revisar antes de guardar. General no necesita
               ninguno.
             </p>`
          : ""
      }
      <div class="task-form__actions">
        <button type="submit" class="primary-btn">Guardar</button>
      </div>
    </form>`;

  // ---------------------------------------------- mostrar/ocultar según tipo

  const studySubtypeField = document.getElementById("study-subtype-field");
  const studySubtypeSelect = document.querySelector(".study-subtype-select");
  const languageFields = document.getElementById("language-fields");
  const weeksField = document.getElementById("weeks-field");
  const planTypeRadios = document.querySelectorAll('#plan-form [name="plan_type"]');

  function selectedPlanType() {
    return document.querySelector('#plan-form [name="plan_type"]:checked')?.value
      || (plan ? plan.plan_type : "sport");
  }
  function isLanguageSelected() {
    return selectedPlanType() === "study" && studySubtypeSelect.value === "language";
  }

  let languageOptionsLoaded = false;
  async function ensureLanguageOptions() {
    if (languageOptionsLoaded) return;
    languageOptionsLoaded = true;
    try {
      const { data } = await api.planLanguageOptions();
      const sel = document.getElementById("language-name-select");
      const current = sel.value;
      const existing = new Set(Array.from(sel.options).map((o) => o.value));
      data.languages.forEach((lang) => {
        if (existing.has(lang)) return;
        const opt = document.createElement("option");
        opt.value = lang;
        opt.textContent = cap(lang);
        sel.appendChild(opt);
      });
      if (current) sel.value = current;

      const knownWrap = document.getElementById("known-languages-options");
      const knownSelected = new Set((plan?.known_languages || "").split(",").map((s) => s.trim()).filter(Boolean));
      knownWrap.innerHTML = data.native_languages
        .map(
          (lang) => `<label class="repeat-option">
            <input type="checkbox" name="known_languages" value="${esc(lang)}" ${knownSelected.has(lang) ? "checked" : ""}>
            <span>${esc(cap(lang))}</span>
          </label>`
        )
        .join("");
    } catch (err) {
      window.__toast?.("No se pudo cargar el catálogo de idiomas — revisa la conexión.", "error");
    }
  }

  function refresh() {
    const isStudy = selectedPlanType() === "study";
    // "" y no "block": es un .field (columna flex con hueco); en block el selector quedaba
    // pegado a su etiqueta (3 px frente a los 8 px de los demás campos).
    studySubtypeField.style.display = isStudy ? "" : "none";
    const isLanguage = isStudy && studySubtypeSelect.value === "language";
    languageFields.style.display = isLanguage ? "block" : "none";
    // "" (no "flex"): #weeks-field es un .field-row (rejilla de 1 columna en móvil). Con
    // display:flex forzado los dos campos (fecha + número) no encogían y «Semanas» se salía
    // de la tarjeta por la derecha.
    weeksField.style.display = isLanguage ? "none" : "";
    if (isLanguage) ensureLanguageOptions();
  }
  planTypeRadios.forEach((r) => r.addEventListener("change", refresh));
  studySubtypeSelect.addEventListener("change", refresh);
  refresh();
  if (isLanguagePlan) ensureLanguageOptions();

  // ------------------------------------------------- minutos/día (idiomas)

  const dailyMinutesValue = document.getElementById("language-daily-minutes-value");
  const dailyMinutesPresets = document.querySelectorAll('input[name="daily_minutes_preset"]');
  const dailyMinutesCustom = document.getElementById("daily-minutes-custom");
  const dailyMinutesHours = document.getElementById("daily-minutes-hours");
  const dailyMinutesMinutes = document.getElementById("daily-minutes-minutes");
  const dailyMinutesError = document.getElementById("daily-minutes-error");

  function setDailyMinutes(minutes) {
    dailyMinutesValue.value = minutes || "";
    if (minutes) dailyMinutesError.hidden = true;
  }
  function updateFromCustom() {
    const h = parseInt(dailyMinutesHours.value, 10) || 0;
    const m = parseInt(dailyMinutesMinutes.value, 10) || 0;
    setDailyMinutes(h * 60 + m || "");
  }
  dailyMinutesPresets.forEach((input) => {
    input.addEventListener("change", function () {
      if (this.value === "custom") {
        dailyMinutesCustom.hidden = false;
        updateFromCustom();
      } else {
        dailyMinutesCustom.hidden = true;
        setDailyMinutes(parseInt(this.value, 10));
      }
    });
  });
  dailyMinutesHours.addEventListener("input", updateFromCustom);
  dailyMinutesMinutes.addEventListener("input", updateFromCustom);
  (function initDailyMinutes() {
    const current = parseInt(dailyMinutesValue.value, 10);
    if (!current) return;
    const preset = Array.from(dailyMinutesPresets).find((p) => parseInt(p.value, 10) === current);
    if (preset) {
      preset.checked = true;
      return;
    }
    const customRadio = Array.from(dailyMinutesPresets).find((p) => p.value === "custom");
    if (customRadio) customRadio.checked = true;
    dailyMinutesCustom.hidden = false;
    dailyMinutesHours.value = Math.floor(current / 60);
    dailyMinutesMinutes.value = current % 60;
  })();

  // ------------------------------------------------------------- envío

  document.getElementById("plan-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const isLanguage = isLanguageSelected();

    if (isLanguage && (!fd.getAll("known_languages").length || !dailyMinutesValue.value)) {
      if (!fd.getAll("known_languages").length) {
        window.__toast?.("Marca al menos un idioma que ya sepas.", "error");
      } else {
        dailyMinutesError.hidden = false;
        dailyMinutesError.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      return;
    }

    const basePayload = {
      name: fd.get("name"),
      notes: fd.get("notes"),
      plan_type: fd.get("plan_type"),
      started_on: fd.get("started_on") || null,
      weeks: parseInt(fd.get("weeks"), 10) || 12,
      custom_days: fd.getAll("custom_days"),
      due_time: fd.get("due_time") || null,
      is_active: Boolean(fd.get("is_active")),
      reward: fd.get("reward"),
    };
    const languagePayload = isLanguage
      ? {
          study_subtype: "language",
          language_name: fd.get("language_name"),
          level_from: fd.get("level_from"),
          level_to: fd.get("level_to"),
          known_languages: fd.getAll("known_languages").join(", "),
          language_daily_minutes: parseInt(dailyMinutesValue.value, 10) || null,
          quiz_every_n_videos: fd.get("quiz_every_n_videos") || null,
        }
      : {};

    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;

    // Idioma, al CREAR: en vez de guardar ya, se pide el borrador (asigna
    // cursos del catálogo, sin IA) y se enseña un paso de revisión antes
    // de guardar nada de verdad — igual que en la web (plan_form ->
    // plan_language_confirm). Al EDITAR un plan de idiomas ya creado no
    // se toca el temario, solo la metadata (mismo criterio que la web).
    if (isLanguage && !plan) {
      try {
        const { draft } = await api.planLanguageDraft({ ...basePayload, ...languagePayload });
        renderLanguagePlanConfirm(draft);
      } catch (err) {
        btn.disabled = false;
        window.__toast?.(err.message, "error");
      }
      return;
    }

    const payload = { ...basePayload, ...languagePayload };
    try {
      const { plan: savedPlan } = plan ? await api.updatePlan(uuid, payload) : await api.createPlan(payload);
      api.clearCache();
      window.__toast?.(plan ? "Plan actualizado." : "Plan creado.");
      location.hash = `#/plan/${savedPlan.uuid}`;
    } catch (err) {
      btn.disabled = false;
      window.__toast?.(err.message, "error");
    }
  });
}

// ------------------------------------------- revisar curso de idioma

/**
 * Paso 2 de crear un plan de Estudio · Idiomas a mano. Sin ruta propia,
 * igual que el borrador de "Generar con IA" (ver renderPlanAI): el
 * borrador vive solo en memoria, en el argumento `draft`, entre pedirlo
 * y confirmarlo — equivalente móvil de plan_language_confirm.html.
 */
function renderLanguagePlanConfirm(draft) {
  const f = draft.plan_fields;
  const levelLabel = `${f.level_from || "A1"} → ${f.level_to || "C2"}`;

  view.innerHTML = `
    ${topbar("plan · idioma", "Revisa el curso", "#/plan-nuevo")}
    <p class="field__hint">
      Esto es lo que se ha asignado del catálogo verificado, sin IA de por medio — puedes
      tocar el nombre y las notas antes de confirmar, o volver atrás y cambiar el idioma o el nivel.
    </p>
    <form class="task-form" id="language-confirm-form">
      <label class="field">
        <span class="field__label">Nombre del plan</span>
        <input type="text" name="name" maxlength="80" required value="${esc(f.name)}">
      </label>
      <label class="field">
        <span class="field__label">Notas</span>
        <textarea name="notes" rows="2">${esc(f.notes || "")}</textarea>
      </label>
      <label class="field">
        <span class="field__label">Hora</span>
        <input type="time" name="due_time" value="${esc(draft.due_time || "")}" required>
        <span class="field__hint">A esta hora avisa la app y, si sigue sin hacerse, se marca sola como no hecha.</span>
      </label>
      <label class="field">
        <span class="field__label">Recompensa al cerrar el ciclo (opcional)</span>
        <input type="text" name="reward" maxlength="200" placeholder="Ej: unas zapatillas nuevas" value="${esc(draft.reward || "")}">
      </label>
      <p class="field__hint">
        ≈${f.weeks} semana${f.weeks === 1 ? "" : "s"} estimadas a ${f.custom_days.length}
        día${f.custom_days.length === 1 ? "" : "s"} a la semana — no es una fecha límite: el curso
        sigue abierto hasta que termines todos los vídeos, tardes más o menos de lo estimado
        («← Cambiar idioma o nivel» para elegir otro ritmo).
      </p>
      <p class="field__hint">Idioma: ${esc(cap(f.language_name))} · nivel ${levelLabel}</p>
      ${
        draft.missing_levels && draft.missing_levels.length
          ? `<p class="plan-deload">
               Todavía no hay ningún curso verificado en el catálogo para: ${esc(draft.missing_levels.join(", "))}.
               El temario se salta esos niveles por ahora.
             </p>`
          : ""
      }
      <h2 class="section-title">Cursos asignados, en orden</h2>
      <p class="field__hint">
        Si hay varios cursos para el mismo nivel, se encadenan todos uno tras otro.
      </p>
      ${
        draft.selected.length
          ? draft.selected
              .map(
                (c, i) => `<section class="plan-item">
                  <header class="plan-item__head">
                    <h3>${i + 1}. ${esc(c.title)}</h3>
                    <span class="plan-item__prog">
                      ${c.level_to && c.level_to !== c.level ? `nivel ${c.level} → ${c.level_to}` : `nivel ${c.level}`}
                    </span>
                  </header>
                  <p class="field__hint">
                    Canal: ${esc(c.channel_title)} · unas ${c.weeks_allocated || 1} semana${(c.weeks_allocated || 1) === 1 ? "" : "s"}
                  </p>
                </section>`
              )
              .join("")
          : `<p class="empty-state">No se ha asignado ningún curso — vuelve atrás y prueba otro nivel.</p>`
      }
      <div class="task-form__actions">
        <button type="submit" class="primary-btn">Guardar plan</button>
      </div>
    </form>
    <div class="task-form__actions" style="margin-top:8px;">
      <a class="ghost-btn" href="#/plan-nuevo">← Cambiar idioma o nivel</a>
    </div>`;

  document.getElementById("language-confirm-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {
      ...draft,
      name: fd.get("name"),
      notes: fd.get("notes"),
      due_time: fd.get("due_time"),
      reward: fd.get("reward"),
    };
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    try {
      const { plan: savedPlan } = await api.planLanguageSave(payload);
      api.clearCache();
      window.__toast?.("Plan creado.");
      location.hash = `#/plan/${savedPlan.uuid}`;
    } catch (err) {
      btn.disabled = false;
      window.__toast?.(err.message, "error");
    }
  });
}

// ----------------------------------------------------- objetivo del plan

export async function renderPlanItemForm(planUuid, itemId) {
  view.innerHTML = `<p class="app-loading">Cargando…</p>`;
  const { data } = await api.plan(planUuid);
  const plan = data.plan;
  const item = itemId ? (plan.items || []).find((i) => String(i.id) === String(itemId)) : null;

  if (plan.plan_type === "general") {
    view.innerHTML = `
      ${topbar(plan.name, "Objetivo", `#/plan/${planUuid}`)}
      <p class="empty">Un plan General no necesita objetivos — la propia tarea diaria ya lo es.</p>`;
    return;
  }

  // Estudio · Idiomas no lleva PlanItem -- el temario entero (CourseModule)
  // se asignó ya al crear el plan, vía renderLanguagePlanConfirm. No hay
  // "objetivo" que añadir ni editar aquí, a diferencia de Hábito simple.
  if (plan.plan_type === "study" && plan.study_subtype === "language") {
    view.innerHTML = `
      ${topbar(plan.name, "Objetivo", `#/plan/${planUuid}`)}
      <p class="empty">
        Un curso de idioma no lleva objetivos aparte — el temario ya se asignó del
        catálogo al crear el plan. Edita el idioma o el nivel desde «Editar plan».
      </p>`;
    return;
  }

  if (plan.plan_type === "study" && (plan.requires_computer || item?.requires_computer)) {
    view.innerHTML = `
      ${topbar(plan.name, "Objetivo", `#/plan/${planUuid}`)}
      <p class="empty">
        💻 Los planes de Udemy e Ilerna se montan y se cambian desde el ordenador (los cuenta la
        extensión de Chrome). Desde aquí solo se ve el progreso.
      </p>`;
    return;
  }

  if (plan.plan_type === "study") {
    view.innerHTML = `
      ${topbar(plan.name, item ? "Editar objetivo" : "Nuevo objetivo", `#/plan/${planUuid}`)}
      <form class="task-form" id="item-form">
        <label class="field">
          <span class="field__label">Cómo llamarlo (opcional)</span>
          <input type="text" name="label" maxlength="80" value="${esc(item?.label || "")}">
        </label>
        <label class="field">
          <span class="field__label">Vídeo de YouTube</span>
          <input type="text" name="youtube_video_id" placeholder="https://youtube.com/watch?v=…" value="${esc(item?.youtube_video_id || "")}">
        </label>
        <label class="field">
          <span class="field__label">…o playlist (alternativa al vídeo suelto)</span>
          <input type="text" name="youtube_playlist_id" placeholder="https://youtube.com/playlist?list=…" value="${esc(item?.youtube_playlist_id || "")}">
          <span class="field__hint">
            Si pones esto, se ignora el vídeo de arriba. Cualquier playlist vale — un curso de
            ajedrez, tu lista de "ver más tarde"... — y la tarea diaria enseña el siguiente
            vídeo sin visto cada vez, sin volver siempre al principio (para eso hace falta
            poner minutos o vídeos al día, aquí abajo).
          </span>
        </label>
        <label class="field">
          <span class="field__label">Minutos al día${item?.youtube_playlist_id ? "" : " (opcional)"}</span>
          <input type="number" name="target_minutes" min="1" max="6000" placeholder="Ej: 20" value="${item?.target_minutes ?? ""}">
          <span class="field__hint">
            Se da por hecho el día al acumular ese tiempo. Con una playlist puesta, pon esto o
            el número de vídeos (el de abajo) — hace falta uno de los dos para saber qué toca
            cada día.
          </span>
        </label>
        <label class="field">
          <span class="field__label">…o vídeos al día${item?.youtube_playlist_id ? "" : " (opcional)"}</span>
          <input type="number" name="target_video_count" min="1" max="500" placeholder="Ej: 5" value="${item?.target_video_count ?? ""}">
          <span class="field__hint">Solo con playlist. Si rellenas esto, gana sobre el objetivo en minutos.</span>
        </label>
        <span class="field__hint">Sin vídeo ni playlist, el día se resuelve con un temporizador manual.</span>
        <div class="task-form__actions">
          <button type="submit" class="primary-btn">Guardar objetivo</button>
        </div>
      </form>`;

    document.getElementById("item-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const payload = {
        label: fd.get("label"),
        youtube_video_id: fd.get("youtube_video_id"),
        youtube_playlist_id: fd.get("youtube_playlist_id"),
        target_minutes: fd.get("target_minutes") || null,
        target_video_count: fd.get("target_video_count") || null,
      };
      // Con playlist, uno de los dos es obligatorio -- mismo aviso que
      // el backend (ver tasks/api.py _apply_plan_item_fields), pero
      // comprobado ya aquí para no esperar al viaje de ida y vuelta.
      if (payload.youtube_playlist_id && !payload.target_minutes && !payload.target_video_count) {
        window.__toast?.("Con una playlist, pon minutos al día o número de vídeos al día.", "error");
        return;
      }
      const btn = e.target.querySelector('button[type="submit"]');
      btn.disabled = true;
      try {
        if (item) await api.updatePlanItem(planUuid, item.id, payload);
        else await api.createPlanItem(planUuid, payload);
        api.clearCache();
        window.__toast?.("Objetivo guardado.");
        location.hash = `#/plan/${planUuid}`;
      } catch (err) {
        btn.disabled = false;
        window.__toast?.(err.message, "error");
      }
    });
    return;
  }

  // Deporte, a partir de aquí.
  const { data: exData } = await api.exercises();
  const exercises = exData.exercises;
  const sessionsPerWeek = Math.max(1, (plan.custom_days || []).length);
  const PROGRESSIONS = [
    ["completion", "Cumplimiento (objetivo fijo)"],
    ["reps", "Repeticiones (sube hasta un techo)"],
    ["double", "Doble (repeticiones y luego peso)"],
  ];

  view.innerHTML = `
    ${topbar(plan.name, item ? "Editar objetivo" : "Nuevo objetivo", `#/plan/${planUuid}`)}
    <form class="task-form" id="item-form">
      <label class="field">
        <span class="field__label">Ejercicio</span>
        <select name="exercise" id="exercise-select">
          <option value="">— elegir —</option>
          ${exercises
            .map(
              (ex) => `<option value="${ex.slug}" data-mode="${ex.mode}" ${item?.slug === ex.slug ? "selected" : ""}>${esc(ex.name)}</option>`
            )
            .join("")}
        </select>
      </label>
      <label class="field">
        <span class="field__label">Cómo llamarlo (opcional)</span>
        <input type="text" name="label" maxlength="80" value="${esc(item?.label || "")}">
      </label>

      <fieldset class="field" id="sport-mode-field">
        <legend class="field__label">¿Cómo la completas?</legend>
        <div class="repeat-options">
          <label class="repeat-option" data-mode-option="camera">
            <input type="radio" name="sport_mode" value="camera" ${item?.sport_mode === "camera" ? "checked" : ""}>
            <span>Contar con la cámara</span>
          </label>
          <label class="repeat-option" data-mode-option="circuit">
            <input type="radio" name="sport_mode" value="circuit" ${item?.sport_mode === "circuit" ? "checked" : ""}>
            <span>Circuito</span>
          </label>
          <label class="repeat-option" data-mode-option="video">
            <input type="radio" name="sport_mode" value="video" ${item?.sport_mode === "video" ? "checked" : ""}>
            <span>Vídeo</span>
          </label>
        </div>
      </fieldset>

      <div id="sport-video-fields" hidden>
        <label class="field">
          <span class="field__label">Vídeo de YouTube</span>
          <input type="text" name="youtube_video_id" placeholder="https://youtube.com/watch?v=…" value="${esc(item?.youtube_video_id || "")}">
        </label>
        <label class="field">
          <span class="field__label">…o playlist</span>
          <input type="text" name="youtube_playlist_id" placeholder="https://youtube.com/playlist?list=…" value="${esc(item?.youtube_playlist_id || "")}">
        </label>
        <span class="field__hint">
          Solo YouTube — un archivo del dispositivo no vale aquí, porque la
          tarea del plan se regenera cada día con un archivo distinto y
          perdería el vídeo a la mañana siguiente.
        </span>
      </div>

      <fieldset class="field" id="progression-field">
        <legend class="field__label">Cómo progresa</legend>
        <div class="repeat-options">
          ${PROGRESSIONS.map(
            ([v, l]) => `<label class="repeat-option">
              <input type="radio" name="progression" value="${v}" data-prog
                ${item ? (item.progression === v ? "checked" : "") : v === "reps" ? "checked" : ""}>
              <span>${l}</span>
            </label>`
          ).join("")}
        </div>
        <span class="field__hint" id="prog-hint"></span>
        <span class="field__hint" id="running-note" hidden>
          Este ejercicio es running — la progresión es siempre por distancia y ritmo, se elige más abajo.
        </span>
      </fieldset>

      <div id="distance-fields">
        <h2 class="section-title">Punto de partida</h2>
        <div class="field-row">
          <label class="field">
            <span class="field__label">Distancia (km)</span>
            <input type="number" name="start_distance_km" id="start-distance" min="0.1" step="0.1" value="${item?.start_distance_km ?? 1.0}">
          </label>
          <label class="field">
            <span class="field__label">A qué ritmo</span>
            <select name="start_pace_seconds_per_km" id="start-pace">
              <option value="3600" ${item?.start_pace_seconds_per_km === 3600 ? "selected" : ""}>Cualquier ritmo (solo cuentan los km)</option>
              ${PACE_PRESETS_FULL.map(([s, l]) => `<option value="${s}" ${item?.start_pace_seconds_per_km === s ? "selected" : ""}>${l}</option>`).join("")}
            </select>
          </label>
        </div>
        <h2 class="section-title">Destino</h2>
        <div class="field-row">
          <label class="field">
            <span class="field__label">Distancia (km)</span>
            <input type="number" name="goal_distance_km" id="goal-distance" min="0.1" step="0.1" value="${item?.goal_distance_km ?? ""}">
          </label>
          <label class="field">
            <span class="field__label">A qué ritmo</span>
            <select name="goal_pace_seconds_per_km" id="goal-pace">
              <option value="">Cualquier ritmo vale</option>
              ${PACE_PRESETS_FULL.map(([s, l]) => `<option value="${s}" ${item?.goal_pace_seconds_per_km === s ? "selected" : ""}>${l}</option>`).join("")}
            </select>
          </label>
        </div>
        <h2 class="section-title">Ritmo de progresión</h2>
        <label class="field">
          <span class="field__label">¿En cuántas semanas quieres llegar al destino?</span>
          <div class="field-row">
            <input type="number" id="weeks-distance" min="1" placeholder="Ej: 9" style="flex:1">
            <button type="button" class="ghost-btn" id="calc-distance-btn">Calcular</button>
          </div>
          <span class="field__hint">
            Con tus ${sessionsPerWeek} día${sessionsPerWeek === 1 ? "" : "s"} a la semana, calcula solo cuánto
            subir en cada escalón.
          </span>
        </label>
        <div class="field-row">
          <label class="field">
            <span class="field__label">Sesiones por escalón</span>
            <input type="number" name="sessions_per_step" id="sessions-per-step-distance" min="1" value="${item?.sessions_per_step ?? 2}">
          </label>
          <label class="field">
            <span class="field__label">Sube (km) cada escalón</span>
            <input type="number" name="distance_increment_km" id="distance-increment" min="0.1" step="0.1" value="${item?.distance_increment_km ?? 0.5}">
          </label>
        </div>
        <label class="field">
          <span class="field__label">Acelera (segundos por km) cada escalón</span>
          <input type="number" name="pace_decrement_seconds" id="pace-decrement" min="0" value="${item?.pace_decrement_seconds ?? 10}">
        </label>
      </div>

      <div id="strength-fields">
        <h2 class="section-title">Punto de partida</h2>
        <div class="field-row">
          <label class="field">
            <span class="field__label">Series</span>
            <input type="number" name="start_sets" min="1" value="${item?.start_sets ?? 3}">
          </label>
          <label class="field" data-when="reps">
            <span class="field__label">Repeticiones</span>
            <input type="number" name="start_reps" id="start-reps" min="1" value="${item?.start_reps ?? 8}">
          </label>
          <label class="field" data-when="seconds">
            <span class="field__label">Segundos</span>
            <input type="number" name="start_seconds" id="start-seconds" min="1" value="${item?.start_seconds ?? 40}">
          </label>
        </div>
        <label class="field" data-when="weight">
          <span class="field__label">Peso inicial (kg)</span>
          <input type="number" name="start_weight_kg" id="start-weight" min="0" step="0.5" value="${item?.start_weight_kg ?? 0}">
        </label>

        <h2 class="section-title" data-when="goal">Destino</h2>
        <div class="field-row" data-when="goal">
          <label class="field">
            <span class="field__label">Series</span>
            <input type="number" name="goal_sets" min="1" value="${item?.goal_sets ?? ""}">
          </label>
          <label class="field" data-when="reps">
            <span class="field__label">Repeticiones</span>
            <input type="number" name="goal_reps" id="goal-reps" min="1" value="${item?.goal_reps ?? ""}">
          </label>
          <label class="field" data-when="seconds">
            <span class="field__label">Segundos</span>
            <input type="number" name="goal_seconds" id="goal-seconds" min="1" value="${item?.goal_seconds ?? ""}">
          </label>
        </div>
        <label class="field" data-when="weight">
          <span class="field__label">Peso objetivo (kg)</span>
          <input type="number" name="goal_weight_kg" id="goal-weight" min="0" step="0.5" value="${item?.goal_weight_kg ?? ""}">
        </label>

        <h2 class="section-title" data-when="goal">Ritmo</h2>
        <label class="field" data-when="goal">
          <span class="field__label">¿En cuántas semanas quieres llegar al destino?</span>
          <div class="field-row">
            <input type="number" id="weeks-reps" min="1" placeholder="Ej: 12" style="flex:1">
            <button type="button" class="ghost-btn" id="calc-reps-btn">Calcular</button>
          </div>
          <span class="field__hint">
            Con tus ${sessionsPerWeek} día${sessionsPerWeek === 1 ? "" : "s"} a la semana, calcula cuánto subir
            cada escalón (o, en peso, cada cuántos ciclos añadir carga).
          </span>
        </label>
        <div class="field-row" data-when="goal">
          <label class="field">
            <span class="field__label">Sesiones por escalón</span>
            <input type="number" name="sessions_per_step" id="sessions-per-step-reps" min="1" value="${item?.sessions_per_step ?? 2}">
          </label>
          <label class="field" data-when="increment">
            <span class="field__label">Sube de</span>
            <input type="number" name="reps_increment" id="reps-increment" min="1" value="${item?.reps_increment ?? 1}">
          </label>
        </div>
        <div class="field-row" data-when="weight">
          <label class="field">
            <span class="field__label">Vuelve a</span>
            <input type="number" name="rep_range_low" id="rep-range-low" min="1" value="${item?.rep_range_low ?? 6}">
          </label>
          <label class="field">
            <span class="field__label">Añade (kg)</span>
            <input type="number" name="weight_increment_kg" id="weight-increment" min="0.5" step="0.5" value="${item?.weight_increment_kg ?? 2.5}">
          </label>
        </div>
        <label class="field" data-when="goal">
          <span class="field__label">Bajar escalón tras</span>
          <input type="number" name="deload_after_failures" min="0" value="${item?.deload_after_failures ?? 3}">
          <span class="field__hint">Sesiones seguidas sin llegar al objetivo antes de bajar un escalón. 0 lo desactiva.</span>
        </label>
      </div>

      <div class="task-form__actions">
        <button type="submit" class="primary-btn">Guardar objetivo</button>
        ${item ? `<button type="button" class="ghost-btn ghost-btn--danger" id="delete-item-btn">Quitar</button>` : ""}
      </div>
    </form>`;

  const HINTS = {
    completion: "Objetivo fijo, no sube nunca. Para hábitos o antitareas.",
    reps: "Sube hasta un techo y ahí se queda. Para abdominales, plancha, resistencia.",
    double: "Sube repeticiones y al llegar arriba añade peso y vuelve abajo. Para fuerza.",
  };
  const exSelect = document.getElementById("exercise-select");
  const esRunning = () => exSelect.options[exSelect.selectedIndex]?.dataset.mode === "distance";
  const esCronometrado = () => exSelect.options[exSelect.selectedIndex]?.dataset.mode === "timed";
  const prog = () => (esRunning() ? "distance" : document.querySelector("[data-prog]:checked")?.value || "reps");

  function actualizar() {
    const running = esRunning();
    const p = prog();
    const timed = esCronometrado();

    // El modo (cámara/circuito/vídeo) no aplica a running — ahí siempre
    // se resuelve por Health Connect o a mano.
    document.getElementById("sport-mode-field").hidden = running;
    if (running) document.querySelectorAll('[name="sport_mode"]').forEach((r) => (r.checked = false));
    const modo = running ? "" : document.querySelector('[name="sport_mode"]:checked')?.value || "";
    document.getElementById("sport-video-fields").hidden = modo !== "video";

    document.getElementById("progression-field").style.display = running ? "none" : "block";
    document.getElementById("running-note").hidden = !running;
    document.querySelectorAll("[data-prog]").forEach((r) => (r.disabled = running));
    document.getElementById("distance-fields").style.display = running ? "block" : "none";
    document.getElementById("strength-fields").style.display = running ? "none" : "block";
    if (running) return;

    document.getElementById("prog-hint").textContent = HINTS[p] || "";
    const visible = {
      reps: !timed, seconds: timed, weight: p === "double",
      goal: p !== "completion", increment: p !== "completion",
    };
    document.querySelectorAll("[data-when]").forEach((el) => {
      el.style.display = visible[el.dataset.when] === false ? "none" : "";
    });
  }
  document.querySelectorAll("[data-prog]").forEach((r) => r.addEventListener("change", actualizar));
  document.querySelectorAll('[name="sport_mode"]').forEach((r) => r.addEventListener("change", actualizar));
  exSelect.addEventListener("change", actualizar);
  actualizar();

  // "Cualquier ritmo" al empezar: solo cuentan los km, así que el ritmo de
  // destino no pinta nada (se vacía y se desactiva para que no se envíe).
  function sincronizarRitmoLibre() {
    const libre = parseInt(document.getElementById("start-pace").value, 10) >= 3600;
    const gp = document.getElementById("goal-pace");
    if (libre) gp.value = "";
    gp.disabled = libre;
  }
  document.getElementById("start-pace").addEventListener("change", sincronizarRitmoLibre);
  sincronizarRitmoLibre();

  // ---------------------------------------------- calculadora de ritmo
  // "¿En cuántas semanas?" en vez de "¿cuánto subir cada escalón?" —
  // el escalón sale solo a partir de ahí.
  function num(id) {
    const el = document.getElementById(id);
    return el ? parseFloat(el.value) || 0 : 0;
  }
  function escalones(weeks, porEscalon) {
    const totalSesiones = weeks * sessionsPerWeek;
    return Math.max(1, Math.round(totalSesiones / porEscalon));
  }

  document.getElementById("calc-distance-btn").addEventListener("click", () => {
    const weeks = num("weeks-distance");
    if (!weeks) { window.__toast?.("Pon primero en cuántas semanas quieres llegar.", "error"); return; }
    const pasos = escalones(weeks, num("sessions-per-step-distance") || 1);
    const dDist = num("goal-distance") - num("start-distance");
    const dPace = num("start-pace") >= 3600 ? 0 : num("start-pace") - num("goal-pace");
    let cambiado = false;
    if (dDist > 0) { document.getElementById("distance-increment").value = (dDist / pasos).toFixed(1); cambiado = true; }
    if (dPace > 0) { document.getElementById("pace-decrement").value = Math.max(1, Math.round(dPace / pasos)); cambiado = true; }
    if (!cambiado) {
      window.__toast?.('Pon primero la distancia y/o el ritmo de destino, en "Destino" — sin eso no hay nada que calcular.', "error");
    }
  });

  document.getElementById("calc-reps-btn").addEventListener("click", () => {
    const weeks = num("weeks-reps");
    if (!weeks) { window.__toast?.("Pon primero en cuántas semanas quieres llegar.", "error"); return; }
    const sesionesPorEscalon = num("sessions-per-step-reps") || 1;

    if (prog() === "double") {
      // El escalón es un ciclo entero del rango de repeticiones antes
      // de añadir peso, no una sesión suelta.
      const low = num("rep-range-low") || 6;
      const top = num("goal-reps") || low + 6;
      const span = Math.max(1, top - low + 1);
      const ciclos = Math.max(1, Math.round(escalones(weeks, sesionesPorEscalon) / span));
      const dPeso = num("goal-weight") - num("start-weight");
      if (dPeso > 0) {
        document.getElementById("weight-increment").value = (dPeso / ciclos).toFixed(1);
      } else {
        window.__toast?.('Pon primero el peso de destino, en "Destino" — sin eso no hay nada que calcular.', "error");
      }
      return;
    }

    const timed = esCronometrado();
    const startId = timed ? "start-seconds" : "start-reps";
    const goalId = timed ? "goal-seconds" : "goal-reps";
    const pasos = escalones(weeks, sesionesPorEscalon);
    const delta = num(goalId) - num(startId);
    if (delta > 0) {
      document.getElementById("reps-increment").value = Math.max(1, Math.round(delta / pasos));
    } else {
      window.__toast?.("Pon primero el destino (repeticiones o segundos), más arriba — sin eso no hay nada que calcular.", "error");
    }
  });

  document.getElementById("item-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {};
    for (const [k, v] of fd.entries()) {
      payload[k] = v;
    }
    payload.exercise = fd.get("exercise") || "";
    payload.progression = esRunning() ? "distance" : fd.get("progression");
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    try {
      if (item) await api.updatePlanItem(planUuid, item.id, payload);
      else await api.createPlanItem(planUuid, payload);
      api.clearCache();
      window.__toast?.("Objetivo guardado.");
      location.hash = `#/plan/${planUuid}`;
    } catch (err) {
      btn.disabled = false;
      window.__toast?.(err.message, "error");
    }
  });

  document.getElementById("delete-item-btn")?.addEventListener("click", async () => {
    if (!confirm("¿Quitar este objetivo?")) return;
    try {
      await api.deletePlanItem(planUuid, item.id);
      api.clearCache();
      window.__toast?.("Objetivo eliminado.");
      location.hash = `#/plan/${planUuid}`;
    } catch (err) {
      window.__toast?.(err.message, "error");
    }
  });
}

// -------------------------------------------------------- cierre de ciclo

export async function renderPlanClose(uuid) {
  view.innerHTML = `<p class="app-loading">Cargando…</p>`;
  const { data } = await api.plan(uuid);
  const p = data.plan;

  const closed = Boolean(p.closed_at);
  // Plan cerrado: el % que tenía AL CERRAR (la foto que guarda el servidor),
  // no el de ahora -- como la web. `!== undefined` por si el servidor es
  // antiguo y no lo manda todavía; null es un valor válido («sin medida»).
  const progress = closed && p.final_progress_pct !== undefined ? p.final_progress_pct : p.progress_pct;
  const completed = closed ? p.is_completed : progress !== null && progress >= 70;

  // Ver el resultado ES enterarse: la lista deja de avisar de este cierre.
  if (closed) api.planClosureSeen(uuid).then(() => api.clearCache()).catch(() => {});

  view.innerHTML = `
    ${topbar(closed ? "cerrado" : "cierre de ciclo", p.name, `#/plan/${uuid}`)}
    <section class="celebration">
      <p class="celebration__emoji">${closed ? (completed ? "🎉" : "🏳️") : "🏁"}</p>
      ${
        closed
          ? completed
            ? `<h2 class="celebration__title">¡Enhorabuena!</h2>
               <p class="celebration__text">Has completado «${esc(p.name)}» — ${p.week} semanas.</p>
               ${p.reward ? `<p class="celebration__reward">Y te has ganado tu recompensa: <strong>${esc(p.reward)}</strong></p>` : ""}`
            : `<h2 class="celebration__title">Ciclo terminado</h2>
               <p class="celebration__text">
                 «${esc(p.name)}» se cerró sin llegar al 70%${progress !== null ? ` (te quedaste en el ${progress}%)` : ""}.
                 No pasa nada — es un dato, no un fracaso.
               </p>
               ${p.reward ? `<p class="field__hint">La recompensa (${esc(p.reward)}) se queda para el próximo ciclo que sí llegue.</p>` : ""}`
          : `<h2 class="celebration__title">Resumen de «${esc(p.name)}»</h2>
             <p class="celebration__text">
               Antes de cerrarlo, así ha quedado${progress !== null ? ` — vas al ${progress}%` : ""}.
             </p>`
      }
    </section>
    ${
      progress !== null
        ? `<div class="plan-bar" role="img" aria-label="Progreso: ${progress}%"><div class="plan-bar__fill" style="width:${progress}%"></div></div>
           <p class="plan-head__meta">${progress}% del objetivo</p>`
        : ""
    }
    ${
      closed
        ? `<div class="task-form__actions"><a class="primary-btn" href="#/">Volver a Tareas</a></div>`
        : `<div class="task-form__actions">
             <button type="button" class="primary-btn" id="confirm-close-btn">Confirmar cierre</button>
             <a class="ghost-btn" href="#/plan/${uuid}">Seguir con el plan</a>
           </div>`
    }`;

  document.getElementById("confirm-close-btn")?.addEventListener("click", async () => {
    if (!confirm(`¿Cerrar «${p.name}»? Dejará de generarte tareas, pero se queda en Planes cerrados.`)) return;
    try {
      await api.closePlan(uuid);
      api.clearCache();
      renderPlanClose(uuid);
    } catch (err) {
      window.__toast?.(err.message, "error");
    }
  });
}

