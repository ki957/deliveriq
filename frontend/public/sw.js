/* global self, caches */
// App-shell service worker (DDR-15, DDR-113 (12)): makes the Delivery PWA installable and lets the shell
// open while offline. It caches only the shell (HTML, JS, CSS, icons). It never caches or queues API calls:
// actions stay blocked offline, and location points are buffered in memory by the page, not here.
const CACHE = "deliveriq-shell-v1";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(["/", "/manifest.webmanifest", "/icon.svg"])),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) => Promise.all(names.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (
    event.request.method !== "GET" ||
    url.origin !== self.location.origin ||
    url.pathname.startsWith("/api/")
  ) {
    return; // network only
  }
  if (event.request.mode === "navigate") {
    // SPA routes: network first, the cached shell when offline.
    event.respondWith(fetch(event.request).catch(() => caches.match("/")));
    return;
  }
  if (/\.(js|css|svg|webmanifest|woff2?)$/.test(url.pathname)) {
    event.respondWith(
      caches.match(event.request).then(
        (hit) =>
          hit ||
          fetch(event.request).then((response) => {
            if (response.ok) {
              const copy = response.clone();
              caches.open(CACHE).then((cache) => cache.put(event.request, copy));
            }
            return response;
          }),
      ),
    );
  }
});
