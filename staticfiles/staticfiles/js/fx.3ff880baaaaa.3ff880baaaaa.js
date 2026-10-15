/* Microinteracciones sobrias: ondulación al pulsar, completar con animación,
   entrada de listas y vibración suave en la app. Sin dependencias. */
(function () {
  "use strict";
  var doc = document, root = doc.documentElement;
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var isApp = !!window.Capacitor;

  function buzz(ms) {
    if (!isApp) return;
    try { navigator.vibrate && navigator.vibrate(ms); } catch (e) {}
  }

  /* 1 · Ondulación desde el punto de pulsación */
  var RIPPLE = ".primary-btn,.quick-add__button,.workout-btn,.ghost-btn,.check-btn,.range-chip,.category-chip,.task-card__delete,.task-card__delete button";
  doc.addEventListener("pointerdown", function (e) {
    if (reduce) return;
    var el = e.target.closest && e.target.closest(RIPPLE);
    if (!el || el.disabled) return;
    var r = el.getBoundingClientRect();
    var d = Math.max(r.width, r.height);
    el.classList.add("fx-host");
    var s = doc.createElement("span");
    s.className = "fx-ripple";
    s.style.left = (e.clientX - r.left) + "px";
    s.style.top = (e.clientY - r.top) + "px";
    s.style.setProperty("--fx-s", Math.max(8, d / 5));
    el.appendChild(s);
    setTimeout(function () { s.remove(); }, 560);
  }, { passive: true });

  /* 2 · Completar / marcar no hecha: animar antes de que la acción siga su curso */
  doc.addEventListener("click", function (e) {
    var btn = e.target.closest && e.target.closest(".check-btn--done, .check-btn--undone");
    if (!btn || btn.dataset.fxGo === "1") return;
    var card = btn.closest(".task-card");
    if (!card || reduce) { buzz(12); return; }
    e.preventDefault();
    e.stopImmediatePropagation();
    if (card.dataset.fxBusy === "1") return;
    card.dataset.fxBusy = "1";
    var done = btn.classList.contains("check-btn--done");
    card.classList.add(done ? "fx-completing" : "fx-failing");
    buzz(done ? 14 : 8);
    setTimeout(function () {
      btn.dataset.fxGo = "1";
      btn.click();
    }, done ? 440 : 340);
  }, true);

  /* 3 · Vibración ligera en acciones principales de la app */
  doc.addEventListener("click", function (e) {
    if (e.target.closest && e.target.closest(".workout-btn,.primary-btn,.tabbar a")) buzz(8);
  }, true);

  /* 4 · Entrada escalonada al abrir una pantalla */
  var t;
  function intro() {
    if (reduce) return;
    root.classList.add("fx-intro");
    clearTimeout(t);
    t = setTimeout(function () { root.classList.remove("fx-intro"); }, 900);
  }
  window.addEventListener("hashchange", intro);
  window.addEventListener("pageshow", intro);
  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", intro); else intro();
})();
