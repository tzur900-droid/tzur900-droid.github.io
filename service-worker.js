const CACHE_NAME = "alfon-netanya-v4";
const APP_SHELL = [
  "./",
  "./index.html",
  "./style.css",
  "./app.js",
  "./manifest.json",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/apple-touch-icon.png",
  "./icons/favicon-32.png"
];

const APP_CODE_PATTERN = /\.(html|js|css)$/;

function freshUrl(url) {
  // Appending a unique query param guarantees the request is treated as a
  // new resource, bypassing the browser's own HTTP cache entirely (a plain
  // network-first fetch can otherwise still be silently answered from the
  // browser's HTTP cache, e.g. GitHub Pages' 10-minute max-age header).
  const u = new URL(url, self.location.href);
  u.searchParams.set("swcb", Date.now().toString());
  return u.toString();
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.all(
        APP_SHELL.map((url) =>
          fetch(freshUrl(url)).then((res) => cache.put(url, res))
        )
      )
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  // Only handle our own same-origin app files. Firebase/Firestore requests
  // (auth, live data channels, CDN scripts) must reach the network normally.
  if (url.origin !== self.location.origin) return;
  const isAppCode = APP_CODE_PATTERN.test(url.pathname) || url.pathname.endsWith("/");

  if (isAppCode) {
    // Network-first (bypassing HTTP cache) so updates show up immediately.
    // Falls back to the cached copy only when offline.
    event.respondWith(
      fetch(freshUrl(event.request.url))
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => caches.match(event.request).then((cached) => cached || caches.match("./index.html")))
    );
  } else {
    // Cache-first for static assets (icons) that rarely change.
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        });
      })
    );
  }
});
