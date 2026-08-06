/* scheduler_queue_filter.js — Client-side exam type filter for scheduler queues.
 *
 * Pendentes tab: filters cards of ALL three groups that feed the primary
 * pending counter (WAIT_APPT + operational notices + operational issues).
 * Processados Hoje tab: simple type filter over processed cards.
 *
 * The selected type lives in radio buttons ([data-scheduler-exam-filter]) and
 * every filterable card exposes the persisted Case.exam_type via
 * data-exam-type. HTMX polling re-applies the filter on htmx:afterSwap
 * because the controls live outside #scheduler-queue-content.
 *
 * No dependencies, no persistence (no URL, storage, cookie or session).
 * No action depends on this filter — ACK forms and schedule links stay intact.
 */
(function () {
  "use strict";

  // ── DOM references (lazily resolved) ──────────────────────────────
  var statusEl = null;
  var noResultsEl = null;
  var typeButtons = [];

  function resolveElements() {
    statusEl = document.querySelector("[data-scheduler-queue-filter-status]");
    noResultsEl = document.querySelector("[data-scheduler-queue-no-results]");
    typeButtons = Array.prototype.slice.call(
      document.querySelectorAll("[data-scheduler-exam-filter]")
    );
  }

  // ── Helpers ───────────────────────────────────────────────────────

  /** Return all filterable cards currently in the DOM. */
  function getCards() {
    return document.querySelectorAll(
      "[data-scheduler-queue-card], [data-scheduler-processed-card]"
    );
  }

  /** Return the selected exam type: "all" | "eda" | "colonoscopy". */
  function getSelectedType() {
    for (var i = 0; i < typeButtons.length; i++) {
      if (typeButtons[i].checked) {
        return typeButtons[i].value;
      }
    }
    return "all";
  }

  /** Human label for the active scope. */
  function scopeLabel(type) {
    if (type === "eda") return "EDA";
    if (type === "colonoscopy") return "Colonoscopia";
    return "Todos";
  }

  /** Pluralize "caso"/"casos". */
  function pluralCasos(n) {
    return n !== 1 ? "casos" : "caso";
  }

  // ── Counters ──────────────────────────────────────────────────────

  /** Recompute per-type counters from the persisted card attribute. */
  function updateCounts() {
    var cards = getCards();
    var counts = { all: cards.length, eda: 0, colonoscopy: 0 };
    Array.prototype.forEach.call(cards, function (card) {
      var type = card.getAttribute("data-exam-type") || "";
      if (counts[type] !== undefined) counts[type]++;
    });
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-exam-type-count]"),
      function (el) {
        var type = el.getAttribute("data-exam-type-count") || "all";
        el.textContent = String(counts[type] !== undefined ? counts[type] : 0);
      }
    );
  }

  // ── Filter logic ──────────────────────────────────────────────────

  function applyFilter() {
    if (!statusEl || !noResultsEl) return;

    var type = getSelectedType();
    updateCounts();

    var cards = getCards();
    var total = cards.length;
    var visibleCount = 0;
    Array.prototype.forEach.call(cards, function (card) {
      var visible =
        type === "all" || (card.getAttribute("data-exam-type") || "") === type;
      card.hidden = !visible;
      if (visible) visibleCount++;
    });

    noResultsEl.style.display = "none";
    if (visibleCount === 0) {
      noResultsEl.style.display = "";
      statusEl.textContent = "";
      return;
    }
    var scope = type !== "all" ? " de " + scopeLabel(type) + "." : ".";
    if (visibleCount === total) {
      statusEl.textContent =
        "Mostrando todos os " + total + " " + pluralCasos(total) + scope;
    } else {
      statusEl.textContent =
        "Mostrando " + visibleCount + " de " + total + " " + pluralCasos(total) + scope;
    }
  }

  // ── Event handlers ────────────────────────────────────────────────

  function onTypeChange() {
    applyFilter();
  }

  /** Re-apply filter after HTMX swaps in fresh cards. */
  function onHtmxAfterSwap(e) {
    if (
      e &&
      e.detail &&
      e.detail.target &&
      e.detail.target.id === "scheduler-queue-content"
    ) {
      applyFilter();
    }
  }

  // ── Initialization ────────────────────────────────────────────────

  function init() {
    resolveElements();
    if (!statusEl || !noResultsEl) return; // not on a scheduler queue page

    typeButtons.forEach(function (btn) {
      btn.addEventListener("change", onTypeChange);
    });

    document.addEventListener("htmx:afterSwap", onHtmxAfterSwap);

    // Initial filter + counters in case of a prefilled selection.
    applyFilter();
  }

  // Run on DOMContentLoaded
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
