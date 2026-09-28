/* scheduler_queue_filter.js — Client-side approved-dimension filter for scheduler queues.
 *
 * Pendentes tab: filters cards of ALL three groups that feed the primary
 * pending counter (WAIT_APPT + operational notices + operational issues).
 * Processados Hoje tab: simple dimension filter over processed cards.
 *
 * The queue filters by the AUTHORIZED procedure set (R5/D13). Every filterable
 * card exposes the projected selection via data-approved-selection; the legacy
 * bridge data-exam-type remains as fallback until cutover. Keys, labels and
 * counters are NOT listed here: the template renders one <option> per
 * catalog-derived option (data-exam-type-label) carrying its own counter
 * (data-exam-type-count) and this script reads and recomposes both from the DOM
 * (R7). The <select> filters on its "change" event — no extra action button.
 *
 * HTMX polling re-applies the filter on htmx:afterSwap because the controls
 * live outside #scheduler-queue-content.
 *
 * No dependencies, no persistence (no URL, storage, cookie or session).
 * No action depends on this filter — ACK forms and schedule links stay intact.
 */
(function () {
  "use strict";

  // ── DOM references (lazily resolved) ──────────────────────────────
  var statusEl = null;
  var noResultsEl = null;
  var typeSelect = null;

  function resolveElements() {
    statusEl = document.querySelector("[data-scheduler-queue-filter-status]");
    noResultsEl = document.querySelector("[data-scheduler-queue-no-results]");
    typeSelect = document.querySelector("select[data-scheduler-exam-filter]");
  }

  // ── Helpers ───────────────────────────────────────────────────────

  /** Return all filterable cards currently in the DOM. */
  function getCards() {
    return document.querySelectorAll(
      "[data-scheduler-queue-card], [data-scheduler-processed-card]"
    );
  }

  /** Selected <option> of the exam-type select (the rendered control owns the
   *  catalog keys, labels and counters — never a hardcoded list). */
  function selectedTypeOption() {
    if (!typeSelect) return null;
    return typeSelect.options[typeSelect.selectedIndex] || null;
  }

  /** Return the selected exam type (catalog selection key or "all"). */
  function getSelectedType() {
    return typeSelect && typeSelect.value ? typeSelect.value : "all";
  }

  /** Human label of the active scope, read from the selected option (R7). */
  function scopeLabel() {
    var option = selectedTypeOption();
    if (!option) return "Todos";
    return option.getAttribute("data-exam-type-label") || option.value || "Todos";
  }

  /** Pluralize "caso"/"casos". */
  function pluralCasos(n) {
    return n !== 1 ? "casos" : "caso";
  }

  /**
   * Return the approved dimension projected on the card (R5/D13): the
   * scheduler queue filters by the AUTHORIZED set (data-approved-selection),
   * falling back to the legacy bridge data-exam-type until cutover.
   */
  function cardSelection(card) {
    var selection = card.getAttribute("data-approved-selection");
    if (!selection) selection = card.getAttribute("data-exam-type") || "";
    return selection;
  }

  // ── Counters ──────────────────────────────────────────────────────

  /** Counter keys are read from the rendered elements (R7): the template emits
   *  one [data-exam-type-count] per catalog-derived option. */
  function emptyCounts() {
    var counts = {};
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-exam-type-count]"),
      function (el) {
        counts[el.getAttribute("data-exam-type-count") || "all"] = 0;
      }
    );
    return counts;
  }

  /** Recompute per-type counters from the projected card attribute and recompose
   *  each option text as "<base label> (<count>)" (R3). */
  function updateCounts() {
    var cards = getCards();
    var counts = emptyCounts();
    counts.all = cards.length;
    Array.prototype.forEach.call(cards, function (card) {
      var selection = cardSelection(card);
      if (counts[selection] !== undefined) counts[selection]++;
    });
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-exam-type-count]"),
      function (el) {
        var type = el.getAttribute("data-exam-type-count") || "all";
        var label = el.getAttribute("data-exam-type-label") || type;
        var count = counts[type] !== undefined ? counts[type] : 0;
        el.textContent = label + " (" + count + ")";
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
      var visible = type === "all" || cardSelection(card) === type;
      card.hidden = !visible;
      if (visible) visibleCount++;
    });

    noResultsEl.style.display = "none";
    if (visibleCount === 0) {
      noResultsEl.style.display = "";
      statusEl.textContent = "";
      return;
    }
    var scope = type !== "all" ? " de " + scopeLabel() + "." : ".";
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
    if (!statusEl || !noResultsEl || !typeSelect) return; // not on a scheduler queue page

    typeSelect.addEventListener("change", onTypeChange);

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
