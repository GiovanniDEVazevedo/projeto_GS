const CACHE_NAME = "safrasmart-v1";
const URLS_CACHEAR = ["/"];

self.addEventListener("install", evento => {
    evento.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(URLS_CACHEAR);
        })
    );
    self.skipWaiting();
});

self.addEventListener("activate", evento => {
    evento.waitUntil(
        caches.keys().then(nomes => {
            return Promise.all(
                nomes.filter(n => n !== CACHE_NAME).map(n => caches.delete(n))
            );
        })
    );
});

self.addEventListener("fetch", evento => {
    evento.respondWith(
        caches.match(evento.request).then(resposta => {
            return resposta || fetch(evento.request);
        })
    );
});
