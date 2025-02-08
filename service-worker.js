const CACHE_NAME = "amount-distribution-cache-v1";
const urlsToCache = [
    "/",
    "/index.html",
    "/assets/logo.png",
    "/app.py",
    "/styles.css"
];

// Install event
self.addEventListener("install", event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(urlsToCache);
        })
    );
});

// Fetch event
self.addEventListener("fetch", event => {
    event.respondWith(
        caches.match(event.request).then(response => {
            return response || fetch(event.request);
        })
    );
});
