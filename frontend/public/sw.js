const CACHE_NAME = "homecam-cache-v2";
const ASSETS_TO_CACHE = [
  "/",
  "/index.html",
  "/favicon.svg",
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/icon-192-maskable.png",
  "/icons/icon-512-maskable.png",
  "/icons/favicon-32.png"
];

// Install Event: cache initial asset shell
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        return cache.addAll(ASSETS_TO_CACHE);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate Event: clean up old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            return caches.delete(cache);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch Event: handle caching strategy
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Private API responses must never come from the offline cache.
  if (url.pathname.startsWith("/api/")) return;

  // Static Assets / Page Navigation: Cache-First, fallback to Network
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }

      return fetch(event.request).then((response) => {
        // Do not cache non-successful responses or cross-origin requests
        if (!response || response.status !== 200 || response.type !== "basic") {
          return response;
        }

        // Dynamically cache the new static asset
        const responseToCache = response.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, responseToCache);
        });

        return response;
      }).catch(() => {
        // Offline navigation fallback: return index.html
        if (event.request.mode === "navigate") {
          return caches.match("/");
        }
      });
    })
  );
});
