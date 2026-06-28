/* ATS Web — Service Worker */

const CACHE_NAME = "ats-cache-v3";
const STATIC_ASSETS = [
  "/static/manifest.json",
  "/static/js/app.js",
  "/static/css/app.css",
  "/static/icons/icon.svg",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

/* Install: pre-cache static assets */
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

/* Activate: clean old caches */
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) => {
      return Promise.all(
        names
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

/* Fetch: cache-first for static, network-first for HTML */
self.addEventListener("fetch", (event) => {
  // Never intercept POST/PUT/DELETE form submissions. They must go directly to
  // Django with the browser's normal cookie/CSRF semantics.
  if (event.request.method !== "GET") {
    return;
  }

  const url = new URL(event.request.url);

  // Network-first for static assets to avoid stale JS after quick fixes.
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          return caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, response.clone());
            return response;
          });
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Network-first for HTML pages
  if (event.request.mode === "navigate") {
    // Bypass for file-viewing routes (PDF/attachments): Chromium's native PDF
    // viewer does not render when the navigation response is delivered via
    // respondWith, leaving the new tab blank. Let the browser fetch natively.
    if (url.pathname.endsWith("/pdf/") || url.pathname.includes("/attachments/")) {
      return;
    }
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match("/");
      })
    );
    return;
  }

  // Default: network-only for everything else
  return;
});
