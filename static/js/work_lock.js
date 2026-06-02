/* ATS Web — Work Lock Heartbeat and Release
 *
 * Monitors human activity on the page and periodically renews the
 * work-leasing lock while the user is actively interacting.
 * On pagehide, attempts an explicit release (best-effort).
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

    /* ── Release on pagehide (best-effort) ────────────────────────── */

    function sendRelease() {
        var body = new FormData();
        body.append('lock_token', lockToken);
        body.append('csrfmiddlewaretoken', getCSRFToken());

        /* sendBeacon is preferred; fallback to fetch with keepalive */
        if (navigator.sendBeacon) {
            navigator.sendBeacon(releaseUrl, body);
        } else {
            fetch(releaseUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCSRFToken(),
                },
                body: body,
                credentials: 'same-origin',
                keepalive: true,
            }).catch(function () { /* silent — best effort */ });
        }
    }

    if (typeof window.addEventListener === 'function') {
        window.addEventListener('pagehide', sendRelease);
    }

    /* ── Start periodic heartbeat ─────────────────────────────────── */

    setInterval(sendRenew, heartbeatMs);
})();
