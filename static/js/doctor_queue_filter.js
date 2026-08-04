/* doctor_queue_filter.js — Client-side filters for doctor queue cards.
 *
 * Pendentes tab: composed filter over exam type (Todos|EDA|Colonoscopia)
 * AND patient name / agency record number search.
 * Decididos Hoje tab: simple exam type filter without search.
 *
 * The type selection lives in radio buttons ([data-doctor-exam-filter]) and
 * the term in the search input; switching type never clears the term and
 * clearing the term never resets the type. HTMX polling re-applies both on
 * htmx:afterSwap because the controls live outside #doctor-queue-content.
 *
 * No dependencies, no persistence (no URL, storage, cookie or session).
 */
(function () {
  "use strict";

  // ── DOM references (lazily resolved) ──────────────────────────────
  var searchInput = null;
  var clearButton = null;
  var statusEl = null;
  var noResultsEl = null;
  var typeButtons = [];

  function resolveElements() {
    searchInput = document.querySelector("[data-doctor-queue-search]");
    clearButton = document.querySelector("[data-doctor-queue-clear]");
    statusEl = document.querySelector("[data-doctor-queue-filter-status]");
    noResultsEl = document.querySelector("[data-doctor-queue-no-results]");
    typeButtons = Array.prototype.slice.call(
      document.querySelectorAll("[data-doctor-exam-filter]")
    );
  }

  // ── Helpers ───────────────────────────────────────────────────────

  /** Normalize text: lowercase, NFD-decompose, remove combining diacritics, trim. */
  function normalize(text) {
    return String(text)
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  /** Check if term contains any letter characters. */
  function hasLetters(term) {
    return /[a-z\u00e0-\u024f]/i.test(term);
  }

  /** Return all queue cards currently in the DOM. */
  function getCards() {
    return document.querySelectorAll("[data-doctor-queue-card]");
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

  // ── Filter logic (type + term composed) ───────────────────────────

  function applyFilter() {
    if (!statusEl || !noResultsEl) return;

    var term = searchInput ? searchInput.value : "";
    var trimmed = term.trim();
    var type = getSelectedType();

    // Clear button visibility follows the term only.
    if (clearButton) {
      clearButton.style.display = trimmed.length > 0 ? "" : "none";
    }

    updateCounts();

    var cards = getCards();
    var total = cards.length;

    var normTerm = normalize(trimmed);
    var hasLettersInTerm = hasLetters(trimmed);
    // Limiar: termo com letras e menos de 3 chars normalizados não filtra o nome.
    var thresholdHint = trimmed.length > 0 && hasLettersInTerm && normTerm.length < 3;

    var visibleCount = 0;
    Array.prototype.forEach.call(cards, function (card) {
      var matchesType =
        type === "all" || (card.getAttribute("data-exam-type") || "") === type;
      var matchesTerm = true;
      if (trimmed.length > 0 && !thresholdHint) {
        var name = card.getAttribute("data-patient-name") || "";
        var record = card.getAttribute("data-agency-record-number") || "";
        matchesTerm =
          normalize(name).indexOf(normTerm) !== -1 ||
          normalize(record).indexOf(normTerm) !== -1;
      }
      var visible = matchesType && matchesTerm;
      card.hidden = !visible;
      if (visible) visibleCount++;
    });

    noResultsEl.style.display = "none";
    if (thresholdHint) {
      statusEl.textContent = "Digite pelo menos 3 letras para filtrar por nome.";
      return;
    }
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

  /** Clear only the term; the selected type (radio state) is preserved. */
  function clearFilter() {
    if (!searchInput) return;
    searchInput.value = "";
    applyFilter();
    searchInput.focus();
  }

  // ── Event handlers ────────────────────────────────────────────────

  function onInput() {
    applyFilter();
  }

  function onKeydown(e) {
    if (e.key === "Escape" && document.activeElement === searchInput) {
      e.preventDefault();
      clearFilter();
    }
  }

  function onClearClick() {
    clearFilter();
  }

  function onTypeChange() {
    // Termo permanece no campo; apenas o escopo de tipo muda.
    applyFilter();
  }

  /** Re-apply composed filter after HTMX swaps in new cards. */
  function onHtmxAfterSwap(e) {
    if (e && e.detail && e.detail.target && e.detail.target.id === "doctor-queue-content") {
      applyFilter();
    }
  }

  // ── Initialization ────────────────────────────────────────────────

  function init() {
    resolveElements();
    if (!statusEl || !noResultsEl) return; // not on a queue page

    if (searchInput) {
      searchInput.addEventListener("input", onInput);
      searchInput.addEventListener("keydown", onKeydown);
    }
    if (clearButton) {
      clearButton.addEventListener("click", onClearClick);
    }
    typeButtons.forEach(function (btn) {
      btn.addEventListener("change", onTypeChange);
    });

    document.addEventListener("htmx:afterSwap", onHtmxAfterSwap);

    // Initial filter in case there's a prefilled value
    applyFilter();
  }

  // Run on DOMContentLoaded
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
