(function () {
  "use strict";

  var BADGE_SELECTOR = "[data-notifications-badge]";
  var DEFAULT_INTERVAL_MS = 45 * 1000; // 45 seconds
  var MAX_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes cap for backoff
  var BACKOFF_MULTIPLIER = 2;

  var badgeEl = document.querySelector(BADGE_SELECTOR);
  if (!badgeEl) {
    return; // No badge on this page (anonymous, login, etc.)
  }

  var unreadCountUrl = badgeEl.getAttribute("data-unread-count-url");
  if (!unreadCountUrl) {
    return; // No polling URL configured
  }

  var currentInterval = DEFAULT_INTERVAL_MS;
  var timeoutId = null;

  /**
   * Fetch the unread count from the server and update the badge.
   * @returns {Promise<number>} The new unread count, or -1 on failure.
   */
  function fetchUnreadCount() {
    return fetch(unreadCountUrl, { credentials: "same-origin" })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("HTTP " + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        if (data && typeof data.unread_count === "number") {
          return data.unread_count;
        }
        throw new Error("Invalid response");
      })
      .catch(function () {
        return -1;
      });
  }

  /**
   * Update the badge DOM element with the new count.
   * @param {number} count - The unread count.
   */
  function updateBadge(count) {
    badgeEl.setAttribute("data-count", String(count));

    // Update visible count badge inside the link
    var countBadge = badgeEl.querySelector(".badge");
    if (count > 0) {
      if (!countBadge) {
        var newBadge = document.createElement("span");
        newBadge.className = "badge bg-danger ms-1";
        newBadge.textContent = String(count);
        badgeEl.appendChild(newBadge);
      } else {
        countBadge.textContent = String(count);
      }
    } else {
      if (countBadge) {
        countBadge.remove();
      }
    }

    // Update aria-label for accessibility
    var label =
      count > 0
        ? "Notificações: " + count + " não lidas"
        : "Notificações: nenhuma não lida";
    badgeEl.setAttribute("aria-label", label);
  }

  /**
   * Schedule the next poll.
   * @param {number} intervalMs - Milliseconds until next poll.
   */
  function scheduleNextPoll(intervalMs) {
    if (timeoutId !== null) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(function () {
      if (document.visibilityState === "visible") {
        pollOnce();
      } else {
        // Page not visible, reschedule with same interval
        scheduleNextPoll(currentInterval);
      }
    }, intervalMs);
  }

  /**
   * Perform a single poll cycle: fetch count, update badge, schedule next.
   */
  function pollOnce() {
    fetchUnreadCount().then(function (count) {
      if (count >= 0) {
        updateBadge(count);
        currentInterval = DEFAULT_INTERVAL_MS; // Reset backoff on success
      } else {
        // Error: apply backoff
        currentInterval = Math.min(
          currentInterval * BACKOFF_MULTIPLIER,
          MAX_INTERVAL_MS
        );
      }
      scheduleNextPoll(currentInterval);
    });
  }

  // Listen for visibility changes to resume polling when user returns
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") {
      // Poll immediately when user returns, then reset interval
      currentInterval = DEFAULT_INTERVAL_MS;
      if (timeoutId !== null) {
        clearTimeout(timeoutId);
      }
      pollOnce();
    }
  });

  // Start the first poll
  pollOnce();
})();
