/* Service worker mínimo: cachea el shell (app estática) para que la PWA
 * instale en el celular y abra con el ícono. La API NUNCA se cachea aquí
 * (los recursos van por auth+query token y son dinámicos). */
const CACHE = "biblioteca-shell-v1";
const SHELL = ["/", "/index.html", "/manifest.webmanifest", "/pwa-192.png", "/pwa-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return;
  if (url.pathname.startsWith("/media/") || url.pathname.startsWith("/auth")) return; // API fuera
  if (event.request.destination === "document") {
    // navigaciones: red primero, shell si no hay red
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put("/index.html", copy));
          return res;
        })
        .catch(() => caches.match("/index.html")),
    );
    return;
  }
  // assets estáticos (assets compilados): cache-first
  if (url.pathname.startsWith("/assets/") || SHELL.includes(url.pathname)) {
    event.respondWith(
      caches.match(event.request).then(
        (hit) =>
          hit ||
          fetch(event.request).then((res) => {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(event.request, copy));
            return res;
          }),
      ),
    );
  }
});
