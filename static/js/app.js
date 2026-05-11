/* ATS Web — Vanilla JavaScript */

// Service Worker registration
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/js/sw.js').catch(() => {});
  });
}
