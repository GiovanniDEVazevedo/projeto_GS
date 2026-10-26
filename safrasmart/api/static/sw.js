const CACHE_NAME = 'safrasmart-v4-clima-cobertura-20261026';
const SHELL = ['/', '/static/app.js', '/static/storage.js', '/static/sync.js', '/static/manifest.json', '/static/icon.svg'];
self.addEventListener('install', event => {
    event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL)));
    self.skipWaiting();
});
self.addEventListener('activate', event => {
    event.waitUntil((async () => {
        for (const nome of await caches.keys()) {
            if (nome.startsWith('safrasmart-') && nome !== CACHE_NAME) await caches.delete(nome);
        }
        await self.clients.claim();
    })());
});
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);
    // APIs, POSTs e fontes externas nunca usam o cache da interface.
    if (event.request.method !== 'GET' || url.origin !== self.location.origin || !SHELL.includes(url.pathname)) return;
    event.respondWith((async () => {
        try {
            const response = await fetch(event.request, {signal: AbortSignal.timeout(5000)});
            if (response.ok) {
                const cache = await caches.open(CACHE_NAME);
                await cache.put(url.pathname, response.clone());
                return response;
            }
            return (await caches.match(url.pathname)) || response;
        } catch (error) {
            const cached = await caches.match(url.pathname);
            if (cached) return cached;
            throw error;
        }
    })());
});
