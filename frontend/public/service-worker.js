const CACHE_PREFIX = "tls-static-";
const CACHE_NAME = `${CACHE_PREFIX}__TLS_BUILD_ID__`;
const MAX_STATIC_ENTRIES = 80;
const APP_SHELL = [
  "/assets/brand/tls-favicon.png",
  "/assets/brand/tls-favicon-light.png",
  "/assets/brand/tls-favicon-dark.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
});

self.addEventListener("message", (event) => {
  let origin = event.origin;
  if (!origin && event.source?.url) {
    try { origin = new URL(event.source.url).origin; } catch { return; }
  }
  if (origin !== self.location.origin) return;
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names
          .filter((name) => (name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME) || ["tls-public-config", "tls-seo-preview", "tls-images"].includes(name))
          .map((name) => caches.delete(name)),
      ))
      .then(() => self.clients.claim()),
  );
});

async function networkFirst(request) {
  try {
    return await fetch(request, { cache: "no-store" });
  } catch {
    return new Response('<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Verbindung fehlt</title><body><h1>Keine Verbindung</h1><p>Bitte prüfe deine Internetverbindung und lade diese Seite erneut. Für die Anmeldung und E-Mail-Bestätigung ist eine Verbindung erforderlich.</p></body></html>', {
      status: 503,
      headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" },
    });
  }
}

async function staticCache(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok && response.type === "basic") {
    await cache.put(request, response.clone());
    const keys = await cache.keys();
    while (keys.length > MAX_STATIC_ENTRIES) {
      await cache.delete(keys.shift());
    }
  }
  return response;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  if (request.mode === "navigate") {
    event.respondWith(networkFirst(request));
    return;
  }

  if (url.pathname.startsWith("/assets/") && ["script", "style", "font", "image"].includes(request.destination)) {
    event.respondWith(staticCache(request));
  }
});
