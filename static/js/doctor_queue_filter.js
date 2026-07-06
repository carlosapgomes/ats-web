/* doctor_queue_filter.js — Client-side filter for doctor pending queue cards.
 * Filters pending case cards by patient name or agency record number.
 * Survives HTMX auto-refresh by re-applying filter on htmx:afterSwap.
 * No dependencies, no persistence (no URL, storage, cookie or session).
 */
(function () {
  "use strict";

  // ── DOM references (lazily resolved) ──────────────────────────────
  var searchInput = null;
  var clearButton = null;
  var statusEl = null;
  var noResultsEl = null;

  function resolveElements() {
    searchInput = document.querySelector("[data-doctor-queue-search]");
    clearButton = document.querySelector("[data-doctor-queue-clear]");
    statusEl = document.querySelector("[data-doctor-queue-filter-status]");
    noResultsEl = document.querySelector("[data-doctor-queue-no-results]");
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

  /** Return all pending cards currently in the DOM. */
  function getCards() {
    return document.querySelectorAll("[data-doctor-queue-card]");
  }

  // ── Filter logic ──────────────────────────────────────────────────

  function applyFilter() {
    if (!searchInput || !statusEl || !noResultsEl) return;

    var term = searchInput.value;
    var trimmed = term.trim();

    // Update clear button visibility
    if (clearButton) {
      clearButton.style.display = trimmed.length > 0 ? "" : "none";
    }

    var cards = getCards();
    var total = cards.length;

    // If empty term, show all
    if (trimmed.length === 0) {
      cards.forEach(function (card) {
        card.hidden = false;
      });
      noResultsEl.style.display = "none";
      statusEl.textContent =
        total > 0
          ? "Mostrando todos os " + total + " paciente" + (total !== 1 ? "s" : "") + " pendentes."
          : "";
      return;
    }

    var normTerm = normalize(trimmed);
    var hasLettersInTerm = hasLetters(trimmed);

    // Limiar: if term has letters and fewer than 3 normalized chars, show all with hint
    if (hasLettersInTerm && normTerm.length < 3) {
      cards.forEach(function (card) {
        card.hidden = false;
      });
      noResultsEl.style.display = "none";
      statusEl.textContent = "Digite pelo menos 3 letras para filtrar por nome.";
      return;
    }

    // Filter
    var visibleCount = 0;
    cards.forEach(function (card) {
      var name = card.getAttribute("data-patient-name") || "";
      var record = card.getAttribute("data-agency-record-number") || "";
      var normName = normalize(name);
      var normRecord = normalize(record);
      var matches = normName.indexOf(normTerm) !== -1 || normRecord.indexOf(normTerm) !== -1;
      card.hidden = !matches;
      if (matches) visibleCount++;
    });

    // Status
    if (visibleCount === 0) {
      noResultsEl.style.display = "";
      statusEl.textContent = "";
    } else {
      noResultsEl.style.display = "none";
      statusEl.textContent =
        "Mostrando " + visibleCount + " de " + total + " paciente" + (total !== 1 ? "s" : "") + ".";
    }
  }

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

  /** Re-apply filter after HTMX swaps in new content. */
  function onHtmxAfterSwap(e) {
    if (e && e.detail && e.detail.target && e.detail.target.id === "doctor-queue-content") {
      // Re-resolve elements inside the swapped content could have changed,
      // but search bar lives outside #doctor-queue-content so references are stable.
      // Cards inside #doctor-queue-content are fresh — re-run filter.
      applyFilter();
    }
  }

  // ── Initialization ────────────────────────────────────────────────

  function init() {
    resolveElements();
    if (!searchInput) return; // silently return if not on a page with search

    searchInput.addEventListener("input", onInput);
    searchInput.addEventListener("keydown", onKeydown);

    if (clearButton) {
      clearButton.addEventListener("click", onClearClick);
    }

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
