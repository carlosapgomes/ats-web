/* ATS Web — Work Lock Heartbeat and Release
 *
 * Monitors human activity on the page and periodically renews the
 * work-leasing lock while the user is actively interacting.
 * On navigation away (link click, pagehide), attempts an explicit
 * release (best-effort).
 *
 * Protected submit guard: when a form containing the current lock_token
 * is submitted, a flag prevents sendRelease() from firing. This avoids
 * a race condition where pagehide/visibilitychange could release the lock
 * before the main POST completes.
 *
 * Configuration is read from <meta name="work-lock-config"> or a
 * script with id="work-lock-config" containing data attributes:
 *   data-renew-url     — POST endpoint for lock renewal
 *   data-release-url   — POST endpoint for lock release
 *   data-lock-token    — current lock token (UUID)
 *   data-heartbeat-ms  — interval between heartbeats in ms (default 60000)
 *   data-grace-ms      — max ms without activity before idle (default 240000)
 *
 * No external dependencies.
 */
(function () {
    "use strict";

    var configEl = document.querySelector('[data-work-lock-config]');
    if (!configEl) {
        configEl = document.getElementById('work-lock-config');
    }
    if (!configEl) return;  /* not a lock-managed page */

    var renewUrl    = configEl.getAttribute('data-renew-url') || '';
    var releaseUrl  = configEl.getAttribute('data-release-url') || '';
    var lockToken   = configEl.getAttribute('data-lock-token') || '';
    var heartbeatMs = parseInt(configEl.getAttribute('data-heartbeat-ms'), 10) || 60000;
    var graceMs     = parseInt(configEl.getAttribute('data-grace-ms'), 10) || 240000;

    if (!renewUrl || !releaseUrl || !lockToken) return;

    /* ── Protected submit guard ─────────────────────────────────────── */

    var protectedSubmitInProgress = false;

    function isProtectedSubmitInProgress() {
        return protectedSubmitInProgress || window.ATS_WORK_LOCK_SUBMITTING === true;
    }

    /* Listen for form submits with our lock_token.
     * Uses bubble phase so a modal/validation can call preventDefault() first.
     * Only marks as protected if the submit was NOT cancelled and the form
     * contains an input[name="lock_token"] with value === current lockToken.
     * This intentionally excludes forms without lock_token (e.g. operational
     * communication, attachments, administrative closure). */
    document.addEventListener('submit', function (event) {
        if (event.defaultPrevented) return;

        var form = event.target;
        if (!form || !form.querySelector) return;

        var tokenInput = form.querySelector('input[name="lock_token"]');
        if (tokenInput && tokenInput.value === lockToken) {
            protectedSubmitInProgress = true;
            window.ATS_WORK_LOCK_SUBMITTING = true;
            log('protected submit detected — suppressing release');
        }
    });

    /* ── Debug logging ────────────────────────────────────────────── */

    var DEBUG = configEl.getAttribute('data-debug') === 'true';

    function log() {
        if (!DEBUG) return;
        var args = Array.prototype.slice.call(arguments);
        args.unshift('[work-lock]');
        console.log.apply(console, args);
    }

    log('initialized — renewUrl:', renewUrl, 'token:', lockToken);

    /* ── Activity tracking ───────────────────────────────────────── */

    var lastActivity = Date.now();
    var activityEvents = ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart', 'focus'];

    function onActivity() {
        lastActivity = Date.now();
        hideWarning();
    }

    for (var i = 0; i < activityEvents.length; i++) {
        window.addEventListener(activityEvents[i], onActivity, { passive: true });
    }

    function hasRecentActivity() {
        return (Date.now() - lastActivity) < graceMs;
    }

    /* ── Warning element ─────────────────────────────────────────── */

    var warningEl = document.getElementById('work-lock-warning');

    function showWarning(msg) {
        if (!warningEl) return;
        warningEl.textContent = msg;
        warningEl.style.display = 'block';
    }

    function hideWarning() {
        if (!warningEl) return;
        warningEl.style.display = 'none';
        warningEl.textContent = '';
    }

    function disableSubmit() {
        var btn = document.getElementById('btn-submit');
        if (btn) btn.disabled = true;
    }

    /* ── CSRF token helper ────────────────────────────────────────── */

    function getCSRFToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.getAttribute('content');

        var csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (csrfInput) return csrfInput.value;

        var cookie = document.cookie.match(/csrftoken=([^;]+)/);
        return cookie ? cookie[1] : '';
    }

    /* ── Renew heartbeat ──────────────────────────────────────────── */

    function sendRenew() {
        if (!hasRecentActivity()) {
            return;  /* no recent activity — skip renewal */
        }

        var body = new FormData();
        body.append('lock_token', lockToken);

        fetch(renewUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken(),
            },
            body: body,
            credentials: 'same-origin',
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    lastActivity = Date.now();
                    hideWarning();
                } else {
                    showWarning(data.error || 'Falha ao renovar reserva.');
                    disableSubmit();
                }
            })
            .catch(function () {
                showWarning('Erro de conexão ao renovar reserva.');
            });
    }

    /* ── Release lock ─────────────────────────────────────────────── */

    var released = false;

    function sendRelease() {
        /* Do not release during a protected submit */
        if (isProtectedSubmitInProgress()) return;

        if (released) return;
        released = true;

        var body = new FormData();
        body.append('lock_token', lockToken);
        var csrfToken = getCSRFToken();

        log('sendRelease — url:', releaseUrl, 'token:', lockToken, 'csrf:', csrfToken ? csrfToken.substring(0, 8) + '...' : 'EMPTY');

        fetch(releaseUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
            },
            body: body,
            credentials: 'same-origin',
            keepalive: true,
        }).then(function (r) {
            log('release response — status:', r.status, r.statusText);
            if (!r.ok) {
                r.text().then(function (t) { log('release body:', t.substring(0, 200)); });
            }
        }).catch(function (e) {
            log('release error:', e);
        });
    }

    /* ── Release triggers ─────────────────────────────────────────── */

    /* 1. Intercept link clicks that navigate away from the lock page.
     *    This is the most reliable trigger because it fires synchronously
     *    before the browser initiates navigation. */
    document.addEventListener('click', function (e) {
        var link = e.target.closest('a[href]');
        if (!link) return;

        var href = link.getAttribute('href') || '';
        /* Skip javascript: links and anchor-only links */
        if (href.indexOf('javascript:') === 0 || href.charAt(0) === '#') return;
        /* Skip links that open in new tab */
        if (link.target === '_blank') return;

        log('link click intercepted — href:', href);
        sendRelease();
    }, true);

    /* 2. pagehide — fires when page is being unloaded */
    window.addEventListener('pagehide', function () {
        log('pagehide — sending release');
        sendRelease();
    });

    /* ── Start periodic heartbeat ─────────────────────────────────── */

    setInterval(sendRenew, heartbeatMs);
})();
