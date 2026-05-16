/* =========================================================
   Namima - Service Worker
   - Precaches the ambient app shell, local JS, profiles, docs, and icons.
   - Keeps cache cleanup scoped to namima cache names only.
   - Network-first for HTML and profile/docs metadata.
   - Runtime caches p5/Tone CDN after an online load.
========================================================= */

const CACHE_PREFIX = "namima-pwa";
const VERSION = `${CACHE_PREFIX}-v2`;
const STATIC_CACHE = `${VERSION}-static`;
const RUNTIME_CACHE = `${VERSION}-runtime`;
const SCOPE_URL = new URL(self.registration.scope);

const PRECACHE_URLS = [
  "./",
  "index.html",
  "audio.js?v=stack-2",
  "music-session-adapter.js?v=stack-2",
  "sketch.js?v=stack-2",
  "manifest.webmanifest",
  "profiles/mood-profiles.json",
  "exports/namima-shape-ambient.json",
  "docs/README.md",
  "icons/icon-96.png",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "icons/icon-512-maskable.png",
  "icons/apple-touch-icon.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) =>
        Promise.all(
          PRECACHE_URLS.map((url) =>
            cache.add(url).catch((error) => {
              console.warn("[Namima SW] precache miss:", url, error);
            })
          )
        )
      )
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith(CACHE_PREFIX) && key !== STATIC_CACHE && key !== RUNTIME_CACHE)
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

function isLocalAppUrl(url) {
  return url.origin === self.location.origin && url.pathname.startsWith(SCOPE_URL.pathname);
}

function isHtmlRequest(request) {
  return request.mode === "navigate" ||
    (request.method === "GET" && request.headers.get("accept")?.includes("text/html"));
}

function isMetadataRequest(url) {
  return isLocalAppUrl(url) &&
    (url.pathname.includes("/profiles/") || url.pathname.includes("/exports/") || url.pathname.includes("/docs/"));
}

function isRuntimeCdn(url) {
  return (url.hostname === "cdn.jsdelivr.net" || url.hostname === "unpkg.com") &&
    (url.pathname.includes("/p5") || url.pathname.includes("/tone"));
}

function matchCachedRequest(request, options = {}) {
  return caches.match(request).then((cached) => {
    if (cached || !options.ignoreSearch) return cached;
    return caches.match(request, { ignoreSearch: true });
  });
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  if (request.headers.get("range")) return;

  const url = new URL(request.url);

  if (isRuntimeCdn(url)) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(RUNTIME_CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        });
      })
    );
    return;
  }

  if (!isLocalAppUrl(url)) return;

  if (isHtmlRequest(request) || isMetadataRequest(url)) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(STATIC_CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => matchCachedRequest(request, { ignoreSearch: true }).then((cached) => cached || caches.match("index.html")))
    );
    return;
  }

  event.respondWith(
    matchCachedRequest(request, { ignoreSearch: true }).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(STATIC_CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      });
    })
  );
});
