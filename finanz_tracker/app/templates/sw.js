// Service Worker des Finanz-Trackers {{ version }}
// Finanzdaten werden bewusst NICHT zwischengespeichert: Seiten kommen immer frisch vom Server.
// Im Cache liegen nur Stylesheet, Skript, Symbole und eine Offline-Seite.
const CACHE = "finanz-{{ version }}";
const DATEIEN = [
  "/offline",
  "/static/app.css?v={{ version }}",
  "/static/app.js?v={{ version }}",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(DATEIEN)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (req.mode === "navigate") {
    e.respondWith(fetch(req).catch(() => caches.match("/offline")));
    return;
  }
  if (url.pathname.startsWith("/static/")) {
    e.respondWith(caches.match(req).then((treffer) => treffer || fetch(req)));
  }
});
