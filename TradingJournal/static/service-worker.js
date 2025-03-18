const CACHE_NAME = 'trading-journal-cache-v1';
const urlsToCache = [
  '/',
  '/static/styles.css',
  '/static/script.js',
  '/dashboard',
  // Add other key routes and assets here...
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});
