/* scheduler_queue_filter.js — Client-side approved-dimension filter for scheduler queues.
 *
 * Pendentes tab: filters cards of ALL three groups that feed the primary
 * pending counter (WAIT_APPT + operational notices + operational issues).
 * Processados Hoje tab: simple dimension filter over processed cards.
 *
 * The queue filters by the AUTHORIZED procedure set (R5/D13). Every filterable
 * card exposes the projected selection via data-approved-selection; the legacy
 * bridge data-exam-type remains as fallback until cutover. Keys, labels and
 * counters are NOT listed here: the template renders one radio per
 * catalog-derived option (data-exam-type-label) and one counter per option
 * (data-exam-type-count) and this script reads both from the DOM (R7).
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

  /** Return the selected exam type (catalog selection key or "all") — never a
   *  hardcoded list. */
  function getSelectedType() {
    for (var i = 0; i < typeButtons.length; i++) {
      if (typeButtons[i].checked) {
        return typeButtons[i].value;
      }
    }
    return "all";
  }

  /** Human label of the active scope, read from the rendered control (R7). */
  function scopeLabel() {
    for (var i = 0; i < typeButtons.length; i++) {
      if (typeButtons[i].checked) {
        return typeButtons[i].getAttribute("data-exam-type-label") || typeButtons[i].value;
      }
    }
    return "Todos";
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

  /** Recompute per-type counters from the projected card attribute. */
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
